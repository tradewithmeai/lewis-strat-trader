"""
portfolio_backtester.py — cross-sectional & diversified-trend backtesting.

The single-asset walk-forward engine (backtester.py) cannot express the strategy
classes the literature actually supports: rank a UNIVERSE by a signal, go long
the top / short the bottom, rebalance, run market-neutral. This module adds that.

Two engines, both operating on a wide price panel (DataFrame: index=time,
columns=assets, values=close):

  cross_sectional_backtest(prices, scores, ...)
      At each rebalance, rank assets by `scores`, long the top `top_frac`, short
      the bottom `top_frac` (market-neutral) or long-only. Equal-weight within a
      leg. Holds between rebalances. Used for cross-sectional momentum (score =
      trailing return) and funding carry (score = -funding rate).

  timeseries_trend_backtest(prices, lookback_days, ...)
      Diversified time-series momentum: each asset's position is the sign of its
      own trailing return, equal risk weight, summed across the basket. This is
      the managed-futures / trend-following structure (the edge is the
      diversification, not any single market).

Costs are charged on turnover (per-leg notional traded × cost_bps). Stats are
annualised with `periods_per_year` (365 for daily crypto, 252 for TradFi).

Research only. No look-ahead: scores at rebalance t use only prices up to t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def portfolio_stats(daily_ret: pd.Series, periods_per_year: int = 365) -> dict:
    """Annualised performance stats from a periodic return series."""
    r = daily_ret.dropna()
    if len(r) < 2:
        return {"ann_return": 0.0, "ann_vol": 0.0, "sharpe": 0.0,
                "max_drawdown": 0.0, "total_return": 0.0, "n_periods": len(r)}
    ann_return = float(r.mean() * periods_per_year)
    ann_vol = float(r.std(ddof=1) * np.sqrt(periods_per_year))
    sharpe = ann_return / ann_vol if ann_vol else 0.0
    eq = (1 + r).cumprod()
    max_dd = float(((eq / eq.cummax()) - 1).min())
    return {
        "ann_return": round(ann_return * 100, 2),
        "ann_vol": round(ann_vol * 100, 2),
        "sharpe": round(sharpe, 2),
        "max_drawdown": round(max_dd * 100, 2),
        "total_return": round(float(eq.iloc[-1] - 1) * 100, 2),
        "n_periods": int(len(r)),
    }


def _rebalance_positions(index: pd.DatetimeIndex, rebalance_days: int) -> list[int]:
    """Row positions at which to rebalance (every `rebalance_days` bars)."""
    return list(range(0, len(index), max(1, rebalance_days)))


def _apply_weights(prices: pd.DataFrame, weights: pd.DataFrame,
                   cost_bps: float, periods_per_year: int):
    """Given a (sparse, rebalance-date) weights frame, hold between rebalances,
    charge turnover cost, and return (stats, equity_curve, per-bar returns)."""
    rets = prices.pct_change()
    held = weights.reindex(prices.index).ffill().fillna(0.0)
    turnover = held.diff().abs().sum(axis=1).fillna(held.abs().sum(axis=1))
    gross = (held.shift(1) * rets).sum(axis=1)
    net = gross - turnover * (cost_bps / 1e4)
    net = net.iloc[1:]  # drop first NaN-return bar
    eq = (1 + net.fillna(0)).cumprod()
    return portfolio_stats(net, periods_per_year), eq, net


def cross_sectional_backtest(
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    top_frac: float = 0.25,
    rebalance_days: int = 7,
    cost_bps: float = 10.0,
    market_neutral: bool = True,
    min_assets: int = 4,
    periods_per_year: int = 365,
) -> dict:
    """Rank-and-trade a universe. `scores` (same shape as `prices`, higher = more
    attractive to long) is read only up to each rebalance bar (no look-ahead).

    Returns {stats, equity, n_rebalances}.
    """
    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    n_rebal = 0
    for pos in _rebalance_positions(prices.index, rebalance_days):
        dt = prices.index[pos]
        s = scores.iloc[pos].dropna()
        # only assets with a price at this bar
        s = s[prices.iloc[pos].reindex(s.index).notna()]
        if len(s) < min_assets:
            continue
        n = max(1, int(round(len(s) * top_frac)))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=prices.columns)
        longs = ranked.index[-n:]
        w[longs] = 1.0 / n
        if market_neutral:
            shorts = ranked.index[:n]
            w[shorts] = w[shorts] - 1.0 / n
        weights.loc[dt] = w
        n_rebal += 1
    stats, eq, _ = _apply_weights(prices, weights, cost_bps, periods_per_year)
    return {"stats": stats, "equity": eq, "n_rebalances": n_rebal}


def timeseries_trend_backtest(
    prices: pd.DataFrame,
    lookback_days: int = 90,
    rebalance_days: int = 7,
    cost_bps: float = 10.0,
    periods_per_year: int = 365,
) -> dict:
    """Diversified time-series momentum: per-asset position = sign(trailing
    return over lookback), equal-weighted across the basket. Net long/short
    floats with how many assets are trending up vs down."""
    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    n_rebal = 0
    for pos in _rebalance_positions(prices.index, rebalance_days):
        if pos < lookback_days:
            continue
        dt = prices.index[pos]
        now = prices.iloc[pos]
        past = prices.iloc[pos - lookback_days]
        trail = now / past - 1.0
        sig = np.sign(trail)
        valid = sig.dropna()
        valid = valid[valid != 0]
        if len(valid) < 1:
            continue
        w = pd.Series(0.0, index=prices.columns)
        w[valid.index] = valid.values / len(valid)  # equal weight across active assets
        weights.loc[dt] = w
        n_rebal += 1
    stats, eq, _ = _apply_weights(prices, weights, cost_bps, periods_per_year)
    return {"stats": stats, "equity": eq, "n_rebalances": n_rebal}


# ── score builders ────────────────────────────────────────────────────────────

def momentum_scores(prices: pd.DataFrame, lookback_days: int = 30,
                    skip_days: int = 0) -> pd.DataFrame:
    """Cross-sectional momentum score = trailing return over `lookback_days`,
    optionally skipping the most recent `skip_days` (to dodge short-term
    reversal). Computed causally at every bar."""
    ref = prices.shift(skip_days)
    return ref / ref.shift(lookback_days) - 1.0
