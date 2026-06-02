"""
binance_klines.py — hourly OHLCV from the Binance public REST API, cached.

The lake only carries deep history for BTCUSDT; ETH/SOL live capture started
in 2026. For cross-asset event studies we need years of hourly bars, and the
public klines endpoint provides them free (no key, 1000 bars/request).
Same venue as the lake, so the two sources are consistent by construction.

Cache: state/signals/klines_{SYMBOL}_1h.parquet — refreshed incrementally
(only fetches past the cached tail).

Usage:
    uv run python -m local_system.signals.binance_klines ETHUSDT 2022-01-01
"""

from __future__ import annotations

import sys
import time
import urllib.request
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

API = "https://api.binance.com/api/v3/klines"
CACHE_DIR = Path("state/signals")


def _fetch_page(symbol: str, start_ms: int, limit: int = 1000) -> list:
    url = f"{API}?symbol={symbol}&interval=1h&startTime={start_ms}&limit={limit}"
    req = urllib.request.Request(url, headers={"User-Agent": "research/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def load_klines_1h(symbol: str, start: date, end: date | None = None) -> pd.DataFrame:
    """Hourly OHLCV (UTC index), served from cache, fetched incrementally."""
    cache = CACHE_DIR / f"klines_{symbol}_1h.parquet"
    frames: list[pd.DataFrame] = []
    fetch_from = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    if cache.exists():
        cached = pd.read_parquet(cache)
        frames.append(cached)
        if not cached.empty:
            fetch_from = max(fetch_from, cached.index.max().to_pydatetime())

    end_dt = (
        datetime(end.year, end.month, end.day, 23, tzinfo=timezone.utc)
        if end
        else datetime.now(timezone.utc)
    )
    cursor = int(fetch_from.timestamp() * 1000)
    end_ms = int(end_dt.timestamp() * 1000)
    new_rows: list[list] = []
    while cursor < end_ms:
        page = _fetch_page(symbol, cursor)
        if not page:
            break
        new_rows.extend(page)
        cursor = page[-1][0] + 3_600_000
        if len(page) < 1000:
            break
        time.sleep(0.15)  # stay far under rate limits

    if new_rows:
        df = pd.DataFrame(
            new_rows,
            columns=[
                "open_time", "open", "high", "low", "close", "volume",
                "close_time", "qav", "trades", "tbb", "tbq", "ignore",
            ],
        )
        df.index = pd.to_datetime(df.open_time, unit="ms", utc=True)
        df.index.name = "window_start"
        df = df[["open", "high", "low", "close", "volume"]].astype(float)
        frames.append(df)

    if not frames:
        return pd.DataFrame()
    out = pd.concat(frames)
    out = out[~out.index.duplicated(keep="last")].sort_index()
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out.to_parquet(cache)
    lo = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    return out[(out.index >= lo) & (out.index <= end_dt)]


if __name__ == "__main__":
    sym = sys.argv[1] if len(sys.argv) > 1 else "ETHUSDT"
    frm = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2022, 1, 1)
    bars = load_klines_1h(sym, frm)
    print(f"{sym}: {len(bars)} 1h bars {bars.index.min()} -> {bars.index.max()}")
