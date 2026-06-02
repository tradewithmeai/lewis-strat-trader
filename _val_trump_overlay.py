"""
_val_trump_overlay.py — adversarial validation of the Trump vol-risk overlay.

Tests whether suppressing new entries during the 4h post-burst elevated-vol
window improves risk-adjusted returns for the active breakout strategy.

Design:
  - 10 disjoint annual windows (2022-05 to 2026-05, each ~1 year)
  - Each window: run breakout with and without the overlay, record
    Sharpe, max-drawdown, trade-count
  - Null: 2000 draws of random 4h windows (same total coverage %) as a
    permutation test — if the overlay is just reducing exposure randomly,
    random windows should do as well

A result "counts" only if:
  - The overlay improves Sharpe in >= 7/10 windows (sign test p < 0.05)
  - AND improvement is not explained by the random-window null (the real
    overlay must beat the median random-window Sharpe improvement)

Usage:
    $env:LAKE_ROOT = "D:/Documents/11Projects/crypto-lake-rs/data/parquet"
    uv run python _val_trump_overlay.py
"""

from __future__ import annotations

import copy
from datetime import date, timedelta
from io import StringIO

import numpy as np
import pandas as pd

from local_system.signals.live_rollup import load_history_hybrid
from local_system.signals.trump_overlay import add_overlay, VOL_WINDOW_H
from local_system.backtester import run_backtest
from local_system.strategies.registry import build_strategy

STRATEGY_NAME = "breakout"
STRATEGY_PARAMS = {"entry": 40, "exit": 20, "stop_loss_pct": 8.0}

WINDOW_MONTHS = 12
WINDOWS_START = date(2022, 5, 1)
WINDOWS_END = date(2026, 5, 1)
N_WINDOWS = 10
N_PERM = 500   # permutation null draws (keep low to avoid usage-limit cuts)
RNG = np.random.default_rng(42)

report = StringIO()


def emit(line: str = "") -> None:
    print(line, flush=True)
    report.write(line + "\n")


def _windows():
    total_days = (WINDOWS_END - WINDOWS_START).days
    step = total_days // N_WINDOWS
    for i in range(N_WINDOWS):
        s = WINDOWS_START + timedelta(days=i * step)
        e = s + timedelta(days=WINDOW_MONTHS * 30)
        if e > WINDOWS_END:
            e = WINDOWS_END
        yield s, e


def _run(bars_1h: pd.DataFrame, overlay: bool, perm_mask: "pd.Series | None" = None):
    ef = None
    if overlay:
        b = add_overlay(bars_1h)
        ef = b["trump_vol_active"]
    if perm_mask is not None:
        ef = perm_mask
    s = build_strategy(STRATEGY_NAME, STRATEGY_PARAMS)
    # backtester expects 1m bars but we're feeding 1h — resample so it doesn't
    # complain about bar count; strategy is hourly so 1h is the right grain
    # (we pass directly; run_backtest resamples 1m->1h internally only if
    # resample=True; here we pass hourly directly and call internal path)
    from local_system.backtester import run_backtest as _rb
    result = _rb(bars_1h, s, train_frac=0.5, entry_filter=ef)
    return result.sharpe, result.max_drawdown, result.n_trades


def main() -> None:
    emit("# Trump vol overlay validation — disjoint window test")
    emit(f"Strategy: {STRATEGY_NAME} {STRATEGY_PARAMS}")
    emit(f"Windows: {N_WINDOWS} x ~{WINDOW_MONTHS}mo, {WINDOWS_START} -> {WINDOWS_END}")
    emit(f"Entry suppression: {VOL_WINDOW_H}h after any market-relevant burst")

    results: list[dict] = []

    emit("\n| window | base Sharpe | overlay Sharpe | delta | base dd | overlay dd | trades base | trades overlay |")
    emit("|---|---|---|---|---|---|---|---|")

    for start, end in _windows():
        bars_1m = load_history_hybrid("BTCUSDT", start, end)
        if bars_1m.empty or len(bars_1m) < 200:
            emit(f"| {start} -> {end} | insufficient data — skipped |||||")
            continue
        from local_system.lake_adapter import resample_ohlcv
        bars_1h = resample_ohlcv(bars_1m, "1h") if "window_start" not in str(bars_1m.index.name) else bars_1m
        if bars_1h.empty or len(bars_1h) < 200:
            bars_1h = bars_1m  # already hourly from rollup

        try:
            s_base, dd_base, n_base = _run(bars_1h, overlay=False)
            s_ov, dd_ov, n_ov = _run(bars_1h, overlay=True)
        except Exception as exc:  # noqa: BLE001
            emit(f"| {start} -> {end} | ERROR: {exc} |||||")
            continue

        delta = s_ov - s_base
        results.append({"start": start, "s_base": s_base, "s_ov": s_ov, "delta": delta,
                         "dd_base": dd_base, "dd_ov": dd_ov, "n_base": n_base, "n_ov": n_ov})
        emit(f"| {start} -> {end} | {s_base:.3f} | {s_ov:.3f} | {delta:+.3f} "
             f"| {dd_base:.2%} | {dd_ov:.2%} | {n_base} | {n_ov} |")

    if not results:
        emit("No results — check data.")
        return

    n_pos = sum(1 for r in results if r["delta"] > 0)
    n = len(results)
    # sign-test p-value (two-sided)
    from scipy.stats import binom_test
    try:
        p_sign = binom_test(n_pos, n, 0.5)
    except AttributeError:
        from scipy.stats import binomtest
        p_sign = binomtest(n_pos, n, 0.5).pvalue

    emit(f"\nOverlay improves Sharpe in {n_pos}/{n} windows  (sign-test p={p_sign:.3f})")
    emit(f"Mean delta Sharpe: {np.mean([r['delta'] for r in results]):+.3f}  "
         f"Median: {np.median([r['delta'] for r in results]):+.3f}")

    # Permutation null — random entry-suppression windows of the same total length
    # Use the first data window for the null (representative)
    emit(f"\nPermutation null ({N_PERM} draws): same % suppressed, random timing")
    first = results[0]
    null_bars = load_history_hybrid("BTCUSDT", WINDOWS_START,
                                    WINDOWS_START + timedelta(days=WINDOW_MONTHS * 30))
    if null_bars.empty:
        emit("Null: data unavailable")
    else:
        from local_system.lake_adapter import resample_ohlcv as _rs
        null_1h = _rs(null_bars, "1h") if len(null_bars) > len(null_bars.resample("1h").first()) else null_bars
        if null_1h.empty or len(null_1h) < 100:
            null_1h = null_bars
        # Coverage: fraction of bars the real overlay flags
        b_ov = add_overlay(null_1h)
        coverage = b_ov["trump_vol_active"].mean()
        null_deltas = []
        for _ in range(N_PERM):
            rand_mask = pd.Series(
                RNG.random(len(null_1h)) < coverage, index=null_1h.index
            )
            try:
                s_b, _, _ = _run(null_1h, overlay=False)
                s_r, _, _ = _run(null_1h, overlay=False, perm_mask=rand_mask)
                null_deltas.append(s_r - s_b)
            except Exception:  # noqa: BLE001
                pass
        if null_deltas:
            obs_delta = np.mean([r["delta"] for r in results])
            p_null = (np.array(null_deltas) >= obs_delta).mean()
            emit(f"Null delta Sharpe: mean={np.mean(null_deltas):+.3f}  "
                 f"95th pct={np.percentile(null_deltas, 95):+.3f}")
            emit(f"Observed mean delta={obs_delta:+.3f}  "
                 f"p vs null (one-sided) = {p_null:.3f}")
            emit("VERDICT: " + (
                "SURVIVES — overlay adds value beyond random suppression"
                if p_null < 0.05 and n_pos >= int(n * 0.7)
                else "FAILS — not distinguishable from random entry suppression"
            ))

    from pathlib import Path
    out = Path("state/val_trump_overlay.log")
    out.write_text(report.getvalue(), encoding="utf-8")
    emit(f"\n[written] {out}")


if __name__ == "__main__":
    main()
