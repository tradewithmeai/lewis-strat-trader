"""
trump.py — Donald Trump social-post adapter (best-effort, graceful degradation).

Trump's posts (Truth Social, sometimes X) move crypto and macro markets, so
they're worth capturing as an event stream. But there is **no official, stable,
free API** for Truth Social, and scraping it fights Cloudflare. This adapter is
therefore deliberately pluggable and fails soft:

  - It reads a feed URL from the env var ``TRUMP_FEED_URL`` (an RSS/Atom or
    JSON-feed mirror of his posts — e.g. a trumpstruth.org-style feed or an
    RSS-bridge instance you control), falling back to a default candidate.
  - If the source is unreachable or empty, it returns [] and logs a clear
    "needs config" message rather than raising.

This keeps the rest of the capture suite working while the exact Trump source is
finalised (see docs/DATA_SOURCES.md, populated by source research). Swap the
implementation of ``_fetch_raw`` for whatever source proves reliable.

NOTE: respect each source's ToS. Prefer a public feed/mirror over scraping.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from local_system.signals.news.base import NewsAdapter, NewsEvent, now_iso, tag_text

# Overridable; default is a candidate public feed of his Truth Social posts.
DEFAULT_TRUMP_FEED = "https://trumpstruth.org/feed"


class TrumpAdapter(NewsAdapter):
    name = "trump"

    def __init__(self, feed_url: str | None = None, max_items: int = 30):
        self.feed_url = feed_url or os.environ.get("TRUMP_FEED_URL", DEFAULT_TRUMP_FEED)
        self.max_items = max_items

    def _fetch_raw(self):
        """Return feedparser entries from the configured feed, or [] on failure."""
        import feedparser

        parsed = feedparser.parse(self.feed_url)
        return parsed.entries[: self.max_items]

    def fetch(self) -> list[NewsEvent]:
        captured = now_iso()
        try:
            entries = self._fetch_raw()
        except Exception as exc:  # noqa: BLE001
            print(f"[trump] source unreachable ({self.feed_url}): {exc}", flush=True)
            return []

        if not entries:
            print(
                f"[trump] no posts from {self.feed_url} — set TRUMP_FEED_URL to a "
                "working Truth Social/X feed mirror (best-effort source).",
                flush=True,
            )
            return []

        events: list[NewsEvent] = []
        for e in entries:
            title = (getattr(e, "title", "") or "").strip()
            link = (getattr(e, "link", "") or "").strip()
            summary = (getattr(e, "summary", "") or "").strip()
            body = title or summary
            if not body:
                continue
            ts = now_iso()
            t = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
            if t:
                try:
                    ts = datetime(*t[:6], tzinfo=timezone.utc).isoformat()
                except (TypeError, ValueError):
                    pass
            events.append(
                NewsEvent(
                    ts=ts,
                    source="trump:truthsocial",
                    title=body[:280],
                    url=link,
                    summary=summary[:500],
                    author="realDonaldTrump",
                    tags=list({"trump", *tag_text(body, summary)}),
                    captured_at=captured,
                )
            )
        return events
