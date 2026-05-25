"""OOS validation: regime_bb with optimised params on held-out 2024-05-25 -> 2026-05-24."""

import os
from datetime import date

LAKE_ROOT = os.environ.get("LAKE_ROOT", "")
if not LAKE_ROOT:
    raise RuntimeError("LAKE_ROOT not set")

from local_system.lake_adapter import load_bars, resample_ohlcv
from local_system.backtester import run_backtest
from local_system.strategies.regime_bb import RegimeBbStrategy

start = date(2024, 5, 25)
end = date(2026, 5, 24)

print(f"Loading held-out bars {start} -> {end}...")
df_1m = load_bars("BTCUSDT", start, end, backfill_only=True)
df = resample_ohlcv(df_1m, "1h")
print(f"Loaded {len(df_1m):,} 1m bars -> {len(df):,} 1h bars\n")

best_params = {
    "bb_period": 20,
    "bb_std": 2.0,
    "adx_period": 14,
    "adx_threshold": 20.0,
    "rvol_threshold": 1.5,
    "slope_threshold": 0.005,
    "stop_loss_pct": 8.0,
    "cooldown_days": 3,
}

strategy = RegimeBbStrategy(params=best_params)
result = run_backtest(df, strategy, symbol="BTCUSDT")

ci_tag = "[+]" if result.sharpe_ci_low > 0 else ("[~]" if result.sharpe_ci_high > 0 else "[-]")

print(f"Out-of-sample result  ({start} -> {end})")
print(
    f"  Sharpe:  {result.sharpe:.3f}  95% CI [{result.sharpe_ci_low:.2f}, {result.sharpe_ci_high:.2f}]  {ci_tag}"
)
print(f"  Return:  {result.total_return * 100:.1f}%  CAGR {result.cagr * 100:.1f}%")
print(f"  Win rate: {result.win_rate * 100:.1f}%")
print(f"  Max DD:  {result.max_drawdown * 100:.1f}%")
print(f"  Trades:  {result.n_trades}")
print()
print("Params used:")
for k, v in best_params.items():
    print(f"  {k}: {v}")
