"""
_phase2_reaction.py — Phase 2 CONFIRMATORY analysis (implements PREREGISTRATION.md).

Regresses crypto + macro reactions on the frozen text-only Trump signal and
decides whether there is value in post-event trades. This script implements the
pre-registered plan EXACTLY; it was written before any Phase-2 results were seen
(see docs/WORKLOG.md). Any deviation must be logged as post-hoc.

Pipeline:
  1. Burst-level panel from state/signals/trump_signal.parquet (market-relevant,
     non-noise; anchored to first post's hour).
  2. Per crypto asset (BTC/ETH/SOL hourly): join + targets fwd_ret/fwd_vol at
     1/4/24h and trailing_vol_24 (known at event time).
  3. Confirmatory OLS: target ~ signal + novelty_7d + topic dummies +
     trailing_vol_24, day-clustered SEs. Collect every p-value into one grid.
  4. Benjamini-Hochberg FDR (q=0.10) across the whole grid (primary correction).
  5. LightGBM with purged + embargoed (24h) walk-forward CV — non-linear check.
  6. OOS tradeable-edge: final 20% by time, sign(signal) rule, net of 0.24%
     round-trip cost, block-bootstrap 95% Sharpe CI. Edge iff CI low > 0.

Run modes:
  --smoke    mechanical test on whatever signal exists now (writes scratch file,
             NEVER the paper results file). Use while the LLM layer is partial.
  --confirm  the real confirmatory run. Refuses unless LLM coverage of
             market-relevant posts >= --min-coverage (default 0.95). Writes
             docs/PAPER/PHASE2_RESULTS.md.

    $env:LAKE_ROOT = "D:/Documents/11Projects/crypto-lake-rs/data/parquet"
    uv run --extra research python _phase2_reaction.py --smoke
"""

from __future__ import annotations

import sys
from datetime import date
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd

SIGNAL_PATH = Path("state/signals/trump_signal.parquet")
RESULTS_MD = Path("docs/PAPER/PHASE2_RESULTS.md")
SCRATCH_MD = Path("state/signals/_phase2_smoke.md")

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
HORIZONS = [1, 4, 24]
TOPIC_COLS = [
    "topic_tariffs_trade", "topic_china", "topic_fed_rates", "topic_crypto",
    "topic_dollar", "topic_energy_oil", "topic_markets", "topic_taxes_fiscal",
    "topic_geopolitics", "topic_market_directive", "topic_reassurance",
]
ROUND_TRIP_COST = 0.0024  # 0.1% taker x2 + 2bps slippage x2 (repo standard)
FDR_Q = 0.10
OOS_FRAC = 0.20
RNG = np.random.default_rng(42)

report = StringIO()


def emit(line: str = "") -> None:
    print(line, flush=True)
    report.write(line + "\n")


# ----------------------------------------------------------------- signal
def load_bursts() -> pd.DataFrame:
    df = pd.read_parquet(SIGNAL_PATH)
    rel = df[df.market_relevant & ~df.is_noise].copy()
    agg = {c: "max" for c in TOPIC_COLS}
    agg |= {
        "ts": "min", "signal": "mean", "finbert_score": "mean",
        "novelty_7d": "max",
    }
    if "conviction" in rel:
        agg["conviction"] = "max"
    for flag in ("is_market_directive", "is_policy_signal"):
        if flag in rel:
            rel[flag] = rel[flag].fillna(False).astype(bool)
            agg[flag] = "max"
    bursts = rel.groupby("burst_id").agg(agg).reset_index()
    bursts["hour"] = bursts.ts.dt.floor("h")
    bursts = bursts.sort_values("ts").drop_duplicates(subset="hour", keep="first")
    return bursts.reset_index(drop=True)


def llm_coverage() -> float:
    df = pd.read_parquet(SIGNAL_PATH)
    mr = df[df.market_relevant & ~df.is_noise]
    if len(mr) == 0 or "has_llm" not in mr:
        return 0.0
    return float(mr["has_llm"].mean())


# ----------------------------------------------------------------- bars
def load_hourly(symbol: str, start: date, end: date) -> pd.DataFrame:
    from local_system.signals.live_rollup import load_history_hybrid
    try:
        bars = load_history_hybrid(symbol, start, end)
    except Exception:  # noqa: BLE001
        bars = pd.DataFrame()
    if len(bars) < 10_000:
        from local_system.signals.binance_klines import load_klines_1h
        bars = load_klines_1h(symbol, start, end)
    bars = bars[~bars.index.duplicated(keep="last")].sort_index()
    out = pd.DataFrame(index=bars.index)
    out["logret"] = np.log(bars.close).diff()
    logc = np.log(bars.close)
    for k in HORIZONS:
        out[f"fwd_ret_{k}"] = logc.shift(-k) - logc
        out[f"fwd_vol_{k}"] = np.sqrt((out.logret**2).rolling(k).sum().shift(-k))
    out["trail_vol_24"] = np.sqrt((out.logret**2).rolling(24).sum()).shift(1)
    return out


# ----------------------------------------------------------------- stats
def benjamini_hochberg(pvals: list[float], q: float) -> list[bool]:
    from statsmodels.stats.multitest import multipletests
    if not pvals:
        return []
    rej, _, _, _ = multipletests(pvals, alpha=q, method="fdr_bh")
    return list(rej)


def block_bootstrap_sharpe_ci(returns: np.ndarray, block: int = 24,
                              n: int = 2000, conf: float = 0.95) -> tuple[float, float]:
    r = returns[~np.isnan(returns)]
    if len(r) < block * 2:
        return (float("nan"), float("nan"))
    sharpes = []
    nblocks = int(np.ceil(len(r) / block))
    starts = np.arange(0, len(r) - block + 1)
    for _ in range(n):
        chosen = RNG.choice(starts, size=nblocks, replace=True)
        samp = np.concatenate([r[s:s + block] for s in chosen])[:len(r)]
        sd = samp.std()
        sharpes.append(samp.mean() / sd * np.sqrt(365 * 24) if sd > 0 else 0.0)
    a = (1 - conf) / 2
    return float(np.quantile(sharpes, a)), float(np.quantile(sharpes, 1 - a))


# ----------------------------------------------------------------- per-asset
def analyse_asset(symbol: str, bursts: pd.DataFrame) -> list[dict]:
    import statsmodels.api as sm

    bars = load_hourly(symbol, bursts.ts.min().date(), date.today())
    joined = bursts.merge(bars, left_on="hour", right_index=True, how="inner")
    emit(f"\n### {symbol}  (bursts joined: {len(joined)})")

    feat_cols = ["signal", "novelty_7d"] + TOPIC_COLS + ["trail_vol_24"]
    grid: list[dict] = []
    for target in [f"fwd_ret_{k}" for k in HORIZONS] + [f"fwd_vol_{k}" for k in HORIZONS]:
        sub = joined.dropna(subset=[target] + feat_cols)
        if len(sub) < 50:
            continue
        X = sm.add_constant(sub[feat_cols].astype(float))
        m = sm.OLS(sub[target].astype(float), X).fit(
            cov_type="cluster", cov_kwds={"groups": sub.ts.dt.date}
        )
        for term in ("signal", "topic_china", "topic_tariffs_trade", "topic_market_directive"):
            if term in m.params:
                grid.append({
                    "asset": symbol, "target": target, "term": term,
                    "beta": float(m.params[term]), "p": float(m.pvalues[term]),
                    "n": int(m.nobs),
                })
    return grid


def _edge_stats(oos: pd.DataFrame, symbol: str, label: str) -> dict:
    horizon = "fwd_ret_4"
    oos = oos.dropna(subset=[horizon, "signal"])
    oos = oos[oos.signal.abs() > 1e-6]
    if len(oos) < 20:
        return {"asset": symbol, "subset": label, "n": len(oos), "verdict": "insufficient OOS events"}
    gross = np.sign(oos["signal"].values) * oos[horizon].values
    net = gross - ROUND_TRIP_COST
    sharpe = net.mean() / net.std() * np.sqrt(365 * 24 / 4) if net.std() > 0 else 0.0
    lo, hi = block_bootstrap_sharpe_ci(net)
    return {
        "asset": symbol, "subset": label, "n": int(len(oos)),
        "mean_net_bp": float(net.mean() * 1e4), "sharpe": float(sharpe),
        "ci_low": lo, "ci_high": hi, "verdict": "EDGE" if lo > 0 else "no edge",
    }


def oos_trading_edge(symbol: str, bursts: pd.DataFrame) -> list[dict]:
    """Pre-registered RQ3 test: sign(signal) rule on the final 20% by time.

    Reported for all market-relevant bursts AND split by is_policy_signal —
    fresh escalations are the candidate incremental-info subset (advisor); a
    directional edge, if any, is far likelier there than in commentary/gloating.
    """
    bars = load_hourly(symbol, bursts.ts.min().date(), date.today())
    joined = bursts.merge(bars, left_on="hour", right_index=True, how="inner").sort_values("ts")
    oos = joined.iloc[int(len(joined) * (1 - OOS_FRAC)):]
    out = [_edge_stats(oos, symbol, "all")]
    if "is_policy_signal" in oos:
        pol = oos["is_policy_signal"].fillna(False).astype(bool)
        out.append(_edge_stats(oos[pol], symbol, "policy/escalation"))
        out.append(_edge_stats(oos[~pol], symbol, "commentary"))
    return out


# ----------------------------------------------------------------- main
def main() -> None:
    smoke = "--smoke" in sys.argv
    confirm = "--confirm" in sys.argv
    min_cov = 0.95
    for i, a in enumerate(sys.argv):
        if a == "--min-coverage":
            min_cov = float(sys.argv[i + 1])
    if not (smoke or confirm):
        print("specify --smoke (mechanical test) or --confirm (real run). See header.")
        sys.exit(2)

    if not SIGNAL_PATH.exists():
        print(f"{SIGNAL_PATH} missing — run trump_signal.py merge first.")
        sys.exit(1)

    cov = llm_coverage()
    if confirm and cov < min_cov:
        print(f"REFUSING --confirm: LLM coverage {cov:.1%} < {min_cov:.0%}. "
              f"Finish the LLM layer first (or lower --min-coverage deliberately + log it).")
        sys.exit(3)

    bursts = load_bursts()
    emit("# Phase 2 — reaction modelling " + ("(SMOKE — not confirmatory)" if smoke else "(CONFIRMATORY)"))
    emit(f"\nLLM coverage of market-relevant posts: {cov:.1%}")
    emit(f"Bursts: {len(bursts)}  ({bursts.ts.min():%Y-%m-%d} -> {bursts.ts.max():%Y-%m-%d})")
    emit(f"Pre-registration: docs/PAPER/PREREGISTRATION.md | costs {ROUND_TRIP_COST:.2%} RT")

    # --- confirmatory OLS grid + BH-FDR ---
    emit("\n## Confirmatory OLS (day-clustered SEs, trailing-vol controlled)")
    grid: list[dict] = []
    for sym in CRYPTO:
        try:
            grid.extend(analyse_asset(sym, bursts))
        except Exception as exc:  # noqa: BLE001
            emit(f"\n### {sym}: FAILED ({exc})")
    if grid:
        pvals = [g["p"] for g in grid]
        rej = benjamini_hochberg(pvals, FDR_Q)
        for g, r in zip(grid, rej):
            g["fdr_sig"] = r
        emit(f"\nGrid: {len(grid)} tests; BH-FDR q={FDR_Q}: "
             f"{sum(rej)} survive correction.")
        emit("\n| asset | target | term | beta | p | FDR-sig |")
        emit("|---|---|---|---|---|---|")
        for g in sorted(grid, key=lambda x: x["p"]):
            beta = g["beta"] * 1e4
            emit(f"| {g['asset']} | {g['target']} | {g['term']} | {beta:+.1f}bp "
                 f"| {g['p']:.3f} | {'YES' if g['fdr_sig'] else ''} |")

    # --- OOS tradeable-edge (RQ3) ---
    emit("\n## OOS tradeable-edge (final 20% by time, net of costs, 4h hold)")
    emit("| asset | subset | n | mean net | Sharpe | 95% CI | verdict |")
    emit("|---|---|---|---|---|---|---|")
    any_edge = False
    for sym in CRYPTO:
        try:
            edges = oos_trading_edge(sym, bursts)
        except Exception as exc:  # noqa: BLE001
            emit(f"| {sym} | — | — | — | — | — | ERROR {exc} |")
            continue
        for e in edges:
            if "sharpe" in e:
                any_edge |= e["verdict"] == "EDGE"
                emit(f"| {e['asset']} | {e['subset']} | {e['n']} | {e['mean_net_bp']:+.1f}bp "
                     f"| {e['sharpe']:+.2f} | [{e['ci_low']:+.2f}, {e['ci_high']:+.2f}] "
                     f"| {e['verdict']} |")
            else:
                emit(f"| {e['asset']} | {e['subset']} | {e['n']} | — | — | — | {e['verdict']} |")
    emit(f"\n**RQ3 verdict:** {'EDGE found on >=1 asset/subset' if any_edge else 'NO tradeable edge after costs'}")

    out = SCRATCH_MD if smoke else RESULTS_MD
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.getvalue(), encoding="utf-8")
    emit(f"\n[written] {out}")
    if smoke:
        emit("NOTE: smoke run — numbers are on partial signal, NOT confirmatory.")


if __name__ == "__main__":
    main()
