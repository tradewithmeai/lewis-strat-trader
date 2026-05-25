"""
Multi-asset OOS test: run mtf_bb_vol (optimised BTC params) on ETH and SOL.

Tests whether the mtf_bb_vol architecture generalises beyond BTC, or whether
the 2024-2026 failure is BTC-regime-specific.

OOS window: 2024-12-01 -> 2026-05-24 (yfinance 1h limit is 730 days from today).
Same best-in-sample params from BTC optimisation on 2021-2024.
"""

import os
from datetime import date

LAKE_ROOT = os.environ.get("LAKE_ROOT", "")
if not LAKE_ROOT:
    raise RuntimeError("LAKE_ROOT not set")

from local_system.lake_adapter import load_bars_yf
from local_system.backtester import run_backtest
from local_system.strategies.mtf_bb_vol import MtfBbVolStrategy

start = date(2024, 12, 1)
end = date(2026, 5, 24)

# Best BTC in-sample params (from optimisation on 2021-05-25 -> 2024-05-25)
best_params = {
    "bb_period": 10,
    "bb_std": 2.5,
    "rvol_period": 10,
    "rvol_threshold": 1.2,
    "slope_threshold": 0.003,
    "stop_loss_pct": 4.0,
    "cooldown_days": 7,
}

symbols = ["ETHUSDT", "SOLUSDT"]

print(f"Multi-asset OOS test ({start} -> {end})  [via yfinance 1h]")
print(f"Params: {best_params}\n")
print(
    f"{'Symbol':<10} {'Sharpe':>8} {'CI Low':>8} {'CI High':>8} {'Tag':>5} "
    f"{'Return':>8} {'CAGR':>7} {'WinRate':>8} {'MaxDD':>7} {'Trades':>7}"
)
print("-" * 88)

for symbol in symbols:
    print(f"Loading {symbol} from yfinance...", flush=True)
    df = load_bars_yf(symbol, start, end, interval="1h")
    if df.empty:
        print(f"{symbol:<10} NO DATA")
        continue
    print(f"  {len(df):,} 1h bars  {df.index[0].date()} -> {df.index[-1].date()}", flush=True)

    strategy = MtfBbVolStrategy(params=best_params)
    result = run_backtest(df, strategy, symbol=symbol)

    ci_tag = "[+]" if result.sharpe_ci_low > 0 else ("[~]" if result.sharpe_ci_high > 0 else "[-]")
    print(
        f"{symbol:<10} {result.sharpe:>8.3f} {result.sharpe_ci_low:>8.2f} {result.sharpe_ci_high:>8.2f} "
        f"{ci_tag:>5} {result.total_return * 100:>7.1f}% {result.cagr * 100:>6.1f}% "
        f"{result.win_rate * 100:>7.1f}% {result.max_drawdown * 100:>6.1f}% {result.n_trades:>7}"
    )

print()
print("BTC reference (same window Dec 2024-May 2026, same params):")
