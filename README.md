# lewis-strat-trader

A self-improving algorithmic trading system built around walk-forward backtesting,
Markov regime detection, and a traffic light strategy promotion framework.

Inspired by Lewis Jackson's YouTube video
[**How To Build A Self-Improving AI Trading Agent (Insanely Cool)**](https://www.youtube.com/results?search_query=lewis+jackson+self+improving+ai+trading+agent).

---

## What it does

- **Loads historical OHLCV data** from a local [crypto-lake-rs](https://github.com/tradewithmeai/crypto-lake-rs)
  parquet store (hive-partitioned, DuckDB-queryable)
- **Walk-forward backtests** strategies: train on 80%, test on 20%, no lookahead

- **Scores strategies** with annualised Sharpe (block-bootstrap 95% CI), max drawdown, win rate
- **Traffic light promotion**: challenger strategies move RED → ORANGE → GREEN over time if they
  consistently beat the active strategy; a human then decides whether to switch
- **Paper trades** the active strategy in real time, logging signals and positions to `state/`

---

## Architecture

```
local_system/
  lake_adapter.py      # DuckDB reader for crypto-lake-rs parquet store
  backtester.py        # Walk-forward engine: fees, slippage, stop-loss, Sharpe CI
  scoring.py           # Composite score + RED/ORANGE/GREEN traffic light state machine
  paper_trader.py      # Live paper trading loop (signals only, no real orders)
  strategies/
    base.py            # Abstract Strategy with stateful _in_position pattern
    markov.py          # Markov regime + RSI entry (active strategy)
    rsi_meanrev.py     # Pure RSI mean-reversion (challenger)
  cli/
    reflect.py         # /reflect-now: run backtest cycle, update traffic lights
    status.py          # /status: print current paper trader + traffic light state
state/
  strategy.yaml        # Active strategy params (edit to tune; human-controlled)
  comparison.json      # Traffic light state for all strategies (written by reflect)
  alerts.jsonl         # Appended when a challenger reaches GREEN
```

---

## Prerequisites

1. Python 3.11+
2. [uv](https://docs.astral.sh/uv/) package manager
3. A running [crypto-lake-rs](https://github.com/tradewithmeai/crypto-lake-rs) instance with
   backfilled BTCUSDT 1m bars

---

## Setup

```powershell
# Clone and install
git clone https://github.com/your-org/lewis-strat-trader
cd lewis-strat-trader
uv sync

# Set the lake path (add to your shell profile to make permanent)
$env:LAKE_ROOT = "D:\path\to\crypto-lake-rs\data\parquet"
```

Copy `.env.example` to `.env` and fill in your `LAKE_ROOT` if you prefer dotenv loading.

---

## How to add a strategy

1. Write `local_system/strategies/my_strategy.py` — implement the `Strategy` base class
2. Add an entry to `local_system/strategies/registry.py` with the class path and optimization grid
3. Run the optimizer to find good parameters:
   ```powershell
   uv run python -m local_system.cli.optimize --strategy my_strategy
   ```
4. Add the strategy name to `state/challengers.yaml`
5. Run a reflect cycle — it picks up the new challenger automatically

That's it. No other files to edit.

---

## Usage

### Run a backtest reflection cycle

```powershell
uv run python -m local_system.cli.reflect                        # last 3 years
uv run python -m local_system.cli.reflect --years 5             # 5 years
uv run python -m local_system.cli.reflect --from 2022-01-01 --to 2024-12-31
```

This will:
1. Load 1m BTCUSDT bars from the lake and resample to 1h
2. Run walk-forward backtest on the active strategy and all challengers in `state/challengers.yaml`
3. Print Sharpe with 95% CI, CAGR, win rate, max drawdown for each
4. Update `state/comparison.json` with new scores and traffic light states

### Optimise a strategy's parameters

```powershell
uv run python -m local_system.cli.optimize --strategy ema_crossover
uv run python -m local_system.cli.optimize --strategy markov_regime --years 3
```

Sweeps the parameter grid defined in `registry.py`, runs all combinations in parallel,
and prints results ranked by Sharpe. Best params are saved to `state/optimize_*.csv`.

### Check current status

```powershell
uv run python -m local_system.cli.status
```

### Tune strategy parameters

Edit `state/strategy.yaml` — changes take effect on the next reflection cycle.

### Add a challenger strategy

1. Create `local_system/strategies/my_strategy.py` inheriting from `Strategy`
2. Add it to `_load_challengers()` in `local_system/cli/reflect.py`

---

## Traffic light rules

| Transition | Condition |
|---|---|
| RED -> ORANGE | Challenger beats active strategy for 7 consecutive days |
| ORANGE -> GREEN | Stays at ORANGE for 14 more days |
| GREEN | Alert written to `state/alerts.jsonl` — human reviews and may switch |

The system never switches strategies automatically. Only you can edit `state/strategy.yaml`.

---

## Costs modelled

| Cost | Value |
|---|---|
| Taker fee | 0.1% per side |
| Slippage | 2 bps per side |
| Round trip | ~0.24% total |

---

## Backtest methodology

- Walk-forward split: first 80% of data for training, last 20% for testing
- No lookahead: strategy only sees bars up to the current bar
- Sharpe annualised from median bar frequency (auto-detected from timestamps)
- Bootstrap CI: 1000 resamples, block size 20 bars, 95% confidence interval
- Stop loss enforced in backtester from `stop_loss_pct` strategy param

---

## Markov regime strategy

Entry condition: Markov bull-regime signal > 0.05 AND RSI(14) < 40  
Exit condition: RSI > 60 OR price drops > 3% from entry

The regime signal is P(Bull | today's state) - P(Bear | today's state), derived from
a 3-state (Bear / Sideways / Bull) first-order Markov chain fitted on 20-day rolling
returns of daily BTCUSDT closes.
