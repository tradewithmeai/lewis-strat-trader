"""
backtester.py — walk-forward backtest engine.

Design:
- No lookahead: strategy only sees bars up to the current bar.
- Costs: 0.1% taker fee each way + 2 bps slippage each way = ~0.24% round trip.
- Block bootstrap Sharpe CI: 1000 resamples, block_size=20 bars, 95% CI.
- Walk-forward split: train on first 80%, test on remaining 20%.

Usage:
    from local_system.backtester import run_backtest, BacktestResult
    from local_system.strategies.markov import MarkovStrategy

    result = run_backtest(df_1m, MarkovStrategy(params))
    print(result.summary())
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

# Round-trip transaction cost (taker fee 0.1% × 2 sides + slippage 2bps × 2)
TAKER_FEE = 0.001
SLIPPAGE_BPS = 0.0002
ROUND_TRIP_COST = (TAKER_FEE + SLIPPAGE_BPS) * 2  # ~0.0024


@dataclass
class Trade:
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    pnl_pct: float  # net of costs
    side: str = "long"


@dataclass
class BacktestResult:
    symbol: str
    strategy_name: str
    start: pd.Timestamp
    end: pd.Timestamp
    n_trades: int
    equity_curve: pd.Series  # indexed by bar timestamp, value = cumulative return
    trades: list[Trade]
    sharpe: float
    sharpe_ci_low: float
    sharpe_ci_high: float
    max_drawdown: float  # as a positive fraction, e.g. 0.15 = 15%
    win_rate: float
    total_return: float  # fractional, e.g. 0.45 = 45%
    cagr: float
    # Mark-to-market (unrealised) drawdown — includes the excursion while a
    # position is OPEN, so hold-to-target strategies can't hide risk behind a
    # realised-only ~0% DD. Holding stats expose capital-lockup / time-in-trade.
    max_drawdown_mtm: float = 0.0
    avg_hold_days: float = 0.0
    max_hold_days: float = 0.0
    open_at_end: bool = False  # a position was never closed by the test end

    def summary(self) -> str:
        years = max((self.end - self.start).days / 365.25, 0.01)
        lines = [
            f"Strategy : {self.strategy_name}",
            f"Symbol   : {self.symbol}",
            f"Period   : {self.start.date()} to {self.end.date()} ({years:.1f}y)",
            f"Trades   : {self.n_trades}",
            f"Win rate : {self.win_rate:.1%}",
            f"Return   : {self.total_return:.1%}  CAGR {self.cagr:.1%}",
            f"Sharpe   : {self.sharpe:.2f}  95% CI [{self.sharpe_ci_low:.2f}, {self.sharpe_ci_high:.2f}]",
            f"Max DD   : {self.max_drawdown:.1%} realised  |  {self.max_drawdown_mtm:.1%} mark-to-market",
            f"Holding  : avg {self.avg_hold_days:.1f}d  max {self.max_hold_days:.1f}d"
            + ("  [STILL OPEN at test end]" if self.open_at_end else ""),
        ]
        return "\n".join(lines)


def _compute_sharpe(returns: np.ndarray, periods_per_year: int = 525_600) -> float:
    """Annualised Sharpe ratio from a series of per-bar returns."""
    if len(returns) < 2:
        return 0.0
    std = returns.std()
    if std == 0:
        return 0.0
    return float(returns.mean() / std * math.sqrt(periods_per_year))


def _block_bootstrap_sharpe(
    returns: np.ndarray,
    n_resamples: int = 1000,
    block_size: int = 20,
    confidence: float = 0.95,
    periods_per_year: int = 525_600,
) -> tuple[float, float]:
    """
    Block bootstrap 95% CI for the Sharpe ratio.
    Returns (ci_low, ci_high).
    """
    n = len(returns)
    if n < block_size * 2:
        s = _compute_sharpe(returns, periods_per_year)
        return s, s

    rng = np.random.default_rng(42)
    sharpes = []
    n_blocks = math.ceil(n / block_size)
    starts = np.arange(0, n - block_size + 1)

    for _ in range(n_resamples):
        chosen = rng.choice(starts, size=n_blocks, replace=True)
        sample = np.concatenate([returns[s : s + block_size] for s in chosen])[:n]
        sharpes.append(_compute_sharpe(sample, periods_per_year))

    alpha = (1 - confidence) / 2
    return float(np.quantile(sharpes, alpha)), float(np.quantile(sharpes, 1 - alpha))


def _max_drawdown(equity: pd.Series) -> float:
    roll_max = equity.cummax()
    drawdown = (equity - roll_max) / roll_max
    return float(-drawdown.min()) if len(drawdown) > 0 else 0.0


def run_backtest(
    df: pd.DataFrame,
    strategy,
    symbol: str = "BTCUSDT",
    train_frac: float = 0.8,
    direction: str = "both",
    entry_filter: "pd.Series | None" = None,
) -> BacktestResult:
    """
    Run a walk-forward backtest on df (1m OHLCV bars).

    strategy must implement:
        strategy.name: str
        strategy.fit(df_train: pd.DataFrame) -> None   (sets internal params)
        strategy.signal(df_window: pd.DataFrame) -> int  (-1 short/flat, 0 flat, 1 long)

    train_frac: fraction of data used for parameter fitting (no trades executed).
    The remaining (1 - train_frac) fraction is the test window where trades happen.

    direction: "both" (default), "long" (suppress all short entries), or
               "short" (suppress all long entries). Used by regime-aware walk-forward
               to apply directional bias per fold — bull folds long-only, bear folds
               short-only, ranging folds unconstrained.

    entry_filter: optional boolean Series aligned to df's index. When True at a
               bar, new entries are suppressed (existing positions are held).
               Intended for risk overlays (e.g. elevated-vol windows after Trump
               posts). Does NOT affect stop-loss exits.
    """
    if df.empty or len(df) < 100:
        raise ValueError(f"Insufficient data: {len(df)} bars")

    split = int(len(df) * train_frac)
    df_train = df.iloc[:split]
    df_test = df.iloc[split:]

    # Fit strategy on training window (no lookahead)
    strategy.fit(df_train)

    # Run signal generation bar-by-bar on the test window
    # To avoid lookahead we pass only rows up to current bar
    closes = df_test["close"].values
    highs = df_test["high"].values
    lows = df_test["low"].values
    times = df_test.index

    position = 0  # 0 = flat, +1 = long, -1 = short
    entry_price = 0.0
    entry_time = None
    trades: list[Trade] = []
    bar_returns = np.zeros(len(df_test))
    open_entry = np.zeros(len(df_test))      # entry price if a position is open at bar i, else 0
    open_side = np.zeros(len(df_test), dtype=int)

    stop_loss_frac = strategy.params.get("stop_loss_pct", 0)
    if stop_loss_frac:
        stop_loss_frac = stop_loss_frac / 100.0

    # Pre-compute entry_filter mask aligned to df_test bars (False = entries OK)
    _filter_arr = None
    if entry_filter is not None:
        _filter_arr = entry_filter.reindex(df_test.index, fill_value=False).values

    full_df = pd.concat([df_train, df_test])

    def _sync_strategy_flat(ts: pd.Timestamp | None = None) -> None:
        """Tell the strategy it's been force-exited (stop loss)."""
        strategy._in_position = False
        if hasattr(strategy, "_side"):
            strategy._side = 0
        if ts is not None and hasattr(strategy, "notify_stop"):
            strategy.notify_stop(ts)

    for i in range(len(df_test)):
        price = closes[i]
        low = lows[i]
        high = highs[i]

        # ── Stop-loss check (before signal, uses bar high/low) ────────────────
        if stop_loss_frac:
            if position == 1:
                stop_price = entry_price * (1 - stop_loss_frac)
                if low <= stop_price:
                    exit_price = stop_price * (1 - SLIPPAGE_BPS)
                    net_ret = (exit_price - entry_price) / entry_price - ROUND_TRIP_COST
                    bar_returns[i] = net_ret
                    trades.append(
                        Trade(entry_time, times[i], entry_price, exit_price, net_ret, "long")
                    )
                    position = 0
                    _sync_strategy_flat(times[i])
                    continue
            elif position == -1:
                stop_price = entry_price * (1 + stop_loss_frac)
                if high >= stop_price:
                    exit_price = stop_price * (1 + SLIPPAGE_BPS)
                    net_ret = (entry_price - exit_price) / entry_price - ROUND_TRIP_COST
                    bar_returns[i] = net_ret
                    trades.append(
                        Trade(entry_time, times[i], entry_price, exit_price, net_ret, "short")
                    )
                    position = 0
                    _sync_strategy_flat(times[i])
                    continue

        lookback_df = full_df.iloc[: split + i + 1]
        sig = strategy.signal(lookback_df)

        # ── Directional bias (regime-aware fold constraint) ───────────────────
        if direction == "long" and sig == -1:
            sig = 0
        elif direction == "short" and sig == 1:
            sig = 0

        # ── Enter ─────────────────────────────────────────────────────────────
        # entry_filter suppresses new entries only (existing positions are held
        # normally — the filter must not override in-position hold signals).
        if position == 0 and _filter_arr is not None and _filter_arr[i]:
            sig = 0
        if position == 0:
            if sig == 1:
                entry_price = price * (1 + SLIPPAGE_BPS)
                entry_time = times[i]
                position = 1
            elif sig == -1:
                entry_price = price * (1 - SLIPPAGE_BPS)
                entry_time = times[i]
                position = -1

        # ── Exit long ─────────────────────────────────────────────────────────
        elif position == 1 and sig != 1:
            exit_price = price * (1 - SLIPPAGE_BPS)
            net_ret = (exit_price - entry_price) / entry_price - ROUND_TRIP_COST
            bar_returns[i] = net_ret
            trades.append(Trade(entry_time, times[i], entry_price, exit_price, net_ret, "long"))
            position = 0

        # ── Exit short ────────────────────────────────────────────────────────
        elif position == -1 and sig != -1:
            exit_price = price * (1 + SLIPPAGE_BPS)
            net_ret = (entry_price - exit_price) / entry_price - ROUND_TRIP_COST
            bar_returns[i] = net_ret
            trades.append(Trade(entry_time, times[i], entry_price, exit_price, net_ret, "short"))
            position = 0

        # Record open-position state at end of bar (for mark-to-market drawdown)
        if position != 0:
            open_entry[i] = entry_price
            open_side[i] = position

    # Build equity curve from realised bar returns
    equity = pd.Series((1 + bar_returns).cumprod(), index=times)

    # Mark-to-market equity: realised equity × the open position's unrealised
    # excursion each bar — surfaces the drawdown a hold-to-target trade racks up
    # while underwater (which the realised curve, flat between trades, hides).
    realised_vals = equity.values
    mtm_vals = realised_vals.copy()
    for i in range(len(df_test)):
        if open_entry[i]:
            unreal = open_side[i] * (closes[i] - open_entry[i]) / open_entry[i]
            mtm_vals[i] = realised_vals[i] * (1 + unreal)
    max_dd_mtm = _max_drawdown(pd.Series(mtm_vals, index=times))

    # Holding times — closed trades plus any position still open at the test end
    hold_days = [(t.exit_time - t.entry_time).total_seconds() / 86400 for t in trades]
    open_at_end = position != 0
    if open_at_end and entry_time is not None:
        hold_days.append((times[-1] - entry_time).total_seconds() / 86400)
    avg_hold = float(np.mean(hold_days)) if hold_days else 0.0
    max_hold = float(np.max(hold_days)) if hold_days else 0.0

    # Infer bar frequency from median timestamp gap; default to 1m if indeterminate
    if len(df_test) >= 2:
        median_gap_sec = df_test.index.to_series().diff().dropna().median().total_seconds()
    else:
        median_gap_sec = 60
    BARS_PER_YEAR = max(1, int(365.25 * 24 * 3600 / median_gap_sec))
    sharpe = _compute_sharpe(bar_returns, BARS_PER_YEAR)
    ci_low, ci_high = _block_bootstrap_sharpe(bar_returns, periods_per_year=BARS_PER_YEAR)
    max_dd = _max_drawdown(equity)

    win_rate = sum(1 for t in trades if t.pnl_pct > 0) / len(trades) if trades else 0.0
    total_return = float(equity.iloc[-1] - 1) if len(equity) > 0 else 0.0
    years = max((df_test.index[-1] - df_test.index[0]).days / 365.25, 0.01)
    cagr = (1 + total_return) ** (1 / years) - 1 if total_return > -1 else -1.0

    return BacktestResult(
        symbol=symbol,
        strategy_name=strategy.name,
        start=df_test.index[0],
        end=df_test.index[-1],
        n_trades=len(trades),
        equity_curve=equity,
        trades=trades,
        sharpe=sharpe,
        sharpe_ci_low=ci_low,
        sharpe_ci_high=ci_high,
        max_drawdown=max_dd,
        win_rate=win_rate,
        total_return=total_return,
        cagr=cagr,
        max_drawdown_mtm=max_dd_mtm,
        avg_hold_days=round(avg_hold, 1),
        max_hold_days=round(max_hold, 1),
        open_at_end=open_at_end,
    )


def run_walk_forward(
    df: pd.DataFrame,
    strategy,
    symbol: str = "BTCUSDT",
    n_splits: int = 5,
) -> list[BacktestResult]:
    """
    Rolling walk-forward: divide df into n_splits folds, each fold uses all
    prior data for training and the new fold for testing. Returns one
    BacktestResult per fold.
    """
    fold_size = len(df) // n_splits
    results = []
    for i in range(1, n_splits):
        test_start = i * fold_size
        test_end = (i + 1) * fold_size
        df_fold = df.iloc[:test_end]
        if len(df_fold) < 200:
            continue
        result = run_backtest(
            df_fold, strategy, symbol=symbol, train_frac=test_start / len(df_fold)
        )
        results.append(result)
    return results
