"""
RSI mean-reversion strategy (challenger).

Entry: RSI(period) < rsi_entry (oversold)
Exit:  RSI > rsi_exit OR stop_loss_pct breach

No regime filter — pure price-action mean reversion.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "rsi_period": 14,
    "rsi_entry": 35,  # oversold on 1h bars
    "rsi_exit": 65,  # overbought on 1h bars
    "stop_loss_pct": 3.0,
}


class RsiMeanRevStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False

    @property
    def name(self) -> str:
        return "rsi_meanrev"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False  # reset state at start of each backtest

    def signal(self, df: pd.DataFrame) -> int:
        period = self._params["rsi_period"]
        if len(df) < period + 1:
            return 0
        rsi = self._compute_rsi(df["close"], period)

        if self._in_position:
            # Hold until explicit exit condition
            if rsi > self._params["rsi_exit"]:
                self._in_position = False
                return 0
            return 1  # hold
        else:
            # Enter when oversold
            if rsi < self._params["rsi_entry"]:
                self._in_position = True
                return 1
            return 0

    def _compute_rsi(self, close: pd.Series, period: int) -> float:
        s = close.iloc[-(period + 1) :]
        delta = s.diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        if loss == 0:
            return 100.0
        return float(100 - 100 / (1 + gain / loss))

    @classmethod
    def from_yaml(cls, text: str) -> "RsiMeanRevStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
