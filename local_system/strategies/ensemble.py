"""
Ensemble voting strategy (ensemble).

Aggregates signals from multiple registered strategies and enters only when
a sufficient majority agree on direction. Designed to filter out noise from
any single strategy's false signals.

Signal logic:
  - Instantiates all strategies listed in `members` param (default: all registry entries)
  - On each bar: collects each member's signal (+1, 0, -1)
  - Counts long votes (+1) and short votes (-1)
  - Enters long  if long_votes  >= vote_threshold
  - Enters short if short_votes >= vote_threshold
  - Exits when the count in the current direction drops below exit_threshold

Position state:
  The ensemble tracks its own position. Member strategies each run their own
  internal state independently (they track their own trades and exits). The
  ensemble's position is gated on the vote count, not individual strategy exits.

Exit logic:
  - Long:  exit when fewer than exit_threshold members return +1
  - Short: exit when fewer than exit_threshold members return -1

Hard stop: stop_loss_pct from entry (handled by backtester).
"""

from __future__ import annotations

import importlib

import pandas as pd

from local_system.strategies.base import Strategy

_DEFAULTS = {
    "vote_threshold": 5,  # minimum members agreeing to enter (out of N)
    "exit_threshold": 3,  # minimum members still agreeing to stay in
    "stop_loss_pct": 5.0,
}

# Default member list — all strategies except ensemble itself and markov (slow)
_DEFAULT_MEMBERS = [
    "rsi_meanrev",
    "ema_crossover",
    "mtf_confluence",
    "breakout",
    "daily_swing",
    "mtf_ls",
    "bollinger",
    "mtf_bb_vol",
]


def _load_strategy(name: str) -> Strategy:
    from local_system.strategies.registry import REGISTRY

    entry = REGISTRY[name]
    module_path, class_name = entry["cls"].rsplit(".", 1)
    module = importlib.import_module(module_path)
    cls = getattr(module, class_name)
    return cls()


class EnsembleStrategy(Strategy):
    def __init__(self, params: dict | None = None):
        self._params = {**_DEFAULTS, **(params or {})}
        members_param = self._params.get("members", _DEFAULT_MEMBERS)
        if isinstance(members_param, str):
            members_param = [m.strip() for m in members_param.split(",")]
        self._member_names: list[str] = list(members_param)
        self._members: list[Strategy] = [_load_strategy(n) for n in self._member_names]
        self._in_position = False
        self._side: int = 0

    @property
    def name(self) -> str:
        return "ensemble"

    @property
    def params(self) -> dict:
        return dict(self._params)

    def fit(self, df_train: pd.DataFrame) -> None:
        for m in self._members:
            m.fit(df_train)
        self._in_position = False
        self._side = 0

    def notify_stop(self, timestamp: pd.Timestamp) -> None:
        self._in_position = False
        self._side = 0
        # Propagate stop to members so they reset cooldowns
        for m in self._members:
            if hasattr(m, "notify_stop"):
                m.notify_stop(timestamp)

    def signal(self, df: pd.DataFrame) -> int:
        vote_thr = int(self._params["vote_threshold"])
        exit_thr = int(self._params["exit_threshold"])

        votes = [m.signal(df) for m in self._members]
        long_votes = votes.count(1)
        short_votes = votes.count(-1)

        if self._in_position:
            if self._side == 1:
                if long_votes < exit_thr:
                    self._in_position = False
                    self._side = 0
                    return 0
                return 1
            else:
                if short_votes < exit_thr:
                    self._in_position = False
                    self._side = 0
                    return 0
                return -1

        if long_votes >= vote_thr:
            self._in_position = True
            self._side = 1
            return 1

        if short_votes >= vote_thr:
            self._in_position = True
            self._side = -1
            return -1

        return 0

    @classmethod
    def from_yaml(cls, text: str) -> "EnsembleStrategy":
        import yaml

        spec = yaml.safe_load(text)
        return cls(params=spec.get("params", {}))
