"""
Directional regime-fold optimisation for regime_bb.

The standard optimiser (local_system.cli.optimize) ranks by single-split Sharpe
with direction='both'. That metric does NOT reward the directional-bias edge we
found (+0.61 avg fold Sharpe). This script re-optimises regime_bb against the
*actual* objective we care about: mean Sharpe across regime folds with
directional bias applied (bull=long-only, bear=short-only, ranging=both).

Train window: 2021-05-25 -> 2024-05-25 (same as the original opt; OOS 2024-05-25
-> 2026-05-24 stays held out for validation of the winner).

Saves: state/optimize_regime_bb_directional_<start>_<end>.csv (checkpointed).

Run:
    LAKE_ROOT=... uv run python _optimize_regime_bb_directional.py [--workers N]
"""

from __future__ import annotations

import argparse
import itertools
import os
import pickle
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import date
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
STATE_DIR = ROOT / "state"

TRAIN_START = date(2021, 5, 25)
TRAIN_END = date(2024, 5, 25)

# Full grid (same as registry's regime_bb grid = 864 combinations)
GRID = {
    "bb_period": [10, 15, 20],
    "bb_std": [2.0, 2.5],
    "adx_period": [10, 14],
    "adx_threshold": [20.0, 25.0, 30.0],
    "rvol_threshold": [1.0, 1.5],
    "slope_threshold": [0.003, 0.005],
    "stop_loss_pct": [3.0, 5.0, 8.0],
    "cooldown_days": [3, 7],
}


def _expand_grid(grid: dict[str, list]) -> list[dict]:
    keys = list(grid.keys())
    combos = list(itertools.product(*[grid[k] for k in keys]))
    return [dict(zip(keys, combo)) for combo in combos]


# ── Worker (module-level for Windows spawn picklability) ──────────────────────
# NOTE: pickle here is trusted — we serialise our own in-process DataFrame/folds
# to hand to our own ProcessPoolExecutor children (same pattern as cli/optimize.py).
# No external/untrusted pickle data is ever loaded.

_WORKER_DF: pd.DataFrame | None = None
_WORKER_FOLDS: list | None = None


def _worker_init(df_bytes: bytes, folds_bytes: bytes) -> None:
    global _WORKER_DF, _WORKER_FOLDS
    _WORKER_DF = pickle.loads(df_bytes)
    _WORKER_FOLDS = pickle.loads(folds_bytes)


def _run_one(params: dict) -> dict:
    """Run directional regime folds for one param combo; return aggregate stats."""
    from local_system.cli.walkforward import _run_folds
    from local_system.strategies.registry import get_strategy

    try:
        strat = get_strategy("regime_bb", params)
        results = _run_folds(
            _WORKER_DF, strat, symbol="BTCUSDT", folds=_WORKER_FOLDS, directional=True
        )
        if not results:
            return {**params, "error": "no folds"}
        sharpes = [r.sharpe for r in results]
        returns = [r.total_return for r in results]
        trades = sum(r.n_trades for r in results)
        n_pos = sum(1 for s in sharpes if s > 0)
        # CI-aware: count folds whose lower CI bound is > 0 (genuinely significant)
        n_sig = sum(1 for r in results if r.sharpe_ci_low > 0)
        return {
            **params,
            "avg_sharpe": round(sum(sharpes) / len(sharpes), 3),
            "best_fold": round(max(sharpes), 3),
            "worst_fold": round(min(sharpes), 3),
            "pos_folds": n_pos,
            "sig_folds": n_sig,
            "n_folds": len(results),
            "avg_return_pct": round(sum(returns) / len(returns) * 100, 1),
            "total_trades": trades,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {**params, "error": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Directional regime-fold opt for regime_bb")
    parser.add_argument(
        "--workers",
        type=int,
        default=max(2, (os.cpu_count() or 4) // 2),
        help="Parallel workers (default: half of cores, to leave room for other jobs)",
    )
    args = parser.parse_args()

    print(f"\nDirectional regime-fold optimisation: regime_bb")
    print(f"Train window: {TRAIN_START} -> {TRAIN_END}  |  {args.workers} workers")
    print("Loading bars...", flush=True)

    from local_system.cli.walkforward import _regime_fold_boundaries
    from local_system.lake_adapter import load_bars, resample_ohlcv

    df_1m = load_bars("BTCUSDT", TRAIN_START, TRAIN_END, backfill_only=True)
    if df_1m.empty:
        print("ERROR: lake empty for train window.")
        return
    df = resample_ohlcv(df_1m, "1h")
    print(f"Loaded {len(df_1m):,} 1m bars -> {len(df):,} 1h bars\n")

    folds = _regime_fold_boundaries(df)
    print(f"Regime folds: {len(folds)}")
    for s, e, lbl in folds:
        print(f"  fold idx [{s}:{e}]  {lbl}")
    print()

    combos = _expand_grid(GRID)
    n = len(combos)
    print(f"Grid: {' x '.join(f'{k}({len(v)})' for k, v in GRID.items())} = {n} combinations")
    print(f"Each combo runs {len(folds)} directional folds. Running...\n", flush=True)

    df_bytes = pickle.dumps(df)
    folds_bytes = pickle.dumps(folds)

    results: list[dict] = []
    completed = 0
    STATE_DIR.mkdir(exist_ok=True)
    csv_path = STATE_DIR / f"optimize_regime_bb_directional_{TRAIN_START}_{TRAIN_END}.csv"

    with ProcessPoolExecutor(
        max_workers=args.workers,
        initializer=_worker_init,
        initargs=(df_bytes, folds_bytes),
    ) as pool:
        futures = {pool.submit(_run_one, c): c for c in combos}
        for fut in as_completed(futures):
            completed += 1
            results.append(fut.result())
            print(f"\r  {completed}/{n}", end="", flush=True)
            # Checkpoint every 50 combos so a kill doesn't lose progress
            if completed % 50 == 0:
                good = [r for r in results if not r.get("error")]
                if good:
                    pd.DataFrame(good).sort_values("avg_sharpe", ascending=False).to_csv(
                        csv_path, index=False
                    )

    print()

    good = [r for r in results if not r.get("error")]
    good.sort(key=lambda r: r.get("avg_sharpe", -999), reverse=True)
    pd.DataFrame(good).to_csv(csv_path, index=False)

    n_profitable = sum(1 for r in good if r["avg_sharpe"] > 0)
    print(f"\n{n_profitable}/{len(good)} combos with positive avg fold Sharpe")
    print(f"Full results: {csv_path}\n")

    print("Top 10 by avg fold Sharpe (directional):")
    print("-" * 90)
    for r in good[:10]:
        pkeys = [
            "bb_period",
            "bb_std",
            "adx_period",
            "adx_threshold",
            "rvol_threshold",
            "slope_threshold",
            "stop_loss_pct",
            "cooldown_days",
        ]
        pstr = " ".join(f"{k.split('_')[0][:4]}{k.split('_')[-1][:1]}={r[k]}" for k in pkeys)
        print(
            f"  avgS {r['avg_sharpe']:+.3f}  pos {r['pos_folds']}/{r['n_folds']}  "
            f"sig {r['sig_folds']}  ret {r['avg_return_pct']:+.1f}%  "
            f"trades {r['total_trades']}  | {pstr}"
        )
    print()


if __name__ == "__main__":
    main()
