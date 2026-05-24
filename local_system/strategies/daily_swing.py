"""
Daily-bar swing strategy (daily_swing).

All entry/exit decisions are made on daily closes to keep trade count low
(target 20-50 trades/year vs 300-600 for 1h strategies). At 0.24% round-trip
cost, annual drag is ~5-12% — a level that profitable entries can overcome.

Long entry — three conditions on daily bars:
  1. Price > EMA(trend_ema_period)          [bull regime]
  2. MACD histogram > 0                     [momentum confirmed]
  3. RSI(rsi_period) < rsi_long_entry       [dip within uptrend]

Short entry — mirror:
  1. Price < EMA(trend_ema_period)          [bear regime]
  2. MACD histogram < 0                     [momentum confirmed]
  3. RSI(rsi_period) > rsi_short_entry      [spike within downtrend]

Exit long:   MACD turns negative OR RSI > rsi_long_exit
Exit short:  MACD turns positive OR RSI < rsi_short_exit

Stop loss enforced by backtester on the 1h bars (fine-grained intraday stop).
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "trend_ema_period": 200,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    "rsi_period": 7,
    "rsi_long_entry": 35,
    "rsi_long_exit": 65,
    "rsi_short_entry": 65,
    "rsi_short_exit": 35,
    "stop_loss_pct": 5.0,
}


class DailySwingStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0  # +1 long, -1 short

    @property
    def name(self) -> str:
        return "daily_swing"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0

    def signal(self, df: pd.DataFrame) -> int:
        """Return +1 (long/hold), -1 (short/hold), or 0 (flat)."""
        p = self._params

        # Resample 1h input to daily closes
        daily = df["close"].resample("1D").last().dropna()

        needed = p["trend_ema_period"] + p["macd_slow"] + p["macd_signal"] + 2
        if len(daily) < needed:
            return 0

        rsi = self._rsi(daily, p["rsi_period"])
        macd_hist = self._macd_histogram(daily, p["macd_fast"], p["macd_slow"], p["macd_signal"])
        if macd_hist is None:
            return 0

        # ── Hold / exit existing position ─────────────────────────────────────
        if self._in_position:
            if self._side == 1:
                if macd_hist < 0 or rsi > p["rsi_long_exit"]:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:  # short
                if macd_hist > 0 or rsi < p["rsi_short_exit"]:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        # ── Regime ───────────────────────────────────────────────────────────
        ema_trend = float(daily.ewm(span=p["trend_ema_period"], adjust=False).mean().iloc[-1])
        current_price = float(daily.iloc[-1])
        bull = current_price > ema_trend
        bear = current_price < ema_trend

        # ── Long entry ───────────────────────────────────────────────────────
        if bull and macd_hist > 0 and rsi < p["rsi_long_entry"]:
            self._in_position = True
            self._side = 1
            return 1

        # ── Short entry ──────────────────────────────────────────────────────
        if bear and macd_hist < 0 and rsi > p["rsi_short_entry"]:
            self._in_position = True
            self._side = -1
            return -1

        return 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _rsi(self, close: pd.Series, period: int) -> float:
        s = close.iloc[-(period * 3) :]
        delta = s.diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        if loss == 0:
            return 100.0
        return float(100 - 100 / (1 + gain / loss))

    def _macd_histogram(self, daily: pd.Series, fast: int, slow: int, signal: int) -> float | None:
        needed = slow + signal + 1
        if len(daily) < needed:
            return None
        ema_fast = daily.ewm(span=fast, adjust=False).mean()
        ema_slow = daily.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        return float((macd_line - signal_line).iloc[-1])

    @classmethod
    def from_yaml(cls, text: str) -> "DailySwingStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
