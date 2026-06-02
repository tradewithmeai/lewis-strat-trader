"""
futures.py — crypto futures / derivatives metrics from Binance USDⓈ-M futures.

Pulls the three derivative signals most often cited as carrying information
beyond spot price, for any USDT-perp symbol (BTCUSDT, SOLUSDT, ...):

  - **Funding rate**  — the periodic (8h) payment between longs and shorts.
    Persistently positive funding = crowded longs (leveraged demand); negative =
    crowded shorts. Mean-reversion and squeeze setups key off funding extremes.
  - **Open interest**  — total notional of open contracts. Rising OI + rising
    price = new money confirming a move; rising OI + falling price = shorts
    building. Falling OI = positions closing (deleveraging).
  - **Long/short account ratio**  — retail positioning (globalLongShortAccount)
    and a smart-money proxy (topLongShortPosition). Crowd extremes often fade.

All three are exposed as *historical* endpoints, so we can backfill rather than
only accruing forward. Caps differ (see each function); we fetch what's allowed.

Binance API notes (no key needed for these public market-data endpoints):
  - Host: https://fapi.binance.com
  - These are low request-weight endpoints; we still space calls politely and
    retry on transient errors. Funding history goes back to listing; the
    data/* endpoints (OI, ratios) are limited to ~30 days (max ~500 points).
  - All timestamps are epoch milliseconds, UTC.

Usage:
    from local_system.signals.futures import collect_futures
    frames = collect_futures(["BTCUSDT", "SOLUSDT"])   # dict[symbol] -> 1h DataFrame
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import pandas as pd
import requests

from local_system.signals import SIGNALS_DIR

BASE = "https://fapi.binance.com"
_TIMEOUT = 15
_RETRIES = 3
_BACKOFF = 2.0  # seconds, doubled each retry
_POLITE_GAP = 0.25  # seconds between calls


def _get(path: str, params: dict | None = None) -> list | dict:
    """GET a Binance futures endpoint with retries + backoff. Returns parsed JSON."""
    url = f"{BASE}{path}"
    last_exc: Exception | None = None
    for attempt in range(_RETRIES):
        try:
            r = requests.get(url, params=params or {}, timeout=_TIMEOUT)
            r.raise_for_status()
            time.sleep(_POLITE_GAP)
            return r.json()
        except Exception as exc:  # noqa: BLE001 — network/HTTP/JSON, all transient-ish
            last_exc = exc
            if attempt < _RETRIES - 1:
                time.sleep(_BACKOFF * (2**attempt))
    raise RuntimeError(f"Binance GET {path} failed after {_RETRIES} tries: {last_exc}")


def _ts_index(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Set a UTC DatetimeIndex from an epoch-ms column (event time)."""
    df = df.copy()
    df.index = pd.to_datetime(df[col].astype("int64"), unit="ms", utc=True)
    df.index.name = "ts"
    return df.drop(columns=[col])


# ── Individual metric fetchers (each returns an event-time-indexed DataFrame) ──


def funding_history(symbol: str, limit: int = 1000) -> pd.DataFrame:
    """Funding-rate history (8-hourly). Deep history available; limit max 1000."""
    raw = _get("/fapi/v1/fundingRate", {"symbol": symbol, "limit": min(limit, 1000)})
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["funding_rate"] = df["fundingRate"].astype(float)
    return _ts_index(df, "fundingTime")[["funding_rate"]]


def open_interest_history(symbol: str, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Open-interest history. NOTE: Binance caps this to ~the last 30 days."""
    raw = _get(
        "/futures/data/openInterestHist",
        {"symbol": symbol, "period": period, "limit": min(limit, 500)},
    )
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["open_interest"] = df["sumOpenInterest"].astype(float)
    df["open_interest_usd"] = df["sumOpenInterestValue"].astype(float)
    return _ts_index(df, "timestamp")[["open_interest", "open_interest_usd"]]


def long_short_account_ratio(symbol: str, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Global retail long/short *account* ratio. Capped ~30 days."""
    raw = _get(
        "/futures/data/globalLongShortAccountRatio",
        {"symbol": symbol, "period": period, "limit": min(limit, 500)},
    )
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["ls_account_ratio"] = df["longShortRatio"].astype(float)
    df["long_account"] = df["longAccount"].astype(float)
    return _ts_index(df, "timestamp")[["ls_account_ratio", "long_account"]]


def top_trader_position_ratio(symbol: str, period: str = "1h", limit: int = 500) -> pd.DataFrame:
    """Top-trader (smart-money proxy) long/short *position* ratio. Capped ~30 days."""
    raw = _get(
        "/futures/data/topLongShortPositionRatio",
        {"symbol": symbol, "period": period, "limit": min(limit, 500)},
    )
    if not raw:
        return pd.DataFrame()
    df = pd.DataFrame(raw)
    df["top_ls_position_ratio"] = df["longShortRatio"].astype(float)
    return _ts_index(df, "timestamp")[["top_ls_position_ratio"]]


def current_snapshot(symbol: str) -> dict:
    """Point-in-time mark/index price, current funding rate, and live OI."""
    prem = _get("/fapi/v1/premiumIndex", {"symbol": symbol})
    oi = _get("/fapi/v1/openInterest", {"symbol": symbol})
    return {
        "ts": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol,
        "mark_price": float(prem["markPrice"]),
        "index_price": float(prem["indexPrice"]),
        "last_funding_rate": float(prem["lastFundingRate"]),
        "next_funding_time": int(prem["nextFundingTime"]),
        "open_interest": float(oi["openInterest"]),
    }


# ── Unified per-symbol frame ─────────────────────────────────────────────────


def build_futures_frame(symbol: str, period: str = "1h") -> pd.DataFrame:
    """Merge funding + OI + positioning into one event-time frame at `period`.

    Funding is 8-hourly; it is forward-filled across the finer grid (the last
    settled rate persists until the next settlement). OI/LS are already at the
    requested period. Returns a DataFrame indexed by UTC ts.
    """
    funding = funding_history(symbol)
    oi = open_interest_history(symbol, period=period)
    lsr = long_short_account_ratio(symbol, period=period)
    top = top_trader_position_ratio(symbol, period=period)

    frames = [f for f in (oi, lsr, top) if not f.empty]
    if not frames:
        # OI/LS history empty (rare) — fall back to funding alone.
        return funding
    merged = pd.concat(frames, axis=1).sort_index()

    if not funding.empty:
        # Reindex funding onto the merged grid, forward-filling between 8h settlements.
        union = merged.index.union(funding.index)
        funding = funding.reindex(union).sort_index().ffill()
        merged = merged.join(funding.reindex(merged.index))

    merged["symbol"] = symbol
    return merged


def collect_futures(
    symbols: list[str] | None = None, period: str = "1h", persist: bool = True
) -> dict[str, pd.DataFrame]:
    """Collect futures metrics for each symbol; optionally persist to state/signals/.

    Each symbol -> a parquet at state/signals/futures_{symbol}.parquet (rebuilt
    from the historical endpoints each run) plus a current snapshot appended to
    state/signals/futures_snapshots.jsonl for forward accrual beyond the API caps.
    """
    import json

    symbols = symbols or ["BTCUSDT", "SOLUSDT"]
    out: dict[str, pd.DataFrame] = {}
    if persist:
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)

    for sym in symbols:
        try:
            frame = build_futures_frame(sym, period=period)
            out[sym] = frame
            if persist and not frame.empty:
                frame.to_parquet(SIGNALS_DIR / f"futures_{sym}.parquet")
            if persist:
                snap = current_snapshot(sym)
                with open(SIGNALS_DIR / "futures_snapshots.jsonl", "a") as fh:
                    fh.write(json.dumps(snap) + "\n")
        except Exception as exc:  # noqa: BLE001 — one bad symbol shouldn't kill the pass
            print(f"[futures] {sym} failed: {exc}", flush=True)
            out[sym] = pd.DataFrame()
    return out


if __name__ == "__main__":
    import sys

    syms = sys.argv[1:] or ["BTCUSDT", "SOLUSDT"]
    print(f"Collecting futures metrics for {syms}...")
    frames = collect_futures(syms)
    for sym, df in frames.items():
        if df.empty:
            print(f"\n{sym}: NO DATA")
            continue
        span_days = (df.index[-1] - df.index[0]).days
        print(f"\n{sym}: {len(df)} rows  {df.index[0]} -> {df.index[-1]}  ({span_days}d)")
        print(f"  columns: {list(df.columns)}")
        print(df.tail(3).to_string())
