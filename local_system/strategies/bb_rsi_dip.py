"""
Bollinger + RSI dip-buy with a fixed % take-profit (bb_rsi_dip).

A deliberately simple, opportunistic, long-only mean-reversion setup on the
DAILY timeframe — the first of the short-term "%-target" strategies.

Entry (long), both must hold (confluence raises the hit rate):
  - daily close < lower Bollinger Band   (price stretched below the band)
  - daily RSI < rsi_buy                  (momentum oversold, default 25)

Exit:
  - price >= entry * (1 + target_pct/100)   — fixed profit target, full exit
  - optional stop_loss_pct (handled by the backtester / paper_trader)
  - optional max_hold_days (bail if the target never comes)

One position at a time: take the target, then hunt the next setup. No shorts,
no pyramiding — "look for opportunity, don't build positions."

Notes:
  - Indicators are computed on COMPLETED daily bars (current bar excluded) to
    avoid lookahead; the entry/target are checked against the live price.
  - The %-target exit is evaluated at bar granularity (close-based). A daily
    strategy on intraday bars exits within one bar of hitting target; true
    intrabar fills are a future fine-resolution refinement.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "bb_period": 20,
    "bb_std": 2.0,
    "rsi_period": 14,
    "rsi_buy": 25.0,       # enter only when daily RSI is below this
    "target_pct": 5.0,     # take-profit target, full exit
    "stop_loss_pct": 0.0,  # 0 = no stop (pure target exit); set >0 to add a stop
    "max_hold_days": 0,    # 0 = hold until target/stop; >0 = time-bail
}


class BbRsiDipStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._entry_price: float = 0.0
        self._entry_time: pd.Timestamp | None = None

    @property
    def name(self) -> str:
        return "bb_rsi_dip"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._entry_price = 0.0
        self._entry_time = None

    @staticmethod
    def _rsi(close: pd.Series, period: int) -> float:
        s = close.iloc[-(period + 1):]
        delta = s.diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        if loss == 0:
            return 100.0
        return float(100 - 100 / (1 + gain / loss))

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        bb_n = int(p["bb_period"])
        rsi_n = int(p["rsi_period"])

        daily = df["close"].resample("1D").last().dropna()
        if len(daily) < max(bb_n, rsi_n) + 2:
            return 0

        prev = daily.iloc[:-1]            # completed bars (no lookahead)
        current = float(daily.iloc[-1])   # live price
        now = daily.index[-1]

        # ── Hold / exit an open position ──────────────────────────────────────
        if self._in_position:
            target = self._entry_price * (1 + p["target_pct"] / 100.0)
            if current >= target:
                self._reset()
                return 0
            max_hold = int(p["max_hold_days"])
            if max_hold and self._entry_time is not None:
                if (now - self._entry_time).days >= max_hold:
                    self._reset()
                    return 0
            return 1  # hold

        # ── Look for a new entry ──────────────────────────────────────────────
        window = prev.iloc[-bb_n:]
        sma = float(window.mean())
        sigma = float(window.std(ddof=1))
        if sigma == 0:
            return 0
        lower = sma - p["bb_std"] * sigma
        rsi = self._rsi(prev, rsi_n)

        if current < lower and rsi < p["rsi_buy"]:
            self._in_position = True
            self._entry_price = current
            self._entry_time = now
            return 1
        return 0

    def _reset(self) -> None:
        self._in_position = False
        self._entry_price = 0.0
        self._entry_time = None

    def notify_stop(self, timestamp: pd.Timestamp) -> None:
        """Called by the backtester / paper_trader on a stop-loss exit."""
        self._reset()

    @classmethod
    def from_yaml(cls, text: str) -> "BbRsiDipStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
