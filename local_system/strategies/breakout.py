"""
Turtle-style breakout strategy (breakout).

Entry logic — enter at strength, not at dips:
  Long:  daily close breaks above the N-day rolling high  [momentum long]
  Short: daily close breaks below the N-day rolling low   [momentum short]

Exit logic:
  Long:  daily close drops below the X-day rolling low    [trend stalled]
  Short: daily close rises above the X-day rolling high   [trend stalled]

An optional ATR-based stop loss adds a hard floor independent of the
channel exit. The backtester enforces this on 1h bars intraday.

Design notes:
- All decisions on daily closes → target 30-60 trades/year
- Win rate is typically 35-45% but avg winner is 3-5x avg loser
- No RSI/MACD filters — pure price action, no curve fitting risk
- entry_period > exit_period forces trend-following, not whipsaw

Classic Turtle params: entry=20, exit=10.
Aggressive params:      entry=10, exit=5.
Conservative params:    entry=55, exit=20.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "entry_period": 40,  # days — optimised on 5y BTC; classic turtle uses 20
    "exit_period": 20,  # days — exit channel, half of entry period
    "stop_loss_pct": 8.0,
}


class BreakoutStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0  # +1 long, -1 short

    @property
    def name(self) -> str:
        return "breakout"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        entry_n = p["entry_period"]
        exit_n = p["exit_period"]

        daily = df["close"].resample("1D").last().dropna()

        if len(daily) < entry_n + 1:
            return 0

        current = float(daily.iloc[-1])

        # Rolling channels (exclude current bar so no lookahead)
        prev = daily.iloc[:-1]
        entry_high = float(prev.iloc[-entry_n:].max())
        entry_low = float(prev.iloc[-entry_n:].min())
        exit_high = float(prev.iloc[-exit_n:].max())
        exit_low = float(prev.iloc[-exit_n:].min())

        # ── Exit / hold existing position ─────────────────────────────────────
        if self._in_position:
            if self._side == 1:  # long — exit if close drops under exit channel low
                if current < exit_low:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:  # short — exit if close rises above exit channel high
                if current > exit_high:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        # ── New entry ─────────────────────────────────────────────────────────
        if current > entry_high:
            self._in_position = True
            self._side = 1
            return 1

        if current < entry_low:
            self._in_position = True
            self._side = -1
            return -1

        return 0

    @classmethod
    def from_yaml(cls, text: str) -> "BreakoutStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
