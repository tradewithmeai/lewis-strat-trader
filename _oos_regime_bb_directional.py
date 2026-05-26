"""
OOS validation: regime_bb + directional bias on held-out 2024-05-25 -> 2026-05-24.

Training cutoff is hard at 2024-05-25 — no OOS data touches the strategy fit.
The OOS window is split into regime blocks (bull/bear/ranging) using the full-
history regime detector (so bars near the cutoff get a valid 90-day lookback).
Each block is tested with the appropriate directional bias:
    bull   -> long-only
    bear   -> short-only
    ranging -> both

Contrast with the naive _oos_regime_bb.py which applies no directional bias
and uses 80% of the OOS window itself as a second training phase.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd

LAKE_ROOT = os.environ.get("LAKE_ROOT", "")
if not LAKE_ROOT:
    raise RuntimeError("LAKE_ROOT not set")

from local_system.backtester import run_backtest
from local_system.lake_adapter import load_bars, resample_ohlcv
from local_system.strategies.regime_bb import RegimeBbStrategy

# Re-use the regime helpers from the walkforward CLI
from local_system.cli.walkforward import (
    _BEAR_THRESHOLD_DEFAULT,
    _BULL_THRESHOLD_DEFAULT,
    _REGIME_WINDOW,
    _detect_regimes,
)

# ── Config ────────────────────────────────────────────────────────────────────
TRAIN_START = date(2021, 5, 25)
OOS_START = date(2024, 5, 25)  # hard cutoff — nothing after here touched during fit
OOS_END = date(2026, 5, 24)
MIN_FOLD_DAYS = 30
DIRECTION_MAP = {"bull": "long", "bear": "short", "ranging": "both"}

BEST_PARAMS = {
    "bb_period": 20,
    "bb_std": 2.0,
    "adx_period": 14,
    "adx_threshold": 20.0,
    "rvol_threshold": 1.5,
    "slope_threshold": 0.005,
    "stop_loss_pct": 8.0,
    "cooldown_days": 3,
}

# ── Load ──────────────────────────────────────────────────────────────────────
print(f"Loading bars {TRAIN_START} -> {OOS_END}...")
df_1m = load_bars("BTCUSDT", TRAIN_START, OOS_END, backfill_only=True)
df = resample_ohlcv(df_1m, "1h")
print(f"Loaded {len(df_1m):,} 1m bars -> {len(df):,} 1h bars\n")

# Find OOS boundary in the hourly index
oos_start_ts = pd.Timestamp(OOS_START, tz="UTC")
train_end_idx = df.index.searchsorted(oos_start_ts)

print(
    f"Train:  {df.index[0].date()} -> {df.index[train_end_idx - 1].date()}  ({train_end_idx:,} bars)"
)
print(
    f"OOS:    {df.index[train_end_idx].date()} -> {df.index[-1].date()}  ({len(df) - train_end_idx:,} bars)\n"
)

# ── Regime detection on full history ─────────────────────────────────────────
# Running on full data so bars near the OOS cutoff get a valid 90-day lookback.
daily_full = df["close"].resample("1D").last().dropna()
regime_full = _detect_regimes(daily_full, _BULL_THRESHOLD_DEFAULT, _BEAR_THRESHOLD_DEFAULT)

# Build contiguous blocks from the full history
raw_blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
cur_label = None
cur_start = None
for ts, lbl in regime_full.items():
    if lbl != cur_label:
        if cur_label is not None:
            raw_blocks.append((cur_start, ts, cur_label))
        cur_label = lbl
        cur_start = ts
if cur_label is not None:
    raw_blocks.append((cur_start, regime_full.index[-1], cur_label))

# Merge blocks shorter than MIN_FOLD_DAYS into prior
merged_blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
for start, end, lbl in raw_blocks:
    if (end - start).days < MIN_FOLD_DAYS and merged_blocks:
        prev_start, _, prev_lbl = merged_blocks[-1]
        merged_blocks[-1] = (prev_start, end, prev_lbl)
    else:
        merged_blocks.append((start, end, lbl))

# Keep only blocks that overlap with the OOS window
oos_end_ts = pd.Timestamp(OOS_END, tz="UTC")
oos_blocks = [
    (max(s, oos_start_ts), min(e, oos_end_ts), lbl)
    for s, e, lbl in merged_blocks
    if e > oos_start_ts and s < oos_end_ts
]

print("OOS regime blocks:")
for s, e, lbl in oos_blocks:
    days = (e - s).days
    direction = DIRECTION_MAP.get(lbl, "both")
    print(f"  {s.date()} -> {e.date()}  [{lbl}]  direction={direction}  ({days}d)")
print()

# ── Per-fold backtest ─────────────────────────────────────────────────────────
fold_results = []
all_trades = []

for fold_start_ts, fold_end_ts, regime_label in oos_blocks:
    idx_start = df.index.searchsorted(fold_start_ts)
    idx_end = min(df.index.searchsorted(fold_end_ts), len(df))

    if idx_end - idx_start < 30:
        print(f"  Skipping {fold_start_ts.date()} -> {fold_end_ts.date()} — too few bars")
        continue

    # Train = all bars before this fold's test window
    # This always includes the full pre-OOS training period
    df_fold = df.iloc[:idx_end]
    train_frac = idx_start / len(df_fold)
    direction = DIRECTION_MAP.get(regime_label, "both")

    strategy = RegimeBbStrategy(params=BEST_PARAMS)
    result = run_backtest(
        df_fold,
        strategy,
        symbol="BTCUSDT",
        train_frac=train_frac,
        direction=direction,
    )
    result.regime = regime_label  # type: ignore[attr-defined]
    result.direction = direction  # type: ignore[attr-defined]

    ci_tag = "[+]" if result.sharpe_ci_low > 0 else ("[~]" if result.sharpe_ci_high > 0 else "[-]")
    print(
        f"{fold_start_ts.date()} -> {fold_end_ts.date()}  [{regime_label}]  direction={direction}"
    )
    print(
        f"  Sharpe {result.sharpe:+.3f}  "
        f"CI [{result.sharpe_ci_low:+.2f}, {result.sharpe_ci_high:+.2f}]  {ci_tag}"
    )
    print(
        f"  Return {result.total_return * 100:+.1f}%  "
        f"MaxDD {result.max_drawdown * 100:.1f}%  "
        f"Trades {result.n_trades}"
    )
    print()

    fold_results.append(result)
    all_trades.extend(result.trades)

# ── Aggregate ─────────────────────────────────────────────────────────────────
print("=" * 60)
print(f"Aggregate OOS  ({OOS_START} -> {OOS_END})")
if fold_results:
    avg_sharpe = sum(r.sharpe for r in fold_results) / len(fold_results)
    total_ret = sum(r.total_return for r in fold_results) / len(fold_results)
    total_trades = sum(r.n_trades for r in fold_results)
    win_rate = sum(1 for t in all_trades if t.pnl_pct > 0) / total_trades if total_trades else 0.0
    n_pos_sharpe = sum(1 for r in fold_results if r.sharpe > 0)
    print(f"  Avg Sharpe   : {avg_sharpe:+.3f}")
    print(f"  Avg Return   : {total_ret * 100:+.1f}%")
    print(f"  Positive folds: {n_pos_sharpe}/{len(fold_results)}")
    print(f"  Total trades : {total_trades}  Win rate {win_rate:.1%}")
else:
    print("  No folds produced results.")

print()
print("Params used:")
for k, v in BEST_PARAMS.items():
    print(f"  {k}: {v}")
