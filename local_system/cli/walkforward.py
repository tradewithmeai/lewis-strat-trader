"""
Walk-forward comparison across all strategies.

Two folding modes:
  --folds N (default)     Equal-time folds. Each fold trains on all prior data
                          and tests on the new period — N-1 independent Sharpe
                          readings per strategy.

  --regime-folds          Regime-aware folds. Detects bull / bear / ranging
                          periods via rolling 90-day return on daily bars and
                          places fold boundaries at regime transitions. Each
                          fold is labelled by its dominant regime, making it
                          easy to see which strategies survive regime changes.

Usage:
    uv run python -m local_system.cli.walkforward
    uv run python -m local_system.cli.walkforward --years 5 --folds 5
    uv run python -m local_system.cli.walkforward --regime-folds
    uv run python -m local_system.cli.walkforward --from 2021-01-01 --to 2026-01-01 --regime-folds
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "state"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"
CHALLENGERS_FILE = STATE_DIR / "challengers.yaml"

# Rolling window (daily bars) for regime detection
_REGIME_WINDOW = 90  # days
_BULL_THRESHOLD = 0.10  # +10% over 90 days = bull
_BEAR_THRESHOLD = -0.10  # -10% over 90 days = bear


def _load_all_strategies() -> list:
    from local_system.strategies.registry import get_strategy

    spec = yaml.safe_load(STRATEGY_FILE.read_text())
    active_name = spec.get("strategy", "markov_regime")
    active_params = spec.get("params", {})
    active = get_strategy(active_name, active_params)

    challengers = []
    if CHALLENGERS_FILE.exists():
        cspec = yaml.safe_load(CHALLENGERS_FILE.read_text())
        for name in cspec.get("challengers", []):
            try:
                challengers.append(get_strategy(name))
            except ValueError as e:
                print(f"  [warn] Skipping '{name}': {e}")

    return [active] + challengers


def _fold_label(result) -> str:
    return f"{result.start.strftime('%Y-%m')}->{result.end.strftime('%Y-%m')}"


def _sharpe_cell(s: float, ci_low: float, ci_high: float) -> str:
    if ci_low > 0:
        marker = " [+]"
    elif ci_high < 0:
        marker = " [-]"
    else:
        marker = " [~]"
    return f"{s:+.2f}{marker}"


def _detect_regimes(df_daily: pd.Series) -> pd.Series:
    """
    Classify each daily bar as 'bull', 'bear', or 'ranging' using a rolling
    90-day return. Returns a Series with the same index.
    """
    roll_ret = df_daily.pct_change(_REGIME_WINDOW)
    regime = pd.Series("ranging", index=df_daily.index)
    regime[roll_ret > _BULL_THRESHOLD] = "bull"
    regime[roll_ret < _BEAR_THRESHOLD] = "bear"
    return regime


def _regime_fold_boundaries(df: pd.DataFrame) -> list[tuple[int, int, str]]:
    """
    Find regime transitions and return fold boundaries as list of
    (test_start_idx, test_end_idx, dominant_regime_label).

    Strategy: detect each contiguous regime block on daily bars, then map
    back to 1h bar indices. Blocks shorter than 30 days are merged into the
    adjacent block to avoid degenerate folds.
    """
    daily = df["close"].resample("1D").last().dropna()
    regime = _detect_regimes(daily)

    # Build contiguous blocks: [(start_date, end_date, label), ...]
    blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    cur_label = None
    cur_start = None
    for ts, lbl in regime.items():
        if lbl != cur_label:
            if cur_label is not None:
                blocks.append((cur_start, ts, cur_label))
            cur_label = lbl
            cur_start = ts
    if cur_label is not None:
        blocks.append((cur_start, regime.index[-1], cur_label))

    # Merge short blocks (< 30 days) into the previous one
    MIN_DAYS = 30
    merged: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for start, end, lbl in blocks:
        days = (end - start).days
        if days < MIN_DAYS and merged:
            prev_start, _, prev_lbl = merged[-1]
            merged[-1] = (prev_start, end, prev_lbl)
        else:
            merged.append((start, end, lbl))

    # Map date boundaries back to 1h bar integer indices
    folds: list[tuple[int, int, str]] = []
    n = len(df)
    for i, (start, end, lbl) in enumerate(merged):
        # Find first 1h bar >= start and last 1h bar < end
        idx_start = df.index.searchsorted(start)
        idx_end = df.index.searchsorted(end)
        idx_end = min(idx_end, n)
        if idx_end - idx_start < 200:
            continue
        folds.append((idx_start, idx_end, lbl))

    return folds


def _run_regime_folds(df: pd.DataFrame, strat, symbol: str) -> list:
    """
    Run backtests for each regime fold. Train = all prior bars, test = fold.
    Returns BacktestResult list with an extra .regime attribute injected.
    """
    from local_system.backtester import run_backtest

    folds = _regime_fold_boundaries(df)
    if not folds:
        return []

    results = []
    for test_start, test_end, regime_label in folds:
        df_fold = df.iloc[:test_end]
        if len(df_fold) < 200:
            continue
        train_frac = test_start / len(df_fold)
        result = run_backtest(df_fold, strat, symbol=symbol, train_frac=train_frac)
        result.regime = regime_label  # type: ignore[attr-defined]
        results.append(result)
    return results


def _regime_fold_label(result) -> str:
    regime = getattr(result, "regime", "?")
    return f"{result.start.strftime('%Y-%m')}->{result.end.strftime('%Y-%m')} [{regime[:3]}]"


def main() -> None:
    parser = argparse.ArgumentParser(description="Walk-forward strategy comparison")
    parser.add_argument("--years", type=float, default=5.0)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--from", dest="from_date", default=None)
    parser.add_argument("--to", dest="to_date", default=None)
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument(
        "--regime-folds",
        action="store_true",
        help="Use regime-aware fold boundaries instead of equal-time folds",
    )
    args = parser.parse_args()

    end = date.fromisoformat(args.to_date) if args.to_date else date.today() - timedelta(days=1)
    start = (
        date.fromisoformat(args.from_date)
        if args.from_date
        else end - timedelta(days=int(args.years * 365))
    )

    mode = "regime-aware" if args.regime_folds else f"{args.folds} equal-time folds"
    print(f"\nWalk-forward: {start} -> {end}  ({mode})")
    print("Loading bars...", flush=True)

    from local_system.backtester import run_walk_forward
    from local_system.lake_adapter import load_bars, load_bars_yf, resample_ohlcv

    df_1m = load_bars(args.symbol, start, end, backfill_only=True)
    if df_1m.empty:
        # Yahoo Finance 1h data is limited to the last 730 days; use daily bars
        # for longer windows. All strategies resample to daily internally so this
        # is equivalent — daily close is the decision point for every signal.
        print("Lake has no historical data — falling back to Yahoo Finance (daily bars).")
        df = load_bars_yf(args.symbol, start, end, interval="1d")
        if df.empty:
            print("ERROR: No data from Yahoo Finance either.")
            return
        print(f"Loaded {len(df):,} daily bars from Yahoo Finance\n")
    else:
        df = resample_ohlcv(df_1m, "1h")
        print(f"Loaded {len(df_1m):,} 1m bars -> {len(df):,} 1h bars\n")

    strategies = _load_all_strategies()

    # Run walk-forward for every strategy, collect fold results
    all_results: dict[str, list] = {}
    for strat in strategies:
        print(f"  Running {strat.name}...", flush=True)
        try:
            if args.regime_folds:
                folds = _run_regime_folds(df, strat, symbol=args.symbol)
            else:
                folds = run_walk_forward(df, strat, symbol=args.symbol, n_splits=args.folds)
            all_results[strat.name] = folds
        except Exception as exc:
            print(f"  ERROR {strat.name}: {exc}")
            all_results[strat.name] = []

    if not all_results:
        print("No results.")
        return

    # Collect fold labels from the first strategy that has results
    fold_label_fn = _regime_fold_label if args.regime_folds else _fold_label
    fold_labels = []
    for folds in all_results.values():
        if folds:
            fold_labels = [fold_label_fn(r) for r in folds]
            break

    n_folds = len(fold_labels)

    col_w = 26 if args.regime_folds else 18
    name_w = 20

    # ── Print Sharpe table ────────────────────────────────────────────────────
    print("\nSharpe per fold  ([+]=CI>0  [~]=CI spans zero  [-]=CI<0)")
    print("=" * (name_w + col_w * n_folds + 12))

    header = (
        f"{'Strategy':<{name_w}}"
        + "".join(f"{lbl:>{col_w}}" for lbl in fold_labels)
        + f"{'Avg':>{12}}"
    )
    print(header)
    print("-" * (name_w + col_w * n_folds + 12))

    for name, folds in all_results.items():
        if not folds:
            print(f"{name:<{name_w}}  (no results)")
            continue
        cells = []
        sharpes = []
        for r in folds:
            cells.append(_sharpe_cell(r.sharpe, r.sharpe_ci_low, r.sharpe_ci_high))
            sharpes.append(r.sharpe)
        avg = sum(sharpes) / len(sharpes)
        avg_str = f"{avg:+.2f}"
        row = f"{name:<{name_w}}" + "".join(f"{c:>{col_w}}" for c in cells) + f"{avg_str:>{12}}"
        print(row)

    print()

    # ── Print return table ────────────────────────────────────────────────────
    print("Return % per fold")
    print("=" * (name_w + col_w * n_folds + 12))
    print(header)
    print("-" * (name_w + col_w * n_folds + 12))

    for name, folds in all_results.items():
        if not folds:
            continue
        cells = []
        returns = []
        for r in folds:
            cells.append(f"{r.total_return * 100:+.1f}%")
            returns.append(r.total_return)
        avg = sum(returns) / len(returns)
        row = (
            f"{name:<{name_w}}" + "".join(f"{c:>{col_w}}" for c in cells) + f"{avg * 100:>+10.1f}%"
        )
        print(row)

    print()

    # ── Per-strategy detail ───────────────────────────────────────────────────
    print("Per-fold detail")
    print("=" * 60)
    for name, folds in all_results.items():
        if not folds:
            continue
        print(f"\n{name}")
        for r in folds:
            regime_tag = f"  regime={getattr(r, 'regime', '?')}" if args.regime_folds else ""
            print(
                f"  {fold_label_fn(r)}{regime_tag}  "
                f"Sharpe {r.sharpe:+.2f} [{r.sharpe_ci_low:+.2f},{r.sharpe_ci_high:+.2f}]  "
                f"Return {r.total_return * 100:+.1f}%  "
                f"MaxDD {r.max_drawdown * 100:.1f}%  "
                f"Trades {r.n_trades}"
            )

    print()


if __name__ == "__main__":
    main()
