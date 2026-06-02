"""
capture.py — orchestrate news adapters into a deduped event log.

Runs each adapter, dedups against events already in state/signals/news.jsonl
(by URL, falling back to source+title for items without a URL), tags, and
appends only new events. Idempotent: re-running won't duplicate.
"""

from __future__ import annotations

import json

from local_system.signals import SIGNALS_DIR
from local_system.signals.news.base import NewsAdapter, NewsEvent
from local_system.signals.news.rss import RssAdapter
from local_system.signals.news.trump import TrumpAdapter

NEWS_LOG = SIGNALS_DIR / "news.jsonl"


def _event_key(e: NewsEvent) -> str:
    return e.url.strip() if e.url.strip() else f"{e.source}|{e.title}"


def _load_seen_keys() -> set[str]:
    if not NEWS_LOG.exists():
        return set()
    seen: set[str] = set()
    for line in NEWS_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            seen.add(d.get("url") or f"{d.get('source')}|{d.get('title')}")
        except json.JSONDecodeError:
            continue
    return seen


def default_adapters() -> list[NewsAdapter]:
    return [RssAdapter(), TrumpAdapter()]


def run_capture(adapters: list[NewsAdapter] | None = None, persist: bool = True) -> dict:
    """Run adapters, append new events to news.jsonl, return a summary dict."""
    adapters = adapters or default_adapters()
    seen = _load_seen_keys()

    collected: list[NewsEvent] = []
    per_source: dict[str, int] = {}
    for ad in adapters:
        evs = ad.fetch()
        per_source[ad.name] = len(evs)
        collected.extend(evs)

    # Dedup within this pass and against history
    new: list[NewsEvent] = []
    batch_keys: set[str] = set()
    for e in collected:
        k = _event_key(e)
        if k in seen or k in batch_keys:
            continue
        batch_keys.add(k)
        new.append(e)

    new.sort(key=lambda e: e.ts)

    if persist and new:
        SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
        with open(NEWS_LOG, "a", encoding="utf-8") as fh:
            for e in new:
                fh.write(json.dumps(e.to_dict()) + "\n")

    return {
        "fetched_per_source": per_source,
        "total_fetched": len(collected),
        "new_events": len(new),
        "newest": new[-1].to_dict() if new else None,
    }


if __name__ == "__main__":
    summary = run_capture()
    print(f"fetched per source: {summary['fetched_per_source']}")
    print(f"total fetched: {summary['total_fetched']}  new: {summary['new_events']}")
    if summary["newest"]:
        n = summary["newest"]
        print(f"\nnewest: [{n['ts']}] ({n['source']}) {n['title'][:100]}")
        print(f"  tags: {n['tags']}")
