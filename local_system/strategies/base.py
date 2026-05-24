"""Abstract base class for all strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd
import yaml


class Strategy(ABC):
    """
    All strategies must implement fit() and signal().

    fit(df_train) — called once before backtesting on the test window.
                    Resets internal position state so the strategy is clean
                    at the start of the test window.

    signal(df) — called bar-by-bar with the full history up to that bar.
                 Returns 1 (long/hold-long) or 0 (flat/exit).

                 IMPORTANT: strategies are stateful. They track their own
                 _in_position flag. When flat, return 1 only when the entry
                 condition is met. When long, return 1 to HOLD and 0 only
                 when the explicit exit condition is met. This prevents the
                 backtester from exiting on every neutral bar.
    """

    # Subclasses set this in __init__ and reset it in fit().
    _in_position: bool = False

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def params(self) -> dict: ...

    @abstractmethod
    def fit(self, df_train: pd.DataFrame) -> None: ...

    @abstractmethod
    def signal(self, df: pd.DataFrame) -> int: ...

    def to_yaml(self) -> str:
        spec = {"name": self.name, "params": self.params}
        return yaml.dump(spec, default_flow_style=False)

    @classmethod
    def from_yaml(cls, text: str) -> "Strategy":
        raise NotImplementedError("Override from_yaml in the subclass")
