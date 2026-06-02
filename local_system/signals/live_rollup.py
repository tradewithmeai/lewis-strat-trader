"""
live_rollup.py — turn the lake's noisy live 1s partitions into clean cached 1h bars.

The crypto-lake-rs collector writes live days as ~1140 one-second-flush parquet
files, some of which are corrupt in more than one way: truncated footers ("No
magic bytes...") and corrupt thrift metadata ("TProtocolException: Invalid
data", reported by DuckDB with *no file path*). A single DuckDB glob over a live
day therefore fails unrecoverably, and the file volume makes per-tick reads slow
regardless.

This module fixes that at the right layer: read each live day **once**, file by
file via pyarrow (skipping any file that fails to parse — tolerant of every
corruption mode), aggregate to 1h, and cache the result under
state/lake_rollup/{symbol}/{YYYY-MM-DD}.parquet. The monitor then stitches clean
backfill (the bulk) with these cached rollups (the live tail) for a continuous,
fast, real-time-fresh series.

Cost model: the first rollup of N live days is slow (one-time); cached days are
skipped on subsequent calls, and only the current (still-growing) day is
re-rolled. Incremental and idempotent.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import pandas as pd

from local_system.lake_adapter import (
    LAKE_ROOT,
    _LIVE_DAY_FILE_THRESHOLD,
    resample_ohlcv,
)

_SELECT = (
    "SELECT window_start, open, high, low, close, "
    "volume_base AS volume, vwap, source FROM read_parquet({glob})"
)

ROLLUP_DIR = Path(__file__).parent.parent.parent / "state" / "lake_rollup"


def _day_dir(symbol: str, d: date, exchange: str = "binance") -> Path:
    return (
        LAKE_ROOT
        / exchange
        / symbol
        / f"year={d.year}"
        / f"month={d.month:02d}"
        / f"day={d.day:02d}"
    )


def _read_files(paths: list[str], _skipped: list[int]) -> pd.DataFrame:
    """Read a list of parquet files in ONE DuckDB call, bisecting on failure.

    The common case — all files valid — is a single fast query. When a read
    fails (truncated footer OR corrupt thrift metadata, neither of which DuckDB
    can recover from or always name), we split the list and recurse, isolating
    the corrupt file(s) in O(log n) extra queries and skipping only them. This
    is ~an order of magnitude faster than reading 1140 files individually.
    """
    if not paths:
        return pd.DataFrame()
    glob = "[" + ",".join(f"'{p}'" for p in paths) + "]"
    con = duckdb.connect()
    try:
        return con.execute(_SELECT.format(glob=glob)).df()
    except Exception:  # noqa: BLE001
        if len(paths) == 1:
            _skipped[0] += 1  # this single file is corrupt — skip it
            return pd.DataFrame()
        mid = len(paths) // 2
        left = _read_files(paths[:mid], _skipped)
        right = _read_files(paths[mid:], _skipped)
        return pd.concat([f for f in (left, right) if not f.empty], ignore_index=True)
    finally:
        con.close()


def _robust_read_day(day_dir: Path) -> pd.DataFrame:
    """Read a whole day partition robustly (one DuckDB call, bisect on corruption)."""
    files = [str(p).replace("\\", "/") for p in sorted(day_dir.glob("*.parquet"))]
    skipped = [0]
    raw = _read_files(files, skipped)
    if skipped[0]:
        print(f"[rollup] {day_dir.name}: skipped {skipped[0]} corrupt file(s)", flush=True)
    return raw


def _raw_to_1h(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise a raw read (window_start + OHLCV) to a 1h OHLCV frame."""
    if raw.empty or "window_start" not in raw.columns:
        return pd.DataFrame()
    df = raw.copy()
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df = df.set_index("window_start").sort_index()
    if "source" not in df.columns:
        df["source"] = "live_rollup"
    keep = [
        c for c in ("open", "high", "low", "close", "volume", "vwap", "source") if c in df.columns
    ]
    return resample_ohlcv(df[keep], "1h")


def rollup_live_days(symbol: str, start: date, end: date, exchange: str = "binance") -> int:
    """Roll up live days in [start, end] to cached 1h parquet. Incremental.

    Only days whose partition looks live (> file threshold) are rolled up;
    clean backfill days are read directly by the lake loader. A cached day is
    skipped unless it is today (which is still being written and so is refreshed).
    Returns the number of days (re)rolled.
    """
    out_dir = ROLLUP_DIR / symbol
    out_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).date()

    n = 0
    d = start
    while d <= end:
        cache = out_dir / f"{d.isoformat()}.parquet"
        if cache.exists() and d != today:
            d += timedelta(days=1)
            continue
        day_dir = _day_dir(symbol, d, exchange)
        if not day_dir.exists():
            d += timedelta(days=1)
            continue
        # Only roll up live (many-file) days; backfill days are handled by load_bars.
        file_count = sum(1 for _ in day_dir.glob("*.parquet"))
        if file_count <= _LIVE_DAY_FILE_THRESHOLD:
            d += timedelta(days=1)
            continue
        df1h = _raw_to_1h(_robust_read_day(day_dir))
        if not df1h.empty:
            df1h.to_parquet(cache)
            n += 1
        d += timedelta(days=1)
    return n


def load_rollup(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Concat cached 1h rollups for [start, end]."""
    out_dir = ROLLUP_DIR / symbol
    if not out_dir.exists():
        return pd.DataFrame()
    frames = []
    d = start
    while d <= end:
        cache = out_dir / f"{d.isoformat()}.parquet"
        if cache.exists():
            try:
                frames.append(pd.read_parquet(cache))
            except Exception:  # noqa: BLE001
                pass
        d += timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_index()


def load_history_hybrid(symbol: str, start: date, end: date) -> pd.DataFrame:
    """Clean backfill (bulk) + cached live 1h rollups (tail), stitched to 1h.

    Backfill provides the long clean history; the rollup provides real-time
    freshness past the backfill cutoff. Overlaps are deduped keeping the rollup
    (live) value.
    """
    from local_system.lake_adapter import load_bars

    backfill_1m = load_bars(symbol, start, end, backfill_only=True)
    backfill_1h = resample_ohlcv(backfill_1m, "1h") if not backfill_1m.empty else pd.DataFrame()

    rollup_live_days(symbol, start, end)  # incremental; cheap once cached
    live_1h = load_rollup(symbol, start, end)

    if backfill_1h.empty:
        return live_1h
    if live_1h.empty:
        return backfill_1h
    combined = pd.concat([backfill_1h, live_1h])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    return combined


if __name__ == "__main__":
    import sys
    import time

    sym = sys.argv[1] if len(sys.argv) > 1 else "BTCUSDT"
    # Probe a single known live day first to gauge cost + corruption tolerance.
    probe = date(2026, 5, 27)
    t0 = time.time()
    df = _raw_to_1h(_robust_read_day(_day_dir(sym, probe)))
    print(f"single-day probe {probe}: {time.time() - t0:.1f}s -> {len(df)} 1h bars")
    if not df.empty:
        print(df.tail(2).to_string())
