"""
macro.py — macro + cross-asset data panel for correlation analysis.

Pulls daily closes for the macro series most often linked to crypto risk
appetite, plus the major crypto assets, and aligns them onto one daily calendar
so cross-asset correlations can be computed (see correlations.py).

Series (via yfinance, no key):
  Macro   DXY (dollar index), S&P 500, Nasdaq, Gold, VIX (equity vol), US 10y yield
  Crypto  BTC, ETH, SOL  (USD)

Alignment gotcha (handled here, flagged because it silently corrupts results):
  Crypto trades 24/7; macro (DXY/SPX/Gold/VIX/yields) does not (weekends, market
  holidays). We build a common daily index over the crypto calendar and
  **forward-fill** the macro series across the days they don't trade — i.e. a
  Saturday's crypto move is compared against Friday's last macro print. This is
  the standard convention; the alternative (restrict to common trading days)
  throws away weekend crypto information.

Usage:
    from local_system.signals.macro import build_panel
    panel = build_panel(lookback_days=365)   # daily close DataFrame, columns = friendly names
"""

from __future__ import annotations

import pandas as pd

from local_system.signals import SIGNALS_DIR

# Friendly name -> yfinance ticker. Verified working tickers.
MACRO_TICKERS = {
    "DXY": "DX-Y.NYB",  # US dollar index
    "SPX": "^GSPC",  # S&P 500
    "NDX": "^IXIC",  # Nasdaq Composite
    "GOLD": "GC=F",  # Gold futures
    "VIX": "^VIX",  # equity implied vol
    "US10Y": "^TNX",  # US 10-year yield (x10)
}
CRYPTO_TICKERS = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
}
ALL_TICKERS = {**CRYPTO_TICKERS, **MACRO_TICKERS}


def fetch_closes(tickers: dict[str, str], lookback_days: int = 365) -> pd.DataFrame:
    """Download daily adjusted closes for a {name: ticker} map. Columns = names."""
    import yfinance as yf

    period = f"{max(lookback_days, 7)}d"
    raw = yf.download(
        list(tickers.values()),
        period=period,
        interval="1d",
        auto_adjust=True,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame()
    closes = raw["Close"] if isinstance(raw.columns, pd.MultiIndex) else raw[["Close"]]
    # Map yfinance tickers back to friendly names
    inv = {v: k for k, v in tickers.items()}
    closes = closes.rename(columns=inv)
    closes.index = pd.to_datetime(closes.index, utc=True)
    closes.index.name = "date"
    return closes


def build_panel(lookback_days: int = 365, persist: bool = True) -> pd.DataFrame:
    """Aligned daily-close panel of crypto + macro, macro forward-filled.

    Returns a DataFrame indexed by UTC date with one column per friendly name.
    Crypto defines the calendar (24/7); macro is forward-filled across the days
    it doesn't trade so weekend crypto moves still have a macro reference.
    """
    crypto = fetch_closes(CRYPTO_TICKERS, lookback_days)
    macro = fetch_closes(MACRO_TICKERS, lookback_days)
    if crypto.empty:
        return macro
    if macro.empty:
        return crypto

    # Common daily calendar = crypto's (the superset, incl. weekends).
    cal = crypto.index.union(macro.index).sort_values()
    crypto = crypto.reindex(cal)
    macro = macro.reindex(cal).ffill()  # carry last macro print across non-trading days
    panel = pd.concat([crypto, macro], axis=1)
    # Drop leading rows where crypto itself is NaN (before history starts)
    panel = panel.dropna(how="all")

    if persist and not panel.empty:
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        panel.to_parquet(SIGNALS_DIR / "macro_panel.parquet")
    return panel


if __name__ == "__main__":
    p = build_panel(lookback_days=365)
    if p.empty:
        print("NO DATA")
    else:
        print(
            f"panel: {p.shape[0]} days x {p.shape[1]} series  {p.index[0].date()} -> {p.index[-1].date()}"
        )
        print(f"columns: {list(p.columns)}")
        print("\nlatest values:")
        print(p.tail(1).T.to_string())
