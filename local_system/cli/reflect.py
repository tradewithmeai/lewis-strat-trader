"""
/reflect-now — run a full backtest cycle on all strategies and update the
traffic light state.

Steps:
1. Load 1m bars from the lake (configurable date range, default last 2 years)
2. Run walk-forward backtest on active strategy and all challengers
3. Print BacktestResult summaries
4. Update state/comparison.json with new scores and traffic light states
5. Print updated traffic light table

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


def _load_active_strategy():
    from local_system.strategies.markov import MarkovStrategy

    params = {}
    if STRATEGY_FILE.exists():
        spec = yaml.safe_load(STRATEGY_FILE.read_text())
        params = spec.get("params", {})
    return MarkovStrategy(params=params)


def _load_challengers():
    from local_system.strategies.rsi_meanrev import RsiMeanRevStrategy

    return [RsiMeanRevStrategy()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Run backtest reflection cycle")
    parser.add_argument("--years", type=float, default=2.0, help="Years of history to backtest")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
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

    # Load backfill 1m data, then resample to 1h for strategy signals.
    # Strategies (RSI mean-rev, Markov regime) are calibrated for hourly bars:
    # RSI 30/65 thresholds on 1m fire every few minutes; on 1h they fire rarely.
    df_1m = load_bars("BTCUSDT", start, end, backfill_only=True)
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
        active_result = run_backtest(df, active, symbol="BTCUSDT")
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
            result = run_backtest(df, challenger, symbol="BTCUSDT")
            print(result.summary())
            print()

            # Update traffic light
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
