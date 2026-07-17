from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from local_system.portfolio_backtester import cash_and_carry_backtest, bootstrap_sharpe_ci
from local_system.signals.futures import funding_history
from local_system.signals.news.event_db import load_event_table
from local_system.tradfi_data import load_yf

symbols = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "SUIUSDT", "XRPUSDT"]
start = pd.Timestamp("2023-05-03T00:00:00Z")
end = pd.Timestamp.now(tz="UTC").normalize()

frames = []
meta = {}
for sym in symbols:
    df = funding_history(sym)
    if df.empty:
        raise SystemExit(f"no funding data for {sym}")
    meta[sym] = {
        "rows": int(len(df)),
        "start": str(df.index.min()),
        "end": str(df.index.max()),
    }
    frames.append(df["funding_rate"].resample("1D").mean().rename(sym).to_frame())

funding_daily = pd.concat(frames, axis=1).sort_index()
funding_daily = funding_daily.loc[(funding_daily.index >= start) & (funding_daily.index <= end)]
funding_daily = funding_daily.dropna(how="all")

results = []
for haircut in [1.0, 0.75, 0.5, 0.35, 0.25]:
    bt = cash_and_carry_backtest(
        funding_daily * haircut,
        signal_lookback=7,
        threshold_bps=0.0,
        cost_bps_per_leg=5.0,
        periods_per_year=365,
    )
    returns = bt["returns"]
    ys = {}
    for yr, g in returns.groupby(returns.index.year):
        if len(g) >= 20 and g.std(ddof=1) > 0:
            ys[int(yr)] = round(float(g.mean() / g.std(ddof=1) * (365 ** 0.5)), 2)
    results.append({
        "haircut": haircut,
        "stats": bt["stats"],
        "ci": list(bootstrap_sharpe_ci(returns, periods_per_year=365, n=1000, block=10)),
        "year_sharpe": ys,
        "avg_active": bt["avg_active"],
    })

tradfi_gc = load_yf("GC=F", "2015-01-01")
tradfi_spx = load_yf("^GSPC", "2015-01-01")

print(json.dumps({
    "window": {
        "start": str(funding_daily.index.min()),
        "end": str(funding_daily.index.max()),
        "symbols": symbols,
        "common_rows": int(len(funding_daily)),
    },
    "sanity": {
        "event_rows": int(len(load_event_table())),
        "tradfi": {"GC=F": int(len(tradfi_gc)), "^GSPC": int(len(tradfi_spx))},
    },
    "symbol_meta": meta,
    "results": results,
}, indent=2, sort_keys=True))
