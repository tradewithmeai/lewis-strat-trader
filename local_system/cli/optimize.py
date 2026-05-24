"""
optimize.py -- parameter grid search for a strategy.

Sweeps the strategy's registered grid, runs walk-forward backtests for each
combination in parallel, and ranks results by Sharpe ratio.

WARNING: selecting parameters based on test-set Sharpe is in-sample
optimisation. Use the best params as a starting point, then validate on a
separate held-out period before going live.

Usage:
    uv run python -m local_system.cli.optimize --strategy ema_crossover
    uv run python -m local_system.cli.optimize --strategy markov_regime
    uv run python -m local_system.cli.optimize --strategy rsi_meanrev --from 2023-01-01 --to 2025-12-31
    uv run python -m local_system.cli.optimize --strategy ema_crossover --workers 8
"""

from __future__ import annotations

import argparse
import itertools
import os
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent.parent.parent
STATE_DIR = ROOT / "state"


def _expand_grid(grid: dict[str, list]) -> list[dict]:
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    return [dict(zip(keys, combo)) for combo in combos]


# ── Worker (module-level so it's picklable on Windows spawn) ──────────────────

_WORKER_DF: pd.DataFrame | None = None


def _worker_init(df_bytes: bytes) -> None:
    global _WORKER_DF
    _WORKER_DF = pickle.loads(df_bytes)


def _run_one(task: tuple) -> dict:
    strategy_name, params, symbol = task
    from local_system.backtester import run_backtest
    from local_system.strategies.registry import get_strategy

    strategy = get_strategy(strategy_name, params)
    try:
        result = run_backtest(_WORKER_DF, strategy, symbol=symbol)
        return {
            **params,
            "sharpe": round(result.sharpe, 3),
            "ci_low": round(result.sharpe_ci_low, 3),
            "ci_high": round(result.sharpe_ci_high, 3),
            "return_pct": round(result.total_return * 100, 1),
            "cagr_pct": round(result.cagr * 100, 1),
            "win_rate_pct": round(result.win_rate * 100, 1),
            "max_dd_pct": round(result.max_drawdown * 100, 1),
            "n_trades": result.n_trades,
            "error": None,
        }
    except Exception as exc:
        return {**params, "error": str(exc)}


# ── Display ───────────────────────────────────────────────────────────────────


def _print_results(rows: list[dict], param_keys: list[str], strategy_name: str) -> None:
    try:
        from rich import box
        from rich.console import Console
        from rich.table import Table

        console = Console(width=120)
        table = Table(
            title=f"Optimisation results: {strategy_name}  (sorted by Sharpe)",
            box=box.SIMPLE_HEAVY,
            show_lines=False,
            min_width=100,
        )

        # Shorten param names so columns don't truncate
        def _shorten(k: str) -> str:
            return (
                k.replace("stop_loss_pct", "sl%")
                .replace("regime_signal_min", "sig_min")
                .replace("use_trend_filter", "trend_f")
                .replace("_period", "_per")
            )

        for k in param_keys:
            table.add_column(_shorten(k), style="cyan", justify="right", min_width=6, no_wrap=True)
        table.add_column("Sharpe", justify="right", min_width=7, no_wrap=True)
        table.add_column("95% CI", justify="right", style="dim", min_width=13, no_wrap=True)
        table.add_column("Ret%", justify="right", min_width=6, no_wrap=True)
        table.add_column("WR%", justify="right", min_width=5, no_wrap=True)
        table.add_column("DD%", justify="right", min_width=5, no_wrap=True)
        table.add_column("N", justify="right", min_width=4, no_wrap=True)

        profitable = 0
        for r in rows:
            if r.get("error"):
                continue
            sharpe = r["sharpe"]
            if sharpe > 0:
                profitable += 1
            color = "green" if sharpe > 0 else ("yellow" if sharpe > -0.5 else "red")
            table.add_row(
                *[str(r[k]) for k in param_keys],
                f"[{color}]{sharpe:.3f}[/{color}]",
                f"[{r['ci_low']:.2f}, {r['ci_high']:.2f}]",
                f"{r['return_pct']:.1f}",
                f"{r['win_rate_pct']:.1f}",
                f"{r['max_dd_pct']:.1f}",
                str(r["n_trades"]),
            )

        console.print(table)
        total = len([r for r in rows if not r.get("error")])
        console.print(f"[bold]{profitable}/{total}[/bold] combinations profitable (Sharpe > 0)\n")

    except ImportError:
        header = "\t".join(
            param_keys + ["sharpe", "ci_low", "ci_high", "return%", "win%", "dd%", "trades"]
        )
        print(header)
        for r in rows:
            if r.get("error"):
                continue
            vals = [str(r[k]) for k in param_keys] + [
                str(r["sharpe"]),
                str(r["ci_low"]),
                str(r["ci_high"]),
                str(r["return_pct"]),
                str(r["win_rate_pct"]),
                str(r["max_dd_pct"]),
                str(r["n_trades"]),
            ]
            print("\t".join(vals))


def _save_csv(rows: list[dict], strategy_name: str, start: date, end: date) -> Path:
    STATE_DIR.mkdir(exist_ok=True)
    fname = STATE_DIR / f"optimize_{strategy_name}_{start}_{end}.csv"
    good_rows = [r for r in rows if not r.get("error")]
    pd.DataFrame(good_rows).to_csv(fname, index=False)
    return fname


# ── Main ──────────────────────────────────────────────────────────────────────


def main() -> None:
    from local_system.strategies.registry import get_grid, list_strategies

    parser = argparse.ArgumentParser(description="Parameter grid search for a strategy")
    parser.add_argument(
        "--strategy", required=True, choices=list_strategies(), help="Strategy to optimise"
    )
    parser.add_argument("--years", type=float, default=3.0, help="Years of history (default 3)")
    parser.add_argument("--from", dest="from_date", default=None, help="Start date YYYY-MM-DD")
    parser.add_argument("--to", dest="to_date", default=None, help="End date YYYY-MM-DD")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(2, (os.cpu_count() or 4) - 1),
        help="Parallel workers",
    )
    parser.add_argument("--symbol", default="BTCUSDT")
    args = parser.parse_args()

    end = date.fromisoformat(args.to_date) if args.to_date else date.today() - timedelta(days=1)
    start = (
        date.fromisoformat(args.from_date)
        if args.from_date
        else end - timedelta(days=int(args.years * 365))
    )

    print(f"\nOptimising: {args.strategy}  |  {start} -> {end}  |  {args.workers} workers")
    print("Loading bars...", flush=True)

    from local_system.lake_adapter import load_bars, resample_ohlcv

    df_1m = load_bars(args.symbol, start, end, backfill_only=True)
    if df_1m.empty:
        print("ERROR: No data in lake for that date range.")
        return
    df = resample_ohlcv(df_1m, "1h")
    print(f"Loaded {len(df):,} 1h bars  ({start} to {end})\n")

    grid = get_grid(args.strategy)
    param_combos = _expand_grid(grid)
    n = len(param_combos)
    print(f"Grid: {' x '.join(f'{k}({len(v)})' for k, v in grid.items())} = {n} combinations")
    print(f"Running backtests ({args.workers} workers)...\n", flush=True)

    df_bytes = pickle.dumps(df)
    tasks = [(args.strategy, params, args.symbol) for params in param_combos]

    results: list[dict] = []
    completed = 0

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_worker_init,
        initargs=(df_bytes,),
    ) as pool:
        futures = {pool.submit(_run_one, t): t for t in tasks}
        for fut in as_completed(futures):
            completed += 1
            print(f"\r  {completed}/{n}", end="", flush=True)
            results.append(fut.result())

    print()

    results.sort(key=lambda r: r.get("sharpe", -999), reverse=True)

    print(
        "\n[!] OVERFITTING WARNING: these results are from the same test window used to "
        "select params.\n    Validate the top combinations on a separate held-out period "
        "before using them live.\n"
    )

    _print_results(results, list(grid.keys()), args.strategy)

    csv_path = _save_csv(results, args.strategy, start, end)
    print(f"Full results saved to: {csv_path}\n")

    best = next((r for r in results if not r.get("error")), None)
    if best:
        print("Best combination:")
        for k in grid.keys():
            print(f"  {k}: {best[k]}")
        print(f"  -> Sharpe {best['sharpe']:.3f}  [{best['ci_low']:.2f}, {best['ci_high']:.2f}]")
        print(
            f"  -> Return {best['return_pct']:.1f}%  "
            f"WinRate {best['win_rate_pct']:.1f}%  "
            f"MaxDD {best['max_dd_pct']:.1f}%  "
            f"Trades {best['n_trades']}\n"
        )


if __name__ == "__main__":
    main()
