"""
EMA crossover trend-following strategy.

Entry:  fast EMA crosses above slow EMA (and optionally price > trend EMA)
Exit:   fast EMA crosses below slow EMA OR stop_loss_pct breach
Hold:   while fast EMA remains above slow EMA

Goes with the trend rather than against it — designed for crypto's
strong directional moves rather than mean-reversion.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "fast_period": 9,
    "slow_period": 21,
    "trend_period": 50,  # macro trend filter: only enter when close > EMA(trend_period)
    "use_trend_filter": True,
    "stop_loss_pct": 4.0,
}


class EmaCrossoverStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False

    @property
    def name(self) -> str:
        return "ema_crossover"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False

    def signal(self, df: pd.DataFrame) -> int:
        slow = self._params["slow_period"]
        trend = self._params["trend_period"]
        min_bars = trend + 1 if self._params["use_trend_filter"] else slow + 1
        if len(df) < min_bars:
            return 0

        close = df["close"]
        fast_ema = close.ewm(span=self._params["fast_period"], adjust=False).mean().iloc[-1]
        slow_ema = close.ewm(span=slow, adjust=False).mean().iloc[-1]

        if self._in_position:
            if fast_ema < slow_ema:
                self._in_position = False
                return 0
            return 1  # hold
        else:
            if fast_ema <= slow_ema:
                return 0
            if self._params["use_trend_filter"]:
                trend_ema = close.ewm(span=trend, adjust=False).mean().iloc[-1]
                if close.iloc[-1] < trend_ema:
                    return 0
            self._in_position = True
            return 1

    @classmethod
    def from_yaml(cls, text: str) -> "EmaCrossoverStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
