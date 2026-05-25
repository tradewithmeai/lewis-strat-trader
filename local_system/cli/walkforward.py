"""
Walk-forward comparison across all strategies.

Three folding modes:
  --folds N (default)     Equal-time folds. Each fold trains on all prior data
                          and tests on the new period — N-1 independent Sharpe
                          readings per strategy.

  --regime-folds          Regime-aware folds. Detects bull / bear / ranging
                          periods via rolling 90-day return on daily bars and
                          places fold boundaries at regime transitions. Each
                          fold is labelled by its dominant regime.

  --regime-override       Manually specify test windows with explicit regime
                          labels. Bypasses auto-detection entirely.

Filtering:
  --only-regimes LABEL    Keep only folds matching the given regime label(s).
                          Works with both --regime-folds and --regime-override.
                          Comma-separated for multiple: --only-regimes bull,ranging

Usage:
    uv run python -m local_system.cli.walkforward
    uv run python -m local_system.cli.walkforward --years 5 --folds 5
    uv run python -m local_system.cli.walkforward --regime-folds
    uv run python -m local_system.cli.walkforward --regime-folds --only-regimes ranging

    # Manual ranging windows — test bollinger on periods you believe were ranging:
    uv run python -m local_system.cli.walkforward \\
        --regime-override 2021-06-01:2021-09-30:ranging 2023-01-01:2023-10-01:ranging \\
        --only-regimes ranging

    # Tune the auto-detector thresholds (default ±10% / 90 days):
    uv run python -m local_system.cli.walkforward --regime-folds \\
        --bull-threshold 0.05 --bear-threshold 0.05 --only-regimes ranging
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
_BULL_THRESHOLD_DEFAULT = 0.10  # +10% over 90 days = bull
_BEAR_THRESHOLD_DEFAULT = 0.10  # 10% drop over 90 days = bear


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


def _detect_regimes(
    df_daily: pd.Series,
    bull_threshold: float = _BULL_THRESHOLD_DEFAULT,
    bear_threshold: float = _BEAR_THRESHOLD_DEFAULT,
) -> pd.Series:
    """
    Classify each daily bar as 'bull', 'bear', or 'ranging' using a rolling
    90-day return. Returns a Series with the same index.
    """
    roll_ret = df_daily.pct_change(_REGIME_WINDOW)
    regime = pd.Series("ranging", index=df_daily.index)
    regime[roll_ret > bull_threshold] = "bull"
    regime[roll_ret < -bear_threshold] = "bear"
    return regime


def _dates_to_fold_boundaries(
    df: pd.DataFrame,
    blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]],
) -> list[tuple[int, int, str]]:
    """
    Convert (start_date, end_date, label) blocks into integer index tuples
    (test_start_idx, test_end_idx, label) suitable for run_backtest.
    Blocks with fewer than 30 daily bars are skipped.
    """
    folds: list[tuple[int, int, str]] = []
    n = len(df)
    daily = df["close"].resample("1D").last().dropna()
    for start, end, lbl in blocks:
        idx_start = df.index.searchsorted(start)
        idx_end = df.index.searchsorted(end)
        idx_end = min(idx_end, n)
        # Count daily bars in this window — strategies need enough history
        n_daily = daily.index.searchsorted(end) - daily.index.searchsorted(start)
        if n_daily < 30 or idx_end - idx_start < 30:
            continue
        folds.append((idx_start, idx_end, lbl))
    return folds


def _regime_fold_boundaries(
    df: pd.DataFrame,
    bull_threshold: float = _BULL_THRESHOLD_DEFAULT,
    bear_threshold: float = _BEAR_THRESHOLD_DEFAULT,
) -> list[tuple[int, int, str]]:
    """
    Auto-detect regime transitions and return fold boundaries.
    Blocks shorter than 30 days are merged into the adjacent block.
    """
    daily = df["close"].resample("1D").last().dropna()
    regime = _detect_regimes(daily, bull_threshold, bear_threshold)

    # Build contiguous blocks
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

    # Merge blocks shorter than 30 days into previous
    MIN_DAYS = 30
    merged: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for start, end, lbl in blocks:
        if (end - start).days < MIN_DAYS and merged:
            prev_start, _, prev_lbl = merged[-1]
            merged[-1] = (prev_start, end, prev_lbl)
        else:
            merged.append((start, end, lbl))

    return _dates_to_fold_boundaries(df, merged)


def _parse_regime_overrides(df: pd.DataFrame, specs: list[str]) -> list[tuple[int, int, str]]:
    """
    Parse --regime-override entries of the form 'YYYY-MM-DD:YYYY-MM-DD:label'
    and convert to integer index tuples.
    """
    blocks: list[tuple[pd.Timestamp, pd.Timestamp, str]] = []
    for spec in specs:
        parts = spec.strip().split(":")
        if len(parts) != 3:
            print(
                f"  [warn] Ignoring malformed --regime-override '{spec}' (expected FROM:TO:LABEL)"
            )
            continue
        try:
            start = pd.Timestamp(parts[0], tz="UTC")
            end = pd.Timestamp(parts[1], tz="UTC")
        except ValueError:
            print(f"  [warn] Ignoring --regime-override '{spec}': bad date format")
            continue
        blocks.append((start, end, parts[2]))

    # Sort by start date so training windows accumulate correctly
    blocks.sort(key=lambda b: b[0])
    return _dates_to_fold_boundaries(df, blocks)


def _run_folds(
    df: pd.DataFrame,
    strat,
    symbol: str,
    folds: list[tuple[int, int, str]],
) -> list:
    """
    Run backtests for explicit (test_start_idx, test_end_idx, label) folds.
    Train = all bars before test window. Returns BacktestResult list with
    .regime attribute injected.
    """
    from local_system.backtester import run_backtest

    results = []
    for test_start, test_end, regime_label in folds:
        df_fold = df.iloc[:test_end]
        if len(df_fold) < 30:
            continue
        train_frac = test_start / len(df_fold) if test_start > 0 else 0.0
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
    parser.add_argument(
        "--regime-override",
        nargs="+",
        metavar="FROM:TO:LABEL",
        default=None,
        help=(
            "Manual regime folds. Each entry: YYYY-MM-DD:YYYY-MM-DD:label. "
            "Bypasses auto-detection. Example: "
            "--regime-override 2023-01-01:2023-10-01:ranging 2021-06-01:2021-09-30:ranging"
        ),
    )
    parser.add_argument(
        "--only-regimes",
        default=None,
        metavar="LABEL[,LABEL]",
        help=(
            "Keep only folds whose regime label matches. "
            "Comma-separated for multiple. Example: --only-regimes ranging  "
            "or --only-regimes bull,ranging"
        ),
    )
    parser.add_argument(
        "--bull-threshold",
        type=float,
        default=_BULL_THRESHOLD_DEFAULT,
        metavar="FRAC",
        help=f"Rolling 90-day return above which = bull (default {_BULL_THRESHOLD_DEFAULT})",
    )
    parser.add_argument(
        "--bear-threshold",
        type=float,
        default=_BEAR_THRESHOLD_DEFAULT,
        metavar="FRAC",
        help=f"Rolling 90-day return below which (abs) = bear (default {_BEAR_THRESHOLD_DEFAULT})",
    )
    args = parser.parse_args()

    end = date.fromisoformat(args.to_date) if args.to_date else date.today() - timedelta(days=1)
    start = (
        date.fromisoformat(args.from_date)
        if args.from_date
        else end - timedelta(days=int(args.years * 365))
    )

    use_regime_mode = args.regime_folds or args.regime_override is not None
    if args.regime_override:
        mode = f"manual regime override ({len(args.regime_override)} windows)"
    elif args.regime_folds:
        mode = f"regime-aware (bull>{args.bull_threshold:.0%} bear>{args.bear_threshold:.0%})"
    else:
        mode = f"{args.folds} equal-time folds"

    if args.only_regimes:
        allowed = {r.strip() for r in args.only_regimes.split(",")}
        mode += f"  [filter: {', '.join(sorted(allowed))}]"
    else:
        allowed = None

    print(f"\nWalk-forward: {start} -> {end}  ({mode})")
    print("Loading bars...", flush=True)

    from local_system.backtester import run_walk_forward
    from local_system.lake_adapter import load_bars, load_bars_yf, resample_ohlcv

    df_1m = load_bars(args.symbol, start, end, backfill_only=True)
    if df_1m.empty:
        print("Lake has no historical data — falling back to Yahoo Finance (daily bars).")
        df = load_bars_yf(args.symbol, start, end, interval="1d")
        if df.empty:
            print("ERROR: No data from Yahoo Finance either.")
            return
        print(f"Loaded {len(df):,} daily bars from Yahoo Finance\n")
    else:
        df = resample_ohlcv(df_1m, "1h")
        print(f"Loaded {len(df_1m):,} 1m bars -> {len(df):,} 1h bars\n")

    # Pre-compute folds once — same for all strategies
    if args.regime_override:
        regime_folds = _parse_regime_overrides(df, args.regime_override)
    elif args.regime_folds:
        regime_folds = _regime_fold_boundaries(df, args.bull_threshold, args.bear_threshold)
    else:
        regime_folds = None

    # Apply regime filter
    if regime_folds is not None and allowed is not None:
        regime_folds = [(s, e, lbl) for s, e, lbl in regime_folds if lbl in allowed]
        if not regime_folds:
            print(f"No folds matched --only-regimes filter '{args.only_regimes}'.")
            print("Try --regime-override to manually specify date windows.")
            return

    strategies = _load_all_strategies()

    # Run walk-forward for every strategy
    all_results: dict[str, list] = {}
    for strat in strategies:
        print(f"  Running {strat.name}...", flush=True)
        try:
            if regime_folds is not None:
                folds = _run_folds(df, strat, symbol=args.symbol, folds=regime_folds)
            else:
                folds = run_walk_forward(df, strat, symbol=args.symbol, n_splits=args.folds)
            all_results[strat.name] = folds
        except Exception as exc:
            print(f"  ERROR {strat.name}: {exc}")
            all_results[strat.name] = []

    if not all_results:
        print("No results.")
        return

    fold_label_fn = _regime_fold_label if use_regime_mode else _fold_label
    fold_labels = []
    for folds in all_results.values():
        if folds:
            fold_labels = [fold_label_fn(r) for r in folds]
            break

    if not fold_labels:
        print("No folds produced results.")
        return

    n_folds = len(fold_labels)
    col_w = 26 if use_regime_mode else 18
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
        row = f"{name:<{name_w}}" + "".join(f"{c:>{col_w}}" for c in cells) + f"{avg:>+12.2f}"
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
            regime_tag = f"  regime={getattr(r, 'regime', '?')}" if use_regime_mode else ""
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
