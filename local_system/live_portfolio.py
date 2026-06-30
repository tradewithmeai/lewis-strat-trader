"""
live_portfolio.py — live forward tracking of the cross-sectional momentum BOOK.

The per-asset live board (paper_trader) can't represent a market-neutral
portfolio, so this computes the cross-sectional momentum book's current value
directly from the lake and exposes it as one extra "account" on the board, for
forward validation of the Phase-2 lead (see docs/PAPER/STRATEGY_RESEARCH.md).

Stateless / restart-safe: each refresh recomputes the book's equity from a fixed
inception date using only causal data (the cross_sectional engine rebalances
weekly, no look-ahead), normalised to $1,000 at inception. The book is
risk-parity weighted and vol-targeted to 15% — the gated config.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from local_system.lake_adapter import load_bars, resample_ohlcv
from local_system.live_board import START_CAPITAL
from local_system.portfolio_backtester import (
    apply_vol_target, cross_sectional_backtest, momentum_scores)

NAME = "xsec_momentum"
LOOKBACK_DAYS = 60
VOL_TARGET = 0.15
_CONTEXT_DAYS = 90  # history before inception needed for the 60d lookback at inception


def _universe(lake_root: str) -> list[str]:
    base = Path(lake_root) / "binance"
    if not base.exists():
        return []
    return sorted(p.name for p in base.iterdir() if p.is_dir())


def compute_book(inception_iso: str, lake_root: str) -> dict | None:
    """Current state of the live cross-sectional momentum book, $1,000 at
    inception. Returns an account-shaped dict (or None if data is insufficient)."""
    inception = datetime.fromisoformat(inception_iso)
    if inception.tzinfo is None:
        inception = inception.replace(tzinfo=timezone.utc)
    load_start = inception.date() - timedelta(days=_CONTEXT_DAYS + LOOKBACK_DAYS)

    closes = {}
    for s in _universe(lake_root):
        try:
            df = load_bars(s, load_start, date.today(), backfill_only=True)
            if not df.empty:
                closes[s] = resample_ohlcv(df, "1d")["close"]
        except Exception:
            continue
    prices = pd.DataFrame(closes).dropna(how="all")
    if prices.shape[1] < 6 or len(prices) < LOOKBACK_DAYS + 5:
        return None
    prices = prices.dropna(axis=1, thresh=int(len(prices) * 0.6)).ffill().dropna()
    if prices.shape[1] < 6:
        return None

    scores = momentum_scores(prices, lookback_days=LOOKBACK_DAYS, skip_days=2)
    res = cross_sectional_backtest(
        prices, scores, top_frac=0.25, rebalance_days=7, market_neutral=True,
        inverse_vol=True, vol_lookback=30, cost_bps=10, periods_per_year=365)
    net = apply_vol_target(res["returns"], VOL_TARGET, 30, 365)

    # restrict to the live window (>= inception) and compound from $1,000
    live = net[net.index >= pd.Timestamp(inception)]
    if live.empty:
        equity = START_CAPITAL
        ret_pct = 0.0
    else:
        equity = round(float(START_CAPITAL * (1 + live.fillna(0)).prod()), 2)
        ret_pct = round((equity / START_CAPITAL - 1) * 100, 2)

    return {
        "balance": equity,
        "equity": equity,
        "pnl": round(equity - START_CAPITAL, 2),
        "return_pct": ret_pct,
        "start_ts": inception_iso,
        "side": "market-neutral",
        "in_position": True,
        "trade_count": int(res["n_rebalances"]),
        "win_rate": 0.0,
        "kind": "portfolio",
        "assets": prices.shape[1],
    }
