"""
base.py — shared schema and adapter interface for the news suite.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone


@dataclass
class NewsEvent:
    """One normalised news/social item.

    `ts` is the EVENT time (when published) in UTC ISO — this is what later
    joins to price bars, so it must be the publish time, not the fetch time.
    `captured_at` records when we pulled it (for audit/latency analysis).
    """

    ts: str
    source: str
    title: str
    url: str
    summary: str = ""
    author: str = ""
    tags: list[str] = field(default_factory=list)
    captured_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Lightweight keyword tagging — enough to filter/route events without an LLM.
_TAG_PATTERNS = {
    "btc": r"\b(bitcoin|btc|xbt)\b",
    "eth": r"\b(ethereum|eth|ether)\b",
    "sol": r"\b(solana|sol)\b",
    "fed": r"\b(fed|fomc|powell|rate cut|rate hike|interest rate)\b",
    "regulation": r"\b(sec|cftc|regulat|lawsuit|etf|approval)\b",
    "macro": r"\b(inflation|cpi|gdp|jobs|unemployment|recession|tariff)\b",
    "trump": r"\b(trump)\b",
    "hack": r"\b(hack|exploit|breach|drained|stolen)\b",
}
_TAG_RES = {tag: re.compile(p, re.IGNORECASE) for tag, p in _TAG_PATTERNS.items()}


def tag_text(*parts: str) -> list[str]:
    """Return keyword tags found across the given text parts."""
    text = " ".join(p for p in parts if p)
    return [tag for tag, rx in _TAG_RES.items() if rx.search(text)]


class NewsAdapter(ABC):
    """A source of NewsEvents. Implementations must be resilient: on any error
    they return [] (and may log), never raise, so one bad source can't take down
    a capture pass."""

    name: str = "base"

    @abstractmethod
    def fetch(self) -> list[NewsEvent]: ...
