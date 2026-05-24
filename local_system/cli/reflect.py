"""
/reflect-now -- run a full backtest cycle on all strategies and update the
traffic light state.

Steps:
1. Load 1m bars from the lake (configurable date range, default last 3 years)
2. Run walk-forward backtest on active strategy and all challengers
3. Print BacktestResult summaries
4. Update state/comparison.json with new scores and traffic light states
5. Print updated traffic light table

Active strategy:  state/strategy.yaml   (strategy name + params)
Challengers:      state/challengers.yaml (list of strategy names)
Strategy classes: local_system/strategies/registry.py

Usage (from repo root):
    uv run python -m local_system.cli.reflect
    uv run python -m local_system.cli.reflect --years 3
    uv run python -m local_system.cli.reflect --from 2022-01-01 --to 2024-12-31
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "state"
STRATEGY_FILE = STATE_DIR / "strategy.yaml"
CHALLENGERS_FILE = STATE_DIR / "challengers.yaml"


def _load_active_strategy():
    """Load the active strategy from state/strategy.yaml."""
    from local_system.strategies.registry import get_strategy

    if not STRATEGY_FILE.exists():
        raise FileNotFoundError(f"Active strategy file not found: {STRATEGY_FILE}")

    spec = yaml.safe_load(STRATEGY_FILE.read_text())
    name = spec.get("strategy", "markov_regime")
    params = spec.get("params", {})
    return get_strategy(name, params)


def _load_challengers():
    """Load challenger strategies from state/challengers.yaml."""
    from local_system.strategies.registry import get_strategy

    if not CHALLENGERS_FILE.exists():
        print(f"  [warn] {CHALLENGERS_FILE} not found — no challengers will run.")
        return []

    spec = yaml.safe_load(CHALLENGERS_FILE.read_text())
    names = spec.get("challengers", [])
    challengers = []
    for name in names:
        try:
            challengers.append(get_strategy(name))
        except ValueError as e:
            print(f"  [warn] Skipping challenger '{name}': {e}")
    return challengers


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backtest reflection cycle")
    parser.add_argument("--years", type=float, default=3.0, help="Years of history to backtest")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()

    end = date.fromisoformat(args.to_date) if args.to_date else date.today() - timedelta(days=1)
    start = (
        date.fromisoformat(args.from_date)
        if args.from_date
        else end - timedelta(days=int(args.years * 365))
    )

    print(f"\nReflection cycle: {start} -> {end}")
    print("Loading bars from lake...", flush=True)

    from local_system.backtester import run_backtest
    from local_system.lake_adapter import load_bars, resample_ohlcv
    from local_system.scoring import traffic_light_summary, update_traffic_light

    df_1m = load_bars(args.symbol, start, end, backfill_only=True)
    if df_1m.empty:
        print("ERROR: No data in lake for that date range.")
        return
    df = resample_ohlcv(df_1m, "1h")
    print(f"Loaded {len(df_1m):,} 1m bars -> resampled to {len(df):,} 1h bars ({start} to {end})\n")

    active = _load_active_strategy()
    challengers = _load_challengers()

    # ── Active strategy backtest ──────────────────────────────────────────────
    print(f"Backtesting active strategy: {active.name}")
    print("-" * 50)
    try:
        active_result = run_backtest(df, active, symbol=args.symbol)
        print(active_result.summary())
    except Exception as exc:
        print(f"ERROR backtesting {active.name}: {exc}")
        return
    print()

    # ── Challenger backtests ──────────────────────────────────────────────────
    for challenger in challengers:
        print(f"Backtesting challenger: {challenger.name}")
        print("-" * 50)
        try:
            result = run_backtest(df, challenger, symbol=args.symbol)
            print(result.summary())
            print()
            new_light = update_traffic_light(
                strategy_name=challenger.name,
                result=result,
                active_strategy_name=active.name,
                active_result=active_result,
            )
            print(f"Traffic light for {challenger.name}: {new_light}")
        except Exception as exc:
            print(f"ERROR backtesting {challenger.name}: {exc}")
        print()

    # ── Summary table ─────────────────────────────────────────────────────────
    print("\nTraffic Light Summary")
    print("=" * 60)
    print(traffic_light_summary())
    print()


if __name__ == "__main__":
    main()
