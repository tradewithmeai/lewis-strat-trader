"""
Multi-timeframe Bollinger Band + Relative Volume confluence strategy (mtf_bb_vol).

Uses three timeframes built from the same 1h bar feed:
  1h  — entry trigger   (BB touch + RVOL spike)
  4h  — direction filter (suppress trades opposing the 4h BB signal)
  1D  — trend gate       (veto entries when 1D EMA slope strongly opposes trade)

Entry logic:
  Long:  1h close < lower BB(1h)
         AND 4h close not above upper BB(4h)   — 4h not in short territory
         AND 1D EMA slope > -slope_threshold   — 1D not in downtrend
         AND 1h RVOL >= rvol_threshold          — volume spike confirms move

  Short: 1h close > upper BB(1h)
         AND 4h close not below lower BB(4h)   — 4h not in long territory
         AND 1D EMA slope < +slope_threshold   — 1D not in uptrend
         AND 1h RVOL >= rvol_threshold

Exit logic:
  Long:  1h close >= midband(1h) captured at entry
  Short: 1h close <= midband(1h) captured at entry
  Hard stop: stop_loss_pct from entry price (handled by backtester)

Cooldown:
  After a stop-out, no new entries for cooldown_days.

Order book hook (live use only):
  Call notify_order_book(imbalance) where imbalance = bid_vol / (bid_vol + ask_vol).
  > 0.55 = buy pressure, < 0.45 = sell pressure.
  When not set (backtest), the gate passes neutrally.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "bb_period": 15,
    "bb_std": 2.0,
    "rvol_period": 10,  # rolling window for RVOL mean (1h bars)
    "rvol_threshold": 1.5,  # min RVOL to enter (1.5 = 50% above average)
    "slope_ema_period": 20,  # EMA period for 1D trend slope
    "slope_lookback": 10,  # days over which to measure 1D EMA slope
    "slope_threshold": 0.005,  # normalised slope above which = trending
    "stop_loss_pct": 5.0,
    "cooldown_days": 7,
}


def _bb_position(closes: pd.Series, bb_period: int, bb_std: float) -> tuple[int, float]:
    """
    Compute BB position of the last close relative to the previous bb_period bars.

    Returns (signal, midband):
      signal = +1 if current < lower band, -1 if current > upper band, 0 otherwise
      midband = SMA of the previous bb_period bars (NaN if insufficient data)
    """
    if len(closes) < bb_period + 2:
        return 0, float("nan")

    current = float(closes.iloc[-1])
    window = closes.iloc[-(bb_period + 1) : -1]

    sma = float(window.mean())
    sigma = float(window.std(ddof=1))
    if sigma == 0:
        return 0, sma

    if current < sma - bb_std * sigma:
        return 1, sma
    if current > sma + bb_std * sigma:
        return -1, sma
    return 0, sma


def _ema_slope(closes: pd.Series, ema_period: int, lookback: int) -> float:
    """
    Normalised EMA slope: (ema_now - ema_past) / (ema_past * lookback).
    Returns 0.0 if insufficient data.
    """
    if len(closes) < ema_period + lookback + 1:
        return 0.0
    ema = closes.ewm(span=ema_period, adjust=False).mean()
    ema_now = float(ema.iloc[-1])
    ema_past = float(ema.iloc[-(lookback + 1)])
    if ema_past == 0:
        return 0.0
    return (ema_now - ema_past) / (ema_past * lookback)


def _rvol(vol_series: pd.Series, period: int) -> float:
    """
    Relative volume: current 1h bar volume / mean of previous `period` bars.
    Returns 0.0 if insufficient data.
    """
    if len(vol_series) < period + 2:
        return 0.0
    current = float(vol_series.iloc[-1])
    mean_vol = float(vol_series.iloc[-(period + 1) : -1].mean())
    if mean_vol == 0:
        return 0.0
    return current / mean_vol


class MtfBbVolStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0  # +1 long, -1 short
        self._entry_mid: float = 0.0  # 1h midband at entry — exit target
        self._cooldown_until: pd.Timestamp | None = None
        self._ob_imbalance: float | None = None  # set by notify_order_book()

    @property
    def name(self) -> str:
        return "mtf_bb_vol"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0
        self._entry_mid = 0.0
        self._cooldown_until = None
        self._ob_imbalance = None

    def notify_stop(self, timestamp: pd.Timestamp) -> None:
        """Called by the backtester when a stop-loss fires."""
        self._in_position = False
        self._side = 0
        self._cooldown_until = timestamp + pd.Timedelta(days=int(self._params["cooldown_days"]))

    def notify_order_book(self, imbalance: float) -> None:
        """
        Live use only — inject current order book imbalance before calling signal().
        imbalance = bid_volume / (bid_volume + ask_volume), range [0, 1].
        Not called in backtests; when absent the gate passes neutrally.
        """
        self._ob_imbalance = imbalance

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        bb_n = int(p["bb_period"])
        bb_std = float(p["bb_std"])
        rvol_n = int(p["rvol_period"])
        rvol_thr = float(p["rvol_threshold"])
        slope_ema = int(p["slope_ema_period"])
        slope_lb = int(p["slope_lookback"])
        slope_thr = float(p["slope_threshold"])

        # ── Minimum bars: enough for 1D slope calculation ─────────────────────
        # 1D needs max(bb_n, slope_ema) + slope_lb + 2 daily bars → × 24 1h bars
        # 4h needs (bb_n + 2) × 4 1h bars
        min_bars = max(
            (max(bb_n, slope_ema) + slope_lb + 2) * 24,
            (bb_n + 2) * 4,
            rvol_n + 2,
        )
        if len(df) < min_bars:
            return 0

        # ── Resample ─────────────────────────────────────────────────────────
        closes_1h = df["close"]
        closes_4h = df["close"].resample("4h").last().dropna()
        closes_1d = df["close"].resample("1D").last().dropna()
        vols_1h = df["volume"]

        now = closes_1h.index[-1]

        # ── Exit / hold ───────────────────────────────────────────────────────
        if self._in_position:
            current = float(closes_1h.iloc[-1])
            if self._side == 1:
                if current >= self._entry_mid:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:
                if current <= self._entry_mid:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        # ── Cooldown ──────────────────────────────────────────────────────────
        if self._cooldown_until is not None and now < self._cooldown_until:
            return 0

        # ── Compute signals ───────────────────────────────────────────────────
        sig_1h, mid_1h = _bb_position(closes_1h, bb_n, bb_std)
        if sig_1h == 0:
            return 0  # no 1h trigger — skip further computation

        sig_4h, _ = _bb_position(closes_4h, bb_n, bb_std)
        slope_1d = _ema_slope(closes_1d, slope_ema, slope_lb)
        rvol_now = _rvol(vols_1h, rvol_n)

        # ── Order book gate (live only; neutral when not set) ─────────────────
        ob_long_ok = self._ob_imbalance is None or self._ob_imbalance > 0.45
        ob_short_ok = self._ob_imbalance is None or self._ob_imbalance < 0.55

        # ── Long entry ────────────────────────────────────────────────────────
        if (
            sig_1h == 1
            and sig_4h != -1  # 4h not opposing (neutral or long)
            and slope_1d > -slope_thr  # 1D not in downtrend
            and rvol_now >= rvol_thr
            and ob_long_ok
        ):
            self._in_position = True
            self._side = 1
            self._entry_mid = mid_1h
            return 1

        # ── Short entry ───────────────────────────────────────────────────────
        if (
            sig_1h == -1
            and sig_4h != 1  # 4h not opposing (neutral or short)
            and slope_1d < slope_thr  # 1D not in uptrend
            and rvol_now >= rvol_thr
            and ob_short_ok
        ):
            self._in_position = True
            self._side = -1
            self._entry_mid = mid_1h
            return -1

        return 0

    @classmethod
    def from_yaml(cls, text: str) -> "MtfBbVolStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
