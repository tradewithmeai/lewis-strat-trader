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
            f"Max DD   : {self.max_drawdown:.1%}",
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
) -> BacktestResult:
    """
    Run a walk-forward backtest on df (1m OHLCV bars).

    strategy must implement:
        strategy.name: str
        strategy.fit(df_train: pd.DataFrame) -> None   (sets internal params)
        strategy.signal(df_window: pd.DataFrame) -> int  (-1 short/flat, 0 flat, 1 long)

    train_frac: fraction of data used for parameter fitting (no trades executed).
    The remaining (1 - train_frac) fraction is the test window where trades happen.
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

    position = 0  # 0 = flat, 1 = long
    entry_price = 0.0
    entry_time = None
    trades: list[Trade] = []
    bar_returns = np.zeros(len(df_test))

    # Read stop_loss_pct from strategy params if present (as a fraction, e.g. 0.03)
    stop_loss_frac = strategy.params.get("stop_loss_pct", 0)
    if stop_loss_frac:
        stop_loss_frac = stop_loss_frac / 100.0

    # Pre-concatenate train + test into one DataFrame so we can slice efficiently
    # instead of doing O(n²) pd.concat on every bar.
    full_df = pd.concat([df_train, df_test])

    for i in range(len(df_test)):
        price = closes[i]
        low = lows[i]

        # Check stop-loss before consulting strategy signal
        if position == 1 and stop_loss_frac:
            stop_price = entry_price * (1 - stop_loss_frac)
            if low <= stop_price:
                exit_price = stop_price * (1 - SLIPPAGE_BPS)
                gross_ret = (exit_price - entry_price) / entry_price
                net_ret = gross_ret - ROUND_TRIP_COST
                bar_returns[i] = net_ret
                trades.append(
                    Trade(
                        entry_time=entry_time,
                        exit_time=times[i],
                        entry_price=entry_price,
                        exit_price=exit_price,
                        pnl_pct=net_ret,
                    )
                )
                position = 0
                # Sync strategy state so it knows we're flat
                strategy._in_position = False
                continue

        # Slice from start of train data up to and including current test bar
        lookback_df = full_df.iloc[: split + i + 1]

        sig = strategy.signal(lookback_df)

        if position == 0 and sig == 1:
            # Enter long at close with slippage
            entry_price = price * (1 + SLIPPAGE_BPS)
            entry_time = times[i]
            position = 1

        elif position == 1 and sig != 1:
            # Exit long
            exit_price = price * (1 - SLIPPAGE_BPS)
            gross_ret = (exit_price - entry_price) / entry_price
            net_ret = gross_ret - ROUND_TRIP_COST
            bar_returns[i] = net_ret
            trades.append(
                Trade(
                    entry_time=entry_time,
                    exit_time=times[i],
                    entry_price=entry_price,
                    exit_price=exit_price,
                    pnl_pct=net_ret,
                )
            )
            position = 0

    # Build equity curve from bar returns
    equity = pd.Series((1 + bar_returns).cumprod(), index=times)

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
