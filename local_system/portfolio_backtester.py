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


def subperiod_sharpe(daily_ret: pd.Series, periods_per_year: int = 365) -> dict:
    """Sharpe per calendar year — the sign-consistency check. A real edge holds
    across years; a fluke is carried by one."""
    r = daily_ret.dropna()
    out = {}
    for yr, sub in r.groupby(r.index.year):
        if len(sub) >= 20 and sub.std(ddof=1) > 0:
            out[int(yr)] = round(float(sub.mean() / sub.std(ddof=1) * np.sqrt(periods_per_year)), 2)
    return out


def bootstrap_sharpe_ci(daily_ret: pd.Series, periods_per_year: int = 365,
                        n: int = 1000, block: int = 10) -> tuple[float, float]:
    """Block-bootstrap 95% CI for the annualised Sharpe."""
    r = daily_ret.dropna().values
    if len(r) < block * 3:
        return (0.0, 0.0)
    rng = np.random.default_rng(42)
    import math
    nb = math.ceil(len(r) / block)
    starts = np.arange(0, len(r) - block + 1)
    sh = []
    for _ in range(n):
        idx = rng.choice(starts, size=nb, replace=True)
        samp = np.concatenate([r[s:s + block] for s in idx])[:len(r)]
        sd = samp.std(ddof=1)
        sh.append(samp.mean() / sd * np.sqrt(periods_per_year) if sd else 0.0)
    return (round(float(np.quantile(sh, 0.025)), 2), round(float(np.quantile(sh, 0.975)), 2))


def apply_vol_target(net_ret: pd.Series, target_ann_vol: float = 0.15,
                     lookback: int = 30, periods_per_year: int = 365,
                     cap: float = 3.0) -> pd.Series:
    """Scale a return stream so its trailing realised vol tracks a target —
    the managed-futures risk-control that tames raw cross-sectional vol. The
    scale uses only past vol (shift 1) so there is no look-ahead."""
    realised = net_ret.rolling(lookback).std(ddof=1) * np.sqrt(periods_per_year)
    scale = (target_ann_vol / realised).clip(upper=cap).shift(1).fillna(0.0)
    return net_ret * scale


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


def _inv_vol(rets: pd.DataFrame, pos: int, assets, lookback: int) -> pd.Series:
    """Normalised inverse-trailing-vol weights for `assets` at row `pos`."""
    lo = max(0, pos - lookback)
    vol = rets.iloc[lo:pos][list(assets)].std(ddof=1)
    inv = (1.0 / vol).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    tot = inv.sum()
    return inv / tot if tot > 0 else pd.Series(1.0 / len(assets), index=list(assets))


def cross_sectional_backtest(
    prices: pd.DataFrame,
    scores: pd.DataFrame,
    top_frac: float = 0.25,
    rebalance_days: int = 7,
    cost_bps: float = 10.0,
    market_neutral: bool = True,
    min_assets: int = 4,
    periods_per_year: int = 365,
    inverse_vol: bool = False,
    vol_lookback: int = 30,
) -> dict:
    """Rank-and-trade a universe. `scores` (same shape as `prices`, higher = more
    attractive to long) is read only up to each rebalance bar (no look-ahead).
    inverse_vol=True weights within each leg by 1/trailing-vol (risk parity).

    Returns {stats, equity, returns, n_rebalances}.
    """
    rets = prices.pct_change()
    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    n_rebal = 0
    for pos in _rebalance_positions(prices.index, rebalance_days):
        dt = prices.index[pos]
        s = scores.iloc[pos].dropna()
        s = s[prices.iloc[pos].reindex(s.index).notna()]
        if len(s) < min_assets:
            continue
        n = max(1, int(round(len(s) * top_frac)))
        ranked = s.sort_values()
        w = pd.Series(0.0, index=prices.columns)
        longs = ranked.index[-n:]
        lw = _inv_vol(rets, pos, longs, vol_lookback) if inverse_vol else pd.Series(1.0 / n, index=longs)
        w[longs] = lw
        if market_neutral:
            shorts = ranked.index[:n]
            sw = _inv_vol(rets, pos, shorts, vol_lookback) if inverse_vol else pd.Series(1.0 / n, index=shorts)
            w[shorts] = w[shorts] - sw
        weights.loc[dt] = w
        n_rebal += 1
    stats, eq, net = _apply_weights(prices, weights, cost_bps, periods_per_year)
    return {"stats": stats, "equity": eq, "returns": net, "n_rebalances": n_rebal}


def timeseries_trend_backtest(
    prices: pd.DataFrame,
    lookback_days: int = 90,
    rebalance_days: int = 7,
    cost_bps: float = 10.0,
    periods_per_year: int = 365,
    inverse_vol: bool = True,
    vol_lookback: int = 60,
) -> dict:
    """Diversified time-series momentum: per-asset position = sign(trailing
    return over lookback). inverse_vol=True (default) scales each position by
    1/trailing-vol — the managed-futures risk-parity sizing that makes the
    diversified basket work. Returns {stats, equity, returns, n_rebalances}."""
    rets = prices.pct_change()
    weights = pd.DataFrame(np.nan, index=prices.index, columns=prices.columns)
    n_rebal = 0
    for pos in _rebalance_positions(prices.index, rebalance_days):
        if pos < max(lookback_days, vol_lookback):
            continue
        dt = prices.index[pos]
        trail = prices.iloc[pos] / prices.iloc[pos - lookback_days] - 1.0
        sig = np.sign(trail.dropna())
        sig = sig[sig != 0]
        if len(sig) < 1:
            continue
        w = pd.Series(0.0, index=prices.columns)
        if inverse_vol:
            iv = _inv_vol(rets, pos, sig.index, vol_lookback)
            w[sig.index] = sig.values * iv.reindex(sig.index).values
        else:
            w[sig.index] = sig.values / len(sig)
        weights.loc[dt] = w
        n_rebal += 1
    stats, eq, net = _apply_weights(prices, weights, cost_bps, periods_per_year)
    return {"stats": stats, "equity": eq, "returns": net, "n_rebalances": n_rebal}


# ── score builders ────────────────────────────────────────────────────────────

def momentum_scores(prices: pd.DataFrame, lookback_days: int = 30,
                    skip_days: int = 0) -> pd.DataFrame:
    """Cross-sectional momentum score = trailing return over `lookback_days`,
    optionally skipping the most recent `skip_days` (to dodge short-term
    reversal). Computed causally at every bar."""
    ref = prices.shift(skip_days)
    return ref / ref.shift(lookback_days) - 1.0
