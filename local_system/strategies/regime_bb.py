"""
Regime-gated Bollinger Band mean-reversion strategy (regime_bb).

Core insight: BB mean-reversion only works in ranging markets. When ADX is high
(trending), price often keeps going — mean reversion fails. Gate entries with ADX.

Timeframes:
  1h  — entry trigger (BB touch + RVOL spike)
  4h  — ADX regime gate (only enter when 4h ADX < adx_threshold)
  1D  — EMA slope veto (suppress entries opposing daily trend)

Entry logic:
  Long:  1h close < lower BB(1h)
         AND 4h ADX < adx_threshold    — market is ranging, not trending
         AND 1D EMA slope > -slope_threshold
         AND 1h RVOL >= rvol_threshold

  Short: 1h close > upper BB(1h)
         AND 4h ADX < adx_threshold
         AND 1D EMA slope < +slope_threshold
         AND 1h RVOL >= rvol_threshold

Exit: close crosses back through midband (same as mtf_bb_vol).
Hard stop: stop_loss_pct from entry (handled by backtester).
Cooldown: no new entries for cooldown_days after a stop-out.
"""

from __future__ import annotations

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "bb_period": 15,
    "bb_std": 2.0,
    "rvol_period": 10,
    "rvol_threshold": 1.2,
    "adx_period": 14,
    "adx_threshold": 25.0,  # only enter when ADX < this (ranging market)
    "slope_ema_period": 20,
    "slope_lookback": 10,
    "slope_threshold": 0.005,
    "stop_loss_pct": 5.0,
    "cooldown_days": 7,
}


def _bb_position(closes: pd.Series, bb_period: int, bb_std: float) -> tuple[int, float]:
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


def _adx(df: pd.DataFrame, period: int) -> float:
    """Compute ADX for the most recent bar. Returns 50 (neutral/high) if insufficient data."""
    n = period * 3
    if len(df) < n:
        return 50.0

    sub = df[["high", "low", "close"]].iloc[-n:]
    high = sub["high"]
    low = sub["low"]
    close = sub["close"]
    prev_close = close.shift(1)
    prev_high = high.shift(1)
    prev_low = low.shift(1)

    tr = pd.concat([(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(
        axis=1
    )

    up_move = high - prev_high
    down_move = prev_low - low

    dm_pos = up_move.where((up_move > down_move) & (up_move > 0), 0.0)
    dm_neg = down_move.where((down_move > up_move) & (down_move > 0), 0.0)

    atr = tr.ewm(span=period, adjust=False).mean()
    safe_atr = atr.replace(0, float("nan"))
    di_pos = 100 * dm_pos.ewm(span=period, adjust=False).mean() / safe_atr
    di_neg = 100 * dm_neg.ewm(span=period, adjust=False).mean() / safe_atr

    di_sum = (di_pos + di_neg).replace(0, float("nan"))
    dx = 100 * (di_pos - di_neg).abs() / di_sum
    adx_series = dx.ewm(span=period, adjust=False).mean()

    val = float(adx_series.iloc[-1])
    return val if not pd.isna(val) else 50.0


def _ema_slope(closes: pd.Series, ema_period: int, lookback: int) -> float:
    if len(closes) < ema_period + lookback + 1:
        return 0.0
    ema = closes.ewm(span=ema_period, adjust=False).mean()
    ema_now = float(ema.iloc[-1])
    ema_past = float(ema.iloc[-(lookback + 1)])
    if ema_past == 0:
        return 0.0
    return (ema_now - ema_past) / (ema_past * lookback)


def _rvol(vol_series: pd.Series, period: int) -> float:
    if len(vol_series) < period + 2:
        return 0.0
    current = float(vol_series.iloc[-1])
    mean_vol = float(vol_series.iloc[-(period + 1) : -1].mean())
    if mean_vol == 0:
        return 0.0
    return current / mean_vol


class RegimeBbStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._in_position = False
        self._side: int = 0
        self._entry_mid: float = 0.0
        self._cooldown_until: pd.Timestamp | None = None

    @property
    def name(self) -> str:
        return "regime_bb"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        self._in_position = False
        self._side = 0
        self._entry_mid = 0.0
        self._cooldown_until = None

    def notify_stop(self, timestamp: pd.Timestamp) -> None:
        self._in_position = False
        self._side = 0
        self._cooldown_until = timestamp + pd.Timedelta(days=int(self._params["cooldown_days"]))

    def signal(self, df: pd.DataFrame) -> int:
        p = self._params
        bb_n = int(p["bb_period"])
        bb_std = float(p["bb_std"])
        rvol_n = int(p["rvol_period"])
        rvol_thr = float(p["rvol_threshold"])
        adx_n = int(p["adx_period"])
        adx_thr = float(p["adx_threshold"])
        slope_ema = int(p["slope_ema_period"])
        slope_lb = int(p["slope_lookback"])
        slope_thr = float(p["slope_threshold"])

        min_bars = max(
            (max(bb_n, slope_ema) + slope_lb + 2) * 24,
            (adx_n * 3) * 4,
            rvol_n + 2,
        )
        if len(df) < min_bars:
            return 0

        closes_1h = df["close"]
        closes_1d = df["close"].resample("1D").last().dropna()
        vols_1h = df["volume"]

        # Resample OHLCV to 4h for ADX (needs high/low)
        df_4h = (
            df.resample("4h")
            .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
            .dropna(subset=["close"])
        )

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

        # ── BB entry trigger (1h) ─────────────────────────────────────────────
        sig_1h, mid_1h = _bb_position(closes_1h, bb_n, bb_std)
        if sig_1h == 0:
            return 0

        # ── ADX regime gate (4h) — only enter when ranging ───────────────────
        adx_4h = _adx(df_4h, adx_n)
        if adx_4h >= adx_thr:
            return 0  # market is trending, skip mean reversion

        # ── Daily trend veto ──────────────────────────────────────────────────
        slope_1d = _ema_slope(closes_1d, slope_ema, slope_lb)

        # ── RVOL gate ─────────────────────────────────────────────────────────
        rvol_now = _rvol(vols_1h, rvol_n)
        if rvol_now < rvol_thr:
            return 0

        # ── Long entry ────────────────────────────────────────────────────────
        if sig_1h == 1 and slope_1d > -slope_thr:
            self._in_position = True
            self._side = 1
            self._entry_mid = mid_1h
            return 1

        # ── Short entry ───────────────────────────────────────────────────────
        if sig_1h == -1 and slope_1d < slope_thr:
            self._in_position = True
            self._side = -1
            self._entry_mid = mid_1h
            return -1

        return 0

    @classmethod
    def from_yaml(cls, text: str) -> "RegimeBbStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
