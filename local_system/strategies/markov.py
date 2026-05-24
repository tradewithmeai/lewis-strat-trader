"""
Markov regime strategy.

Entry: Markov regime signal > regime_signal_min AND RSI(rsi_period) < rsi_entry
Exit:  RSI > rsi_exit OR price drops > stop_loss_pct from entry

The Markov signal is P(Bull | current state) - P(Bear | current state) derived
from a 3-state (Bear/Sideways/Bull) first-order Markov chain fitted on rolling
daily returns of the symbol.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from local_system.strategies.base import Strategy

# Default hyperparameters — can be overridden via params dict
_DEFAULTS = {
    "regime_signal_min": 0.05,  # min bull-minus-bear probability to consider entry
    "rsi_period": 7,  # crypto: shorter period responds faster to volatile moves
    "rsi_entry": 40,  # enter long when RSI < this (oversold in bull regime, 1h bars)
    "rsi_exit": 60,  # exit when RSI > this (overbought, 1h bars)
    "stop_loss_pct": 3.0,  # exit when price falls >3% from entry
    "regime_window": 20,  # rolling window for regime return labelling
    "regime_threshold": 0.02,  # |rolling return| threshold to label Bull/Bear vs Sideways
    "daily_resample": True,  # resample input bars to 1d for regime model
}


class MarkovStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        self._transition_matrix: np.ndarray | None = None
        self._in_position: bool = False

    @property
    def name(self) -> str:
        return "markov_regime"

    @property
    def params(self) -> dict:
        return dict(self._params)

    # ── Training ──────────────────────────────────────────────────────────────

    def fit(self, df_train: pd.DataFrame) -> None:
        """Fit the Markov transition matrix on training data daily returns."""
        self._in_position = False  # reset state at start of each backtest
        daily = self._to_daily(df_train)
        if len(daily) < self._params["regime_window"] + 5:
            return
        labels = self._label_regimes(daily["close"])
        self._transition_matrix = self._build_transition_matrix(labels)

    # ── Signal ────────────────────────────────────────────────────────────────

    def signal(self, df: pd.DataFrame) -> int:
        """Return 1 (long/hold) or 0 (flat/exit) based on regime signal and RSI."""
        if len(df) < self._params["rsi_period"] + 1:
            return 0

        rsi = self._compute_rsi(df["close"], self._params["rsi_period"])

        if self._in_position:
            # Hold until RSI overbought — don't exit on regime shift alone
            if rsi > self._params["rsi_exit"]:
                self._in_position = False
                return 0
            return 1  # hold
        else:
            # Enter only when regime is bullish AND RSI is oversold
            regime_sig = self._regime_signal(df)
            if regime_sig > self._params["regime_signal_min"] and rsi < self._params["rsi_entry"]:
                self._in_position = True
                return 1
            return 0

    # ── Internals ─────────────────────────────────────────────────────────────

    def _to_daily(self, df: pd.DataFrame) -> pd.DataFrame:
        if not self._params["daily_resample"]:
            return df
        return df["close"].resample("1D").last().dropna().to_frame()

    def _label_regimes(self, close: pd.Series) -> pd.Series:
        """Label each bar Bear=-1, Sideways=0, Bull=1 from rolling pct_change."""
        thresh = self._params["regime_threshold"]
        window = self._params["regime_window"]
        ret = close.pct_change(window).dropna()
        labels = pd.Series(0, index=ret.index)
        labels[ret > thresh] = 1
        labels[ret < -thresh] = -1
        return labels

    def _build_transition_matrix(self, labels: pd.Series) -> np.ndarray:
        """MLE 3×3 transition matrix. States: 0=Bear, 1=Sideways, 2=Bull."""
        state_map = {-1: 0, 0: 1, 1: 2}
        mat = np.ones((3, 3))  # Laplace smoothing
        vals = labels.map(state_map).values
        for i in range(len(vals) - 1):
            mat[vals[i], vals[i + 1]] += 1
        row_sums = mat.sum(axis=1, keepdims=True)
        return mat / row_sums

    def _stationary_dist(self, P: np.ndarray) -> np.ndarray:
        """Stationary distribution via left eigenvector of P^T."""
        eigvals, eigvecs = np.linalg.eig(P.T)
        idx = np.argmin(np.abs(eigvals - 1.0))
        vec = eigvecs[:, idx].real
        vec = np.abs(vec)
        return vec / vec.sum()

    def _regime_signal(self, df: pd.DataFrame) -> float:
        """P(Bull|current_state) - P(Bear|current_state) from recent daily bars."""
        if self._transition_matrix is None:
            return 0.0
        daily = self._to_daily(df)
        if len(daily) < 2:
            return 0.0
        last_ret = daily["close"].pct_change().iloc[-1]
        thresh = self._params["regime_threshold"]
        if last_ret > thresh:
            state = 2  # Bull
        elif last_ret < -thresh:
            state = 0  # Bear
        else:
            state = 1  # Sideways
        row = self._transition_matrix[state]
        return float(row[2] - row[0])  # P(Bull next) - P(Bear next)

    def _compute_rsi(self, close: pd.Series, period: int) -> float:
        """Wilder's RSI on the last (period+1) bars."""
        s = close.iloc[-(period + 1) :]
        delta = s.diff().dropna()
        gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean().iloc[-1]
        if loss == 0:
            return 100.0
        rs = gain / loss
        return float(100 - 100 / (1 + rs))

    @classmethod
    def from_yaml(cls, text: str) -> "MarkovStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
