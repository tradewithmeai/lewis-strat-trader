"""
lake_adapter.py — read OHLCV bars from the crypto-lake-rs parquet store.

The lake is partitioned as {exchange}/{symbol}/year=Y/month=MM/day=DD/*.parquet

Set the lake root via environment variable:
    LAKE_ROOT=D:/path/to/crypto-lake-rs/data/parquet

All public functions return a pandas DataFrame indexed by UTC datetime with
columns: open, high, low, close, volume, vwap, source.

Usage:
    from local_system.lake_adapter import load_bars, load_recent_bars
    df = load_bars("BTCUSDT", "2024-01-01", "2024-12-31")   # 1m bars
    df = load_recent_bars("BTCUSDT", n_days=7)               # live bars -> 1m
"""

from __future__ import annotations

import os
import re
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pandas as pd

_lake_root_env = os.environ.get("LAKE_ROOT", "")
if not _lake_root_env:
    raise EnvironmentError(
        "LAKE_ROOT environment variable is not set. "
        "Set it to the path of your crypto-lake-rs parquet store, e.g.:\n"
        "  $env:LAKE_ROOT = 'D:/Documents/11Projects/crypto-lake-rs/data/parquet'"
    )
LAKE_ROOT = Path(_lake_root_env)
BINANCE_REST = "https://api.binance.com/api/v3"


_PARQUET_MAGIC = b"PAR1"


def _valid_parquet(path: Path) -> bool:
    """Return True only if the file has the PAR1 magic at BOTH ends.

    Parquet writes the 4-byte magic as a header *and* a footer. The collector's
    in-progress live flush has the header but a truncated/missing footer, so a
    header-only check passes it and DuckDB then throws 'No magic bytes found at
    end of file'. We must validate the footer too (seek to end-4).
    """
    try:
        if path.stat().st_size < 8:  # need at least header+footer
            return False
        with open(path, "rb") as f:
            if f.read(4) != _PARQUET_MAGIC:
                return False
            f.seek(-4, 2)  # last 4 bytes
            return f.read(4) == _PARQUET_MAGIC
    except OSError:
        return False


# Days with more than this many parquet files are live 1s data (not backfill).
# Live days have ~1140 files (one per minute flush); backfill days have 1-5.
_LIVE_DAY_FILE_THRESHOLD = 50

# On a live day, only the newest few files can be mid-write/partial, so we
# validate just the tail rather than scanning all ~1140 every load.
_LIVE_TAIL_CHECK = 8


def _is_live_day(day_dir: Path) -> bool:
    """Return True if a day partition contains live 1s data (many small files)."""
    count = sum(1 for _ in day_dir.glob("*.parquet"))
    return count > _LIVE_DAY_FILE_THRESHOLD


def _quarantine_corrupt_files(
    symbol: str, start: date, end: date, exchange: str = "binance"
) -> int:
    """
    Scan for parquet files without PAR1 magic bytes and rename them to .bad
    so DuckDB glob patterns skip them.

    Skips live 1s days (>50 files) — those are written atomically by the Rust
    collector so corruption there is rare, and scanning 1000+ files per day is slow.
    """
    quarantined = 0
    d = start
    while d <= end:
        p = (
            LAKE_ROOT
            / exchange
            / symbol
            / f"year={d.year}"
            / f"month={d.month:02d}"
            / f"day={d.day:02d}"
        )
        if p.exists():
            files = sorted(p.glob("*.parquet"))
            # Live days: only the newest files can be mid-write — check the tail.
            # Backfill days: few files, check all.
            if len(files) > _LIVE_DAY_FILE_THRESHOLD:
                files = files[-_LIVE_TAIL_CHECK:]
            for f in files:
                if not _valid_parquet(f):
                    f.rename(f.with_suffix(".parquet.bad"))
                    quarantined += 1
        d += timedelta(days=1)
    return quarantined


def _day_paths(
    symbol: str,
    start: date,
    end: date,
    exchange: str = "binance",
    backfill_only: bool = False,
) -> list[str]:
    """
    Return per-day glob patterns for each day in [start, end] that has parquet files.

    backfill_only=True skips live 1s days (>50 files per partition). Use this for
    backtesting to avoid the expensive enumeration of thousands of small files.
    """
    paths = []
    d = start
    while d <= end:
        p = (
            LAKE_ROOT
            / exchange
            / symbol
            / f"year={d.year}"
            / f"month={d.month:02d}"
            / f"day={d.day:02d}"
        )
        if p.exists():
            if backfill_only and _is_live_day(p):
                d += timedelta(days=1)
                continue
            if list(p.glob("*.parquet")):
                paths.append(str(p).replace("\\", "/") + "/*.parquet")
        d += timedelta(days=1)
    return paths


_CORRUPT_PATH_RE = re.compile(r"'([^']+\.parquet)'")


def _raw_query(paths: list[str], _max_heals: int = 500) -> pd.DataFrame:
    """Execute DuckDB query over per-day glob patterns, self-healing corrupt files.

    The live collector occasionally leaves a partially-written parquet (valid
    header, truncated footer) *anywhere* in a day partition — not just the newest
    file — which DuckDB rejects with 'No magic bytes found at end of file <path>'.
    The tail-only quarantine in _quarantine_corrupt_files catches the common case
    cheaply; this is the safety net for the rest: parse the offending path from
    the error, rename it to .parquet.bad (so the *.parquet glob skips it), retry.
    Capped so a non-quarantine-able error can't loop forever.
    """
    if not paths:
        return pd.DataFrame()
    glob_list = "[" + ",".join(f"'{p}'" for p in paths) + "]"
    sql = f"""
        SELECT window_start, open, high, low, close,
               volume_base AS volume, vwap, source
        FROM read_parquet({glob_list})
        ORDER BY window_start
    """
    df = None
    for _ in range(_max_heals):
        con = duckdb.connect()
        try:
            df = con.execute(sql).df()
            break
        except Exception as exc:  # noqa: BLE001
            msg = str(exc)
            m = _CORRUPT_PATH_RE.search(msg)
            if not m or "magic bytes" not in msg.lower():
                raise
            bad = Path(m.group(1))
            if not (bad.exists() and bad.suffix == ".parquet"):
                raise
            bad.rename(bad.with_suffix(".parquet.bad"))
        finally:
            con.close()
    if df is None:
        raise RuntimeError(f"_raw_query: exceeded {_max_heals} corrupt-file quarantines; aborting")
    if df.empty:
        return df
    df["window_start"] = pd.to_datetime(df["window_start"], utc=True)
    df = df.set_index("window_start")
    return df


def _resample_1m(df: pd.DataFrame) -> pd.DataFrame:
    """Resample a raw (mixed-resolution) DataFrame to 1-minute OHLCV bars."""
    if df.empty:
        return df
    ohlc = df["close"].resample("1min").ohlc()
    ohlc["open"] = df["open"].resample("1min").first()
    ohlc["high"] = df["high"].resample("1min").max()
    ohlc["low"] = df["low"].resample("1min").min()
    ohlc["volume"] = df["volume"].resample("1min").sum()
    vwap_num = (df["close"] * df["volume"]).resample("1min").sum()
    vwap_den = df["volume"].resample("1min").sum().replace(0, float("nan"))
    ohlc["vwap"] = vwap_num / vwap_den
    ohlc["source"] = "resampled_1m"
    return ohlc.dropna(subset=["close"])


def load_bars(
    symbol: str,
    start: str | date,
    end: str | date,
    exchange: str = "binance",
    resample: bool = True,
    backfill_only: bool = False,
) -> pd.DataFrame:
    """
    Load OHLCV 1-minute bars for a symbol between start and end (inclusive, UTC).

    backfill_only=True skips live 1s-bar days (>50 files/partition). Use this
    for backtesting — it avoids enumerating thousands of small live files and
    produces clean uniform 1m data. For paper trading signals use the default
    (backfill_only=False) with load_recent_bars().

    Returns a DataFrame indexed by UTC datetime. Empty if no data exists.
    """
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)

    _quarantine_corrupt_files(symbol, start, end, exchange)
    paths = _day_paths(symbol, start, end, exchange, backfill_only=backfill_only)
    df = _raw_query(paths)
    if df.empty:
        return df

    if resample:
        df = _resample_1m(df)

    return df


def resample_ohlcv(df: pd.DataFrame, tf: str) -> pd.DataFrame:
    """
    Resample a 1m OHLCV DataFrame to a larger timeframe.
    tf: pandas offset string, e.g. "1h", "4h", "1D"
    """
    if df.empty:
        return df
    ohlc = df["close"].resample(tf).ohlc()
    ohlc["open"] = df["open"].resample(tf).first()
    ohlc["high"] = df["high"].resample(tf).max()
    ohlc["low"] = df["low"].resample(tf).min()
    ohlc["volume"] = df["volume"].resample(tf).sum()
    vwap_num = (df["close"] * df["volume"]).resample(tf).sum()
    vwap_den = df["volume"].resample(tf).sum().replace(0, float("nan"))
    ohlc["vwap"] = vwap_num / vwap_den
    ohlc["source"] = df["source"].resample(tf).last()
    return ohlc.dropna(subset=["close"])


def load_recent_bars(
    symbol: str,
    n_days: int = 7,
    exchange: str = "binance",
) -> pd.DataFrame:
    """
    Load the most recent n_days of bars, resampled to 1m.
    Useful for paper trading signal calculation.
    """
    end = date.today()
    start = end - timedelta(days=n_days)
    return load_bars(symbol, start, end, exchange, resample=True)


def available_date_range(symbol: str, exchange: str = "binance") -> tuple[date | None, date | None]:
    """Return (earliest_date, latest_date) for which parquet data exists."""
    sym_root = LAKE_ROOT / exchange / symbol
    if not sym_root.exists():
        return None, None

    all_days: list[date] = []
    for year_dir in sorted(sym_root.glob("year=*")):
        year = int(year_dir.name.split("=")[1])
        for month_dir in sorted(year_dir.glob("month=*")):
            month = int(month_dir.name.split("=")[1])
            for day_dir in sorted(month_dir.glob("day=*")):
                day = int(day_dir.name.split("=")[1])
                if list(day_dir.glob("*.parquet")):
                    all_days.append(date(year, month, day))

    if not all_days:
        return None, None
    return all_days[0], all_days[-1]


def load_bars_yf(
    symbol: str,
    start: str | date,
    end: str | date,
    interval: str = "1h",
) -> pd.DataFrame:
    """
    Load OHLCV bars from Yahoo Finance for backtesting when the local lake
    doesn't have historical data. Returns a DataFrame indexed by UTC datetime
    with columns: open, high, low, close, volume.

    symbol: Binance-style e.g. 'BTCUSDT' → converted to Yahoo 'BTC-USD'
    interval: '1h' or '1d'
    """
    import yfinance as yf

    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)

    # Convert BTCUSDT → BTC-USD
    yf_symbol = symbol.replace("USDT", "-USD").replace("BUSD", "-USD")

    df = yf.download(
        yf_symbol,
        start=start.isoformat(),
        end=end.isoformat(),
        interval=interval,
        auto_adjust=True,
        progress=False,
    )
    if df.empty:
        return pd.DataFrame()

    # Flatten MultiIndex columns if present
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0].lower() for c in df.columns]
    else:
        df.columns = [c.lower() for c in df.columns]

    df = df.rename(columns={"adj close": "close"})
    df.index = pd.to_datetime(df.index, utc=True)
    df.index.name = "window_start"
    df["source"] = "yfinance"
    return df[["open", "high", "low", "close", "volume", "source"]]


def bar_count(symbol: str, start: str | date, end: str | date, exchange: str = "binance") -> int:
    """Return the number of raw bars in the lake for a date range."""
    if isinstance(start, str):
        start = date.fromisoformat(start)
    if isinstance(end, str):
        end = date.fromisoformat(end)
    _quarantine_corrupt_files(symbol, start, end, exchange)
    paths = _day_paths(symbol, start, end, exchange)
    if not paths:
        return 0
    glob_list = "[" + ",".join(f"'{p}'" for p in paths) + "]"
    con = duckdb.connect()
    result = con.execute(f"SELECT COUNT(*) FROM read_parquet({glob_list})").fetchone()
    con.close()
    return int(result[0]) if result else 0
