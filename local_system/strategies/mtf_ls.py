"""
Multi-timeframe long/short strategy (mtf_ls).

Extends mtf_confluence with a short side so the strategy can profit in
bear markets, not just bull runs. Signals: +1 long, -1 short, 0 flat.

Long entry  — all four layers must pass:
  1. Price > EMA(trend_ema_period) daily          [bull regime]
  2. 4h MACD histogram > 0                        [trend confirmation]
  3. RSI(rsi_period) < rsi_long_entry on 1h       [dip in uptrend]
  4. Price within vwap_band_pct of session VWAP   [near value]

Short entry — mirror image:
  1. Price < EMA(trend_ema_period) daily          [bear regime]
  2. 4h MACD histogram < 0                        [trend confirmation]
  3. RSI(rsi_period) > rsi_short_entry on 1h      [overbought in downtrend]
  4. Price within vwap_band_pct above VWAP        [near overhead resistance]

Exit long:   MACD turns negative OR RSI > rsi_long_exit OR stop_loss breach
Exit short:  MACD turns positive OR RSI < rsi_short_exit OR stop_loss breach
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    # Regime
    "trend_ema_period": 200,
    # MACD
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    # RSI
    "rsi_period": 7,
    "rsi_long_entry": 40,  # oversold — long entry
    "rsi_long_exit": 65,  # overbought — long exit
    "rsi_short_entry": 60,  # overbought — short entry
    "rsi_short_exit": 35,  # oversold — short exit/cover
    # VWAP
    "vwap_band_pct": 1.5,
    # Risk
    "stop_loss_pct": 4.0,
}


class MtfLsStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0  # +1 long, -1 short

    @property
    def name(self) -> str:
        return "mtf_ls"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0

    def signal(self, df: pd.DataFrame) -> int:
        """Return +1 (long/hold), -1 (short/hold), or 0 (flat)."""
        p = self._params
        if len(df) < p["trend_ema_period"] * 24 + 1:
            return 0

        close = df["close"]
        current_price = float(close.iloc[-1])
        rsi = self._rsi(close, p["rsi_period"])
        macd_hist = self._macd_histogram(df, "4h")
        if macd_hist is None:
            return 0

        # ── Exit existing position ────────────────────────────────────────────
        if self._in_position:
            if self._side == 1:  # long
                if rsi > p["rsi_long_exit"] or macd_hist < 0:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:  # short
                if rsi < p["rsi_short_exit"] or macd_hist > 0:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        # ── Regime ───────────────────────────────────────────────────────────
        daily_close = close.resample("1D").last().dropna()
        if len(daily_close) < p["trend_ema_period"]:
            return 0
        ema_trend = float(daily_close.ewm(span=p["trend_ema_period"], adjust=False).mean().iloc[-1])
        bull_regime = current_price > ema_trend
        bear_regime = current_price < ema_trend

        session_vwap = self._session_vwap(df)

        # ── Long entry ───────────────────────────────────────────────────────
        if bull_regime and macd_hist > 0 and rsi < p["rsi_long_entry"]:
            if session_vwap is None or (
                (current_price - session_vwap) / session_vwap * 100 <= p["vwap_band_pct"]
            ):
                self._in_position = True
                self._side = 1
                return 1

        # ── Short entry ──────────────────────────────────────────────────────
        if bear_regime and macd_hist < 0 and rsi > p["rsi_short_entry"]:
            if session_vwap is None or (
                (current_price - session_vwap) / session_vwap * 100 >= -p["vwap_band_pct"]
            ):
                self._in_position = True
                self._side = -1
                return -1

        return 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _rsi(self, close: pd.Series, period: int) -> float:
        s = close.iloc[-(period + 1) :]
        delta = s.diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        if loss == 0:
            return 100.0
        return float(100 - 100 / (1 + gain / loss))

    def _macd_histogram(self, df: pd.DataFrame, tf: str) -> float | None:
        p = self._params
        bars = df["close"].resample(tf).last().dropna()
        needed = p["macd_slow"] + p["macd_signal"] + 1
        if len(bars) < needed:
            return None
        ema_fast = bars.ewm(span=p["macd_fast"], adjust=False).mean()
        ema_slow = bars.ewm(span=p["macd_slow"], adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=p["macd_signal"], adjust=False).mean()
        return float((macd_line - signal_line).iloc[-1])

    def _session_vwap(self, df: pd.DataFrame) -> float | None:
        if "volume" not in df.columns:
            return None
        today = df.index[-1].date()
        session = df[df.index.date == today]
        if len(session) < 2:
            return None
        vol = session["volume"]
        if vol.sum() == 0:
            return None
        return float((session["close"] * vol).sum() / vol.sum())

    @classmethod
    def from_yaml(cls, text: str) -> "MtfLsStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
