"""
Strategy registry — single source of truth for all available strategies.

To add a new strategy:
  1. Write the class in local_system/strategies/your_strategy.py
  2. Add an entry to REGISTRY below (class + optimization grid)
  3. Add the name to state/challengers.yaml to include it in reflect runs

The grid is used by optimize.py for parameter search. Fixed params not in the
grid will use the strategy's own _DEFAULTS.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from local_system.strategies.base import Strategy

# ── Registry ──────────────────────────────────────────────────────────────────
# Each entry: strategy_name -> {"cls": callable, "grid": {param: [values]}}

REGISTRY: dict[str, dict] = {
    "markov_regime": {
        "cls": "local_system.strategies.markov.MarkovStrategy",
        "grid": {
            "rsi_period": [7, 9, 14],
            "rsi_entry": [30, 35, 40],
            "rsi_exit": [55, 60, 65],
            "regime_signal_min": [0.03, 0.05, 0.10],
        },
    },
    "rsi_meanrev": {
        "cls": "local_system.strategies.rsi_meanrev.RsiMeanRevStrategy",
        "grid": {
            "rsi_period": [7, 9, 14],
            "rsi_entry": [25, 30, 35],
            "rsi_exit": [60, 65, 70],
            "stop_loss_pct": [2.0, 3.0, 5.0, 8.0],
        },
    },
    "ema_crossover": {
        "cls": "local_system.strategies.ema_crossover.EmaCrossoverStrategy",
        "grid": {
            "fast_period": [7, 9, 12],
            "slow_period": [21, 26, 34],
            "trend_period": [50, 100, 200],
            "stop_loss_pct": [3.0, 5.0, 8.0],
        },
    },
    "mtf_confluence": {
        "cls": "local_system.strategies.mtf_confluence.MtfConfluenceStrategy",
        "grid": {
            "trend_ema_period": [100, 200],
            "macd_fast": [9, 12],
            "macd_slow": [21, 26],
            "rsi_entry": [40, 45, 50],
            "vwap_band_pct": [1.0, 1.5, 2.5],
            "stop_loss_pct": [3.0, 5.0, 8.0],
        },
    },
    "breakout": {
        "cls": "local_system.strategies.breakout.BreakoutStrategy",
        "grid": {
            "entry_period": [10, 20, 40, 55],
            "exit_period": [5, 10, 20],
            "stop_loss_pct": [5.0, 8.0, 12.0],
        },
    },
    "daily_swing": {
        "cls": "local_system.strategies.daily_swing.DailySwingStrategy",
        "grid": {
            "trend_ema_period": [100, 200],
            "macd_fast": [9, 12],
            "macd_slow": [21, 26],
            "rsi_long_entry": [30, 35, 40],
            "rsi_short_entry": [60, 65, 70],
            "rsi_long_exit": [60, 65, 70],
            "rsi_short_exit": [30, 35, 40],
            "stop_loss_pct": [5.0, 8.0, 12.0],
        },
    },
    "mtf_ls": {
        "cls": "local_system.strategies.mtf_ls.MtfLsStrategy",
        "grid": {
            "trend_ema_period": [100, 200],
            "macd_fast": [9, 12],
            "macd_slow": [21, 26],
            "rsi_long_entry": [35, 40, 45],
            "rsi_short_entry": [55, 60, 65],
            "vwap_band_pct": [1.0, 2.0],
            "stop_loss_pct": [3.0, 5.0, 8.0],
        },
    },
}


def get_strategy(name: str, params: dict | None = None) -> "Strategy":
    """Instantiate a strategy by name with optional param overrides."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy '{name}'. Registered: {list(REGISTRY)}")
    entry = REGISTRY[name]
    module_path, class_name = entry["cls"].rsplit(".", 1)
    import importlib

    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls(params=params)


def get_grid(name: str) -> dict[str, list]:
    """Return the default optimization grid for a strategy."""
    if name not in REGISTRY:
        raise ValueError(f"Unknown strategy '{name}'. Registered: {list(REGISTRY)}")
    return dict(REGISTRY[name]["grid"])


def list_strategies() -> list[str]:
    return list(REGISTRY.keys())
