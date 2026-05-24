"""
Multi-timeframe confluence strategy.

Four-layer entry filter — each layer must pass before entering:

  Layer 1 — Regime gate (daily bars)
    Price > EMA(trend_ema_period) on daily closes.
    Only trade when BTC is in a macro uptrend.

  Layer 2 — Trend confirmation (4h bars)
    MACD(fast, slow, signal) histogram crossed above zero on the last 4h bar.
    Confirms the move is starting, not already exhausted.

  Layer 3 — Entry dip (1h bars)
    RSI(rsi_period) < rsi_entry. Buy the pullback within the trend.

  Layer 4 — VWAP proximity (daily session, from 1h bars)
    Price within vwap_band_pct of the session VWAP.
    Avoids chasing — only enter near institutional value.

Exit:
  MACD histogram turns negative on 4h (trend reversal), OR
  RSI > rsi_exit (overbought), OR
  stop_loss_pct breach (enforced by backtester).

This strategy does not short — long-only, consistent with bull-regime gate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    # Layer 1
    "trend_ema_period": 200,  # daily EMA — macro regime gate
    # Layer 2
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9,
    # Layer 3
    "rsi_period": 7,
    "rsi_entry": 45,  # oversold within trend
    "rsi_exit": 65,  # overbought exit
    # Layer 4
    "vwap_band_pct": 1.5,  # max % above session VWAP to enter
    # Risk
    "stop_loss_pct": 4.0,
}


class MtfConfluenceStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False

    @property
    def name(self) -> str:
        return "mtf_confluence"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        min_bars = p["trend_ema_period"] * 24 + 1  # daily EMA needs this many 1h bars
        if len(df) < min_bars:
            return 0

        close = df["close"]
        current_price = float(close.iloc[-1])

        # ── Exit logic (checked before entry filters) ─────────────────────────
        if self._in_position:
            rsi = self._rsi(close, p["rsi_period"])
            macd_hist = self._macd_histogram(df, "4h")
            if rsi > p["rsi_exit"] or (macd_hist is not None and macd_hist < 0):
                self._in_position = False
                return 0
            return 1  # hold

        # ── Layer 1: daily EMA regime gate ────────────────────────────────────
        daily_close = close.resample("1D").last().dropna()
        if len(daily_close) < p["trend_ema_period"]:
            return 0
        ema_trend = float(daily_close.ewm(span=p["trend_ema_period"], adjust=False).mean().iloc[-1])
        if current_price < ema_trend:
            return 0

        # ── Layer 2: 4h MACD histogram > 0 (trend confirmation) ───────────────
        macd_hist = self._macd_histogram(df, "4h")
        if macd_hist is None or macd_hist <= 0:
            return 0

        # ── Layer 3: 1h RSI dip ───────────────────────────────────────────────
        rsi = self._rsi(close, p["rsi_period"])
        if rsi >= p["rsi_entry"]:
            return 0

        # ── Layer 4: daily session VWAP proximity ─────────────────────────────
        session_vwap = self._session_vwap(df)
        if session_vwap is not None:
            pct_above_vwap = (current_price - session_vwap) / session_vwap * 100
            if pct_above_vwap > p["vwap_band_pct"]:
                return 0

        self._in_position = True
        return 1

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
        """MACD histogram on resampled bars. Returns None if insufficient data."""
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
        """Volume-weighted average price for the current calendar day."""
        if "volume" not in df.columns:
            return None
        today = df.index[-1].date()
        session = df[df.index.date == today]
        if len(session) < 2:
            return None
        vol = session["volume"].replace(0, np.nan).dropna()
        if vol.empty:
            return None
        vwap = float((session["close"] * session["volume"]).sum() / session["volume"].sum())
        return vwap

    @classmethod
    def from_yaml(cls, text: str) -> "MtfConfluenceStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
