from __future__ import annotations

import json
from datetime import datetime, timezone

import pandas as pd
import requests

from local_system.portfolio_backtester import cash_and_carry_backtest, bootstrap_sharpe_ci
from local_system.signals.news.event_db import load_event_table
from local_system.tradfi_data import load_yf

BASE = "https://fapi.binance.com"
SYMBOLS = ["ADAUSDT", "AVAXUSDT", "BNBUSDT", "BTCUSDT", "DOGEUSDT", "DOTUSDT", "ETHUSDT", "LINKUSDT", "LTCUSDT", "SOLUSDT", "SUIUSDT", "XRPUSDT"]
START = pd.Timestamp("2023-05-03T16:00:00Z")
END = pd.Timestamp.now(tz="UTC").normalize()
LIMIT = 1000

def get(path: str, params: dict | None = None):
    r = requests.get(f"{BASE}{path}", params=params or {}, timeout=20)
    r.raise_for_status()
    return r.json()


def funding_history_paged(symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    rows = []
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    cur = start_ms
    while True:
        batch = get(
            "/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": cur, "endTime": end_ms, "limit": LIMIT},
        )
        if not batch:
            break
        rows.extend(batch)
        last = int(batch[-1]["fundingTime"])
        nxt = last + 1
        if nxt <= cur:
            break
        cur = nxt
        if len(batch) < LIMIT:
            break
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows).drop_duplicates(subset=["fundingTime"]).copy()
    df["funding_rate"] = df["fundingRate"].astype(float)
    df.index = pd.to_datetime(df["fundingTime"].astype("int64"), unit="ms", utc=True)
    df.index.name = "ts"
    return df[["funding_rate"]].sort_index()


frames = []
meta = {}
for sym in SYMBOLS:
    df = funding_history_paged(sym, START, END)
    if df.empty:
        raise SystemExit(f"No funding history for {sym}")
    meta[sym] = {"rows": int(len(df)), "start": str(df.index.min()), "end": str(df.index.max())}
    frames.append(df["funding_rate"].resample("1D").mean().rename(sym).to_frame())

funding_daily = pd.concat(frames, axis=1).sort_index()
funding_daily = funding_daily.loc[(funding_daily.index >= START.normalize()) & (funding_daily.index <= END)]
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
        "symbols": SYMBOLS,
        "common_rows": int(len(funding_daily)),
    },
    "sanity": {
        "event_rows": int(len(load_event_table())),
        "tradfi": {"GC=F": int(len(tradfi_gc)), "^GSPC": int(len(tradfi_spx))},
    },
    "symbol_meta": meta,
    "results": results,
}, indent=2, sort_keys=True))
