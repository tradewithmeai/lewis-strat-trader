"""
tradfi_data.py — public-data OHLCV loader for the TradFi research track.

Fetches via yfinance and returns a DataFrame in the SAME shape the crypto
backtester expects — a UTC DatetimeIndex with open/high/low/close/volume/source
columns — so the existing backtester and the whole strategy registry run
UNCHANGED on stocks, indices, FX and commodities.

Research / backtest only: this is an on-demand public-data pull, NOT a collector
or a lake. No 24/7 ingestion, no parquet store (it does cache fetches in-process).

Usage:
    from local_system.tradfi_data import load_yf, COMMODITIES
    df = load_yf("GC=F", "2015-01-01")          # gold, daily, ~10y
    from local_system.backtester import run_backtest
    from local_system.strategies.bb_rsi_dip import BbRsiDipStrategy
    run_backtest(df, BbRsiDipStrategy(), symbol="GC=F")

EXTEND (Darren+Claude): intraday intervals (yfinance caps 1h at ~730d), more
tickers, a thin disk cache if fetch volume grows, alternative free providers.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

# Convenient research baskets (yfinance tickers).
COMMODITIES = {
    "gold": "GC=F", "silver": "SI=F", "wti_oil": "CL=F", "brent_oil": "BZ=F",
    "natgas": "NG=F", "copper": "HG=F", "corn": "ZC=F", "wheat": "ZW=F",
}
INDICES = {
    "sp500": "^GSPC", "nasdaq": "^IXIC", "dow": "^DJI", "russell2k": "^RUT", "vix": "^VIX",
}
FX = {
    "eurusd": "EURUSD=X", "usdjpy": "JPY=X", "gbpusd": "GBPUSD=X", "dxy": "DX-Y.NYB",
}


def load_yf(ticker: str, start, end=None, interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV for `ticker` and normalise to the backtester's format.

    Returns an empty DataFrame on any failure (resilient, like the lake adapter).
    """
    try:
        import yfinance as yf

        df = yf.download(
            ticker,
            start=str(start),
            end=(str(end) if end else None),
            interval=interval,
            auto_adjust=True,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # noqa: BLE001
        print(f"[tradfi_data] fetch failed for {ticker}: {exc}")
        return pd.DataFrame()

    if df is None or len(df) == 0:
        return pd.DataFrame()

    # yfinance may return MultiIndex columns even for a single ticker
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df = df.rename(columns=str.lower)
    keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
    if "close" not in keep:
        return pd.DataFrame()
    df = df[keep].copy()
    df.index = pd.to_datetime(df.index, utc=True)
    df = df[~df.index.duplicated(keep="last")].sort_index()
    df["source"] = "yfinance"
    return df.dropna(subset=["close"])


def buy_hold_return(df: pd.DataFrame) -> float:
    """Total return of simply holding the asset over df's span (fraction)."""
    if df.empty:
        return 0.0
    return float(df["close"].iloc[-1] / df["close"].iloc[0] - 1.0)


if __name__ == "__main__":
    d = load_yf("GC=F", date(2015, 1, 1))
    print(f"gold: {len(d)} daily bars  {d.index.min()} -> {d.index.max()}")
    print(f"buy-and-hold return: {buy_hold_return(d) * 100:+.1f}%")
