"""
_event_study_trump.py — do markets react to Trump's Truth Social posts?

Event study of market-relevant Trump posts (state/signals/trump_events.parquet,
built by local_system.signals.trump_classify) against hourly crypto bars from
the lake and the daily macro panel.

PRE-REGISTERED HYPOTHESES (written before looking at results — see
RESEARCH_NOTE.md for why this discipline exists in this repo):

  H1 (volatility): forward realized volatility over 1h/4h/24h after a
      market-relevant post burst is elevated vs comparable non-event hours.
  H2 (sentiment direction): signed forward return is positively related to
      post sentiment (VADER compound) among market-relevant bursts.
  H3 (topic direction): tariffs/china bursts -> negative forward returns;
      crypto bursts -> positive forward returns.

  Replication bar (a result only "counts" if): it holds on BOTH time halves
  (2022-02..2024-12 pre-inauguration vs 2025-01..now in office — a natural
  power split) AND on at least 2 of 3 assets (BTC/ETH/SOL).

DESIGN
  - Unit of observation: the *burst* (posts <30 min apart), not the post —
    within-burst moves can't be attributed to one post and bursts are the
    natural clustering unit. Burst ts = first market-relevant post's ts.
  - Anchor: t = event ts floored to the hour. Forward return over k hours =
    log(C[t+k] / C[t]) — measured strictly from the event hour's close, so no
    look-ahead (conservative: misses the first minutes of reaction).
    Forward vol over k hours = sqrt(sum of squared hourly log returns
    t+1..t+k).
  - Null: 2000 bootstrap draws of len(events) random bar-hours, sampled to
    match the events' hour-of-day distribution (controls intraday
    seasonality), excluding hours within 24h after any relevant burst.
  - Regression: fwd_ret_k ~ sentiment + engagement + topic dummies, OLS with
    day-clustered standard errors.

Usage:
    $env:LAKE_ROOT = "D:/Documents/11Projects/crypto-lake-rs/data/parquet"
    uv run python _event_study_trump.py [--assets BTCUSDT,ETHUSDT,SOLUSDT]

Writes results to docs/TRUMP_EVENT_STUDY.md (and prints them).
"""

from __future__ import annotations

import sys
from datetime import date
from io import StringIO

import numpy as np
import pandas as pd

EVENTS_PATH = "state/signals/trump_events.parquet"
OUT_MD = "docs/TRUMP_EVENT_STUDY.md"
HORIZONS = [1, 4, 24]  # hours
N_BOOT = 2000
RNG = np.random.default_rng(42)
SPLIT_AT = pd.Timestamp("2025-01-20", tz="UTC")  # inauguration — natural power split
TOPIC_COLS = [
    "topic_tariffs_trade",
    "topic_china",
    "topic_fed_rates",
    "topic_crypto",
    "topic_dollar",
    "topic_energy_oil",
    "topic_markets",
    "topic_taxes_fiscal",
    "topic_geopolitics",
    "topic_market_directive",
    "topic_reassurance",
]

report = StringIO()


def emit(line: str = "") -> None:
    print(line, flush=True)
    report.write(line + "\n")


# ---------------------------------------------------------------- events
def load_bursts() -> pd.DataFrame:
    """Market-relevant, non-noise posts collapsed to burst level."""
    ev = pd.read_parquet(EVENTS_PATH)
    rel = ev[ev.market_relevant & ~ev.is_noise].copy()
    agg = {c: "max" for c in TOPIC_COLS}
    agg |= {"ts": "min", "sentiment": "mean", "engagement": "max"}
    bursts = rel.groupby("burst_id").agg(agg).reset_index()
    bursts["hour"] = bursts.ts.dt.floor("h")
    # one observation per anchor hour (two bursts in one hour merge)
    bursts = bursts.sort_values("ts").drop_duplicates(subset="hour", keep="first")
    return bursts.reset_index(drop=True)


# ---------------------------------------------------------------- bars
def load_hourly(symbol: str, start: date, end: date) -> pd.DataFrame:
    from local_system.signals.live_rollup import load_history_hybrid

    try:
        bars = load_history_hybrid(symbol, start, end)
    except Exception:  # noqa: BLE001 — lake has nothing usable for this symbol
        bars = pd.DataFrame()
    if len(bars) < 10_000:  # lake lacks depth (ETH/SOL live-only) -> Binance API
        from local_system.signals.binance_klines import load_klines_1h

        bars = load_klines_1h(symbol, start, end)
    bars = bars[~bars.index.duplicated(keep="last")].sort_index()
    out = pd.DataFrame(index=bars.index)
    out["logret"] = np.log(bars.close).diff()
    logc = np.log(bars.close)
    for k in HORIZONS:
        out[f"fwd_ret_{k}"] = logc.shift(-k) - logc
        out[f"fwd_vol_{k}"] = np.sqrt(
            (out.logret**2).rolling(k).sum().shift(-k)
        )
    # trailing 24h realized vol through the PREVIOUS bar close — known at event
    # time. The key confound control: vol clusters, and he may post *because*
    # markets are already moving; the null must be matched on this.
    out["trail_vol_24"] = np.sqrt((out.logret**2).rolling(24).sum()).shift(1)
    return out


# ---------------------------------------------------------------- null
def null_distribution(
    bars: pd.DataFrame,
    event_hours: pd.DatetimeIndex,
    stat_cols: list[str],
    match_vol: bool = True,
) -> dict[str, np.ndarray]:
    """Bootstrap null means: random hours matching the events' hour-of-day
    bucket AND trailing-24h-vol quintile (vol clusters; posting timing is
    endogenous — an unmatched null lets "he posts when markets already move"
    masquerade as an event effect). Excludes hours within 24h after any event,
    restricted to the events' own era."""
    tainted = pd.DatetimeIndex(
        np.unique(np.concatenate([(event_hours + pd.Timedelta(hours=h)).values for h in range(25)]))
    )
    pool = bars.dropna(subset=stat_cols + ["trail_vol_24"])
    # null must come from the same era as the events — otherwise regime drift
    # (bull 2023-24 vs chop 2025) masquerades as an event effect
    pool = pool[(pool.index >= event_hours.min()) & (pool.index <= event_hours.max())]
    pool_clean = pool[~pool.index.isin(tainted)]

    # stratum key: 6h-of-day bucket x trailing-vol quintile (bins from the
    # full era pool so event hours land in well-defined quintiles)
    vol_bins = pool["trail_vol_24"].quantile([0, 0.2, 0.4, 0.6, 0.8, 1.0]).values
    vol_bins[0], vol_bins[-1] = -np.inf, np.inf

    def strata(df: pd.DataFrame) -> pd.Series:
        hod = df.index.hour // 6
        volq = pd.cut(df["trail_vol_24"], bins=vol_bins, labels=False)
        return hod * 10 + volq if match_vol else pd.Series(hod, index=df.index)

    pool_strata = strata(pool_clean)
    ev = pool.reindex(event_hours).dropna(subset=["trail_vol_24"])
    ev_counts = strata(ev).value_counts()

    by_stratum = {s: g for s, g in pool_clean.groupby(pool_strata)}
    pairs = [(s, int(n)) for s, n in ev_counts.items() if s in by_stratum]
    draws: dict[str, list[float]] = {c: [] for c in stat_cols}
    for _ in range(N_BOOT):
        sample = pd.concat(
            [by_stratum[s].iloc[RNG.choice(len(by_stratum[s]), size=n, replace=True)]
             for s, n in pairs]
        )
        for c in stat_cols:
            draws[c].append(sample[c].mean())
    return {c: np.array(v) for c, v in draws.items()}


def pct_rank(null: np.ndarray, obs: float) -> float:
    """Two-sided bootstrap p-value of obs against null draws."""
    p_hi = (null >= obs).mean()
    p_lo = (null <= obs).mean()
    return float(min(1.0, 2 * min(p_hi, p_lo)))


# ---------------------------------------------------------------- per-asset study
def study_asset(symbol: str, bursts: pd.DataFrame) -> None:
    start = bursts.ts.min().date()
    end = date.today()
    bars = load_hourly(symbol, start, end)
    emit(f"\n## {symbol}  ({len(bars)} hourly bars {bars.index.min():%Y-%m-%d} -> "
         f"{bars.index.max():%Y-%m-%d})")

    joined = bursts.merge(
        bars, left_on="hour", right_index=True, how="inner"
    )
    emit(f"bursts joined to bars: {len(joined)} / {len(bursts)}")

    stat_cols = [f"fwd_ret_{k}" for k in HORIZONS] + [f"fwd_vol_{k}" for k in HORIZONS]
    splits = {
        "full": joined,
        "pre-2025 (out of office)": joined[joined.ts < SPLIT_AT],
        "2025+ (in office)": joined[joined.ts >= SPLIT_AT],
    }

    for name, sub in splits.items():
        sub = sub.dropna(subset=stat_cols)
        if len(sub) < 30:
            emit(f"\n### {name}: only {len(sub)} events — skipped")
            continue
        null = null_distribution(bars, pd.DatetimeIndex(sub.hour), stat_cols)
        emit(f"\n### {name}  (n={len(sub)} bursts)")
        emit("| stat | event mean | null mean | p (2-sided) |")
        emit("|---|---|---|---|")
        for c in stat_cols:
            obs = sub[c].mean()
            p = pct_rank(null[c], obs)
            flag = " **" if p < 0.05 else ""
            emit(f"| {c} | {obs * 1e4:+.1f} bp | {null[c].mean() * 1e4:+.1f} bp | "
                 f"{p:.3f}{flag} |")

    # discriminating vol test: fwd_vol ~ event + trailing vol + hod, all bars.
    # If the event dummy survives the trailing-vol control, posts carry vol
    # information beyond "he posts when markets are already moving".
    import statsmodels.api as sm

    emit("\n### Vol regression with trailing-vol control (all bars, day-clustered SEs)")
    for era_name, lo, hi in [
        ("full", None, None),
        ("2025+", SPLIT_AT, None),
    ]:
        b = bars.dropna(subset=[f"fwd_vol_{k}" for k in HORIZONS] + ["trail_vol_24"]).copy()
        if lo is not None:
            b = b[b.index >= lo]
        b["event"] = b.index.isin(joined.hour).astype(float)
        hod = pd.get_dummies(b.index.hour // 6, prefix="hod", drop_first=True).set_index(b.index)
        X = sm.add_constant(pd.concat([b[["event", "trail_vol_24"]], hod], axis=1).astype(float))
        terms = []
        for k in HORIZONS:
            m = sm.OLS(b[f"fwd_vol_{k}"].astype(float), X).fit(
                cov_type="cluster", cov_kwds={"groups": b.index.date}
            )
            terms.append(f"vol_{k}h: event b={m.params['event'] * 1e4:+.2f}bp "
                         f"(p={m.pvalues['event']:.3f})")
        emit(f"- {era_name} (n={len(b)}, events={int(b.event.sum())}): " + "; ".join(terms))

    # H2/H3 regression: fwd_ret ~ sentiment + engagement + topics, day-clustered SEs

    emit("\n### Regressions (day-clustered SEs)")
    for k in HORIZONS:
        sub = joined.dropna(subset=[f"fwd_ret_{k}", "sentiment", "engagement"])
        X = sm.add_constant(
            sub[["sentiment", "engagement"] + TOPIC_COLS].astype(float)
        )
        m = sm.OLS(sub[f"fwd_ret_{k}"].astype(float), X).fit(
            cov_type="cluster", cov_kwds={"groups": sub.ts.dt.date}
        )
        sig = m.pvalues[m.pvalues < 0.05].drop("const", errors="ignore")
        emit(f"- fwd_ret_{k}h: R2={m.rsquared:.3f}, n={int(m.nobs)}; "
             + ("significant terms: "
                + ", ".join(f"{t} (b={m.params[t] * 1e4:+.1f}bp, p={m.pvalues[t]:.3f})"
                            for t in sig.index)
                if len(sig) else "no significant terms"))


# ---------------------------------------------------------------- macro daily
def study_macro(bursts: pd.DataFrame) -> None:
    try:
        panel = pd.read_parquet("state/signals/macro_panel.parquet")
    except Exception as exc:  # noqa: BLE001
        emit(f"\n## Macro daily panel: unavailable ({exc})")
        return
    emit(f"\n## Macro daily panel  ({panel.index.min():%Y-%m-%d} -> {panel.index.max():%Y-%m-%d}, "
         f"cols: {list(panel.columns)})")
    if panel.index.tz is None:
        panel.index = panel.index.tz_localize("UTC")
    rets = np.log(panel).diff()

    # daily event variable: count + mean sentiment of relevant bursts, mapped to
    # NEXT day's return (posts often land after the US close — conservative)
    daily = bursts.set_index("ts").resample("1D").agg(
        n=("burst_id", "count"), sent=("sentiment", "mean")
    )
    daily.index = daily.index.tz_convert("UTC") if daily.index.tz else daily.index
    ev_day = (daily.n > 0).astype(float)

    import statsmodels.api as sm

    emit("\n| asset | next-day ret on event days vs not (bp) | sentiment beta (bp, p) |")
    emit("|---|---|---|")
    for col in rets.columns:
        r = rets[col].dropna()
        nxt = r.shift(-1).reindex(daily.index)
        d = pd.DataFrame({"nxt": nxt, "ev": ev_day, "sent": daily.sent.fillna(0)}).dropna()
        if len(d) < 100:
            continue
        diff = (d.loc[d.ev == 1, "nxt"].mean() - d.loc[d.ev == 0, "nxt"].mean()) * 1e4
        m = sm.OLS(d.nxt, sm.add_constant(d[["sent"]])).fit(cov_type="HAC", cov_kwds={"maxlags": 5})
        emit(f"| {col} | {diff:+.1f} | {m.params['sent'] * 1e4:+.1f} (p={m.pvalues['sent']:.3f}) |")


# ---------------------------------------------------------------- main
def main() -> None:
    assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
    for a in sys.argv[1:]:
        if a.startswith("--assets"):
            assets = a.split("=", 1)[1].split(",")

    bursts = load_bursts()
    emit("# Trump Truth Social event study")
    emit(f"\nPinned archive events: see state/signals/trump_archive.meta.json")
    emit(f"Market-relevant non-noise bursts: {len(bursts)} "
         f"({bursts.ts.min():%Y-%m-%d} -> {bursts.ts.max():%Y-%m-%d})")
    emit(f"Horizons: {HORIZONS}h; null draws: {N_BOOT}; split at {SPLIT_AT:%Y-%m-%d} (inauguration)")

    for sym in assets:
        try:
            study_asset(sym, bursts)
        except Exception as exc:  # noqa: BLE001
            emit(f"\n## {sym}: FAILED ({exc})")

    study_macro(bursts)

    from pathlib import Path

    Path(OUT_MD).parent.mkdir(parents=True, exist_ok=True)
    Path(OUT_MD).write_text(report.getvalue(), encoding="utf-8")
    print(f"\n[written] {OUT_MD}")


if __name__ == "__main__":
    main()
