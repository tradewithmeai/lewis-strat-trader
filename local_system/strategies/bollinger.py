"""
Bollinger Band mean-reversion strategy (bollinger).

Complements the breakout strategy: enters at band extremes expecting reversion
to the mean. A trend filter (EMA slope) suppresses entries in trending markets,
where band touches often continue rather than revert.

Entry logic:
  Long:  daily close < lower BB  (oversold — expect bounce to midband)
  Short: daily close > upper BB  (overbought — expect drop to midband)
  Skipped if |EMA slope| > threshold (trending market → skip mean-reversion)

Exit logic:
  Long:  daily close >= midband at entry  (mean restored)
  Short: daily close <= midband at entry  (mean restored)
  Hard stop: stop_loss_pct from entry price

Regime bias:
  Mild bull (slope > 0): only take long entries
  Mild bear (slope < 0): only take short entries
  Strong trend either way: skip entirely

This strategy is intentionally inactive during trending regimes where the
breakout strategy performs best — the two are designed as complements.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "bb_period": 20,  # SMA and sigma window (days)
    "bb_std": 2.0,  # standard deviations for band width
    "slope_ema_period": 50,  # EMA period for slope calculation
    "slope_lookback": 10,  # days over which to measure EMA slope
    "slope_threshold": 0.003,  # |daily slope fraction| above which = trending
    "stop_loss_pct": 6.0,
}


class BollingerStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0  # +1 long, -1 short
        self._entry_mid: float = 0.0  # midband at entry time — exit target

    @property
    def name(self) -> str:
        return "bollinger"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0
        self._entry_mid = 0.0

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        bb_n = p["bb_period"]
        bb_std = p["bb_std"]
        slope_ema_n = p["slope_ema_period"]
        slope_lb = p["slope_lookback"]
        slope_thr = p["slope_threshold"]

        daily = df["close"].resample("1D").last().dropna()

        min_bars = max(bb_n, slope_ema_n) + slope_lb + 2
        if len(daily) < min_bars:
            return 0

        # Exclude current bar to avoid lookahead
        prev = daily.iloc[:-1]
        current = float(daily.iloc[-1])

        # Bollinger Bands on prev bars
        sma = float(prev.iloc[-bb_n:].mean())
        sigma = float(prev.iloc[-bb_n:].std(ddof=1))
        if sigma == 0:
            return 0
        upper = sma + bb_std * sigma
        lower = sma - bb_std * sigma

        # EMA slope as trend filter
        ema = prev.ewm(span=slope_ema_n, adjust=False).mean()
        ema_now = float(ema.iloc[-1])
        ema_past = float(ema.iloc[-(slope_lb + 1)])
        # Normalise by price so threshold is scale-independent
        slope = (ema_now - ema_past) / (ema_past * slope_lb) if ema_past != 0 else 0.0
        trending = abs(slope) > slope_thr

        # ── Exit / hold existing position ─────────────────────────────────────
        if self._in_position:
            if self._side == 1:  # long — exit at midband
                if current >= self._entry_mid:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:  # short — exit at midband
                if current <= self._entry_mid:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        # ── New entry — skip in strong trending regimes ───────────────────────
        if trending:
            return 0

        if current < lower and slope >= 0:  # below lower BB + mild bull
            self._in_position = True
            self._side = 1
            self._entry_mid = sma
            return 1

        if current > upper and slope <= 0:  # above upper BB + mild bear
            self._in_position = True
            self._side = -1
            self._entry_mid = sma
            return -1

        return 0

    @classmethod
    def from_yaml(cls, text: str) -> "BollingerStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
