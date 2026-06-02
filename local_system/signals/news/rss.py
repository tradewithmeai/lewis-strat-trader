"""
rss.py — RSS/Atom news adapter (feedparser, no API key).

Crypto and financial outlets publish RSS feeds we can poll politely. feedparser
handles RSS+Atom, redirects, and most malformed feeds. We extract the publish
time as the event timestamp (falling back to fetch time only if absent).

Feed list is a starting set; verify/extend from docs/DATA_SOURCES.md. Any feed
that fails (404, redirect loop, parse error) is skipped — never fatal.
"""

from __future__ import annotations

from datetime import datetime, timezone

from local_system.signals.news.base import NewsAdapter, NewsEvent, now_iso, tag_text

# name -> feed URL. Cointelegraph confirmed working; others best-effort.
DEFAULT_FEEDS = {
    "cointelegraph": "https://cointelegraph.com/rss",
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "decrypt": "https://decrypt.co/feed",
    "bitcoinmagazine": "https://bitcoinmagazine.com/feed",
    "cryptoslate": "https://cryptoslate.com/feed/",
}


def _to_utc_iso(entry) -> str:
    """Extract publish time as UTC ISO from a feedparser entry; fall back to now."""
    for key in ("published_parsed", "updated_parsed"):
        t = getattr(entry, key, None) or (entry.get(key) if hasattr(entry, "get") else None)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc).isoformat()
            except (TypeError, ValueError):
                pass
    return now_iso()


class RssAdapter(NewsAdapter):
    name = "rss"

    def __init__(self, feeds: dict[str, str] | None = None, max_per_feed: int = 30):
        self.feeds = feeds or DEFAULT_FEEDS
        self.max_per_feed = max_per_feed

    def fetch(self) -> list[NewsEvent]:
        import feedparser

        events: list[NewsEvent] = []
        captured = now_iso()
        for source, url in self.feeds.items():
            try:
                parsed = feedparser.parse(url)
                for entry in parsed.entries[: self.max_per_feed]:
                    title = getattr(entry, "title", "") or ""
                    link = getattr(entry, "link", "") or ""
                    summary = getattr(entry, "summary", "") or ""
                    author = getattr(entry, "author", "") or ""
                    if not (title and link):
                        continue
                    events.append(
                        NewsEvent(
                            ts=_to_utc_iso(entry),
                            source=f"rss:{source}",
                            title=title.strip(),
                            url=link.strip(),
                            summary=summary.strip()[:500],
                            author=author.strip(),
                            tags=tag_text(title, summary),
                            captured_at=captured,
                        )
                    )
            except Exception as exc:  # noqa: BLE001 — bad feed must not kill the pass
                print(f"[rss] {source} failed: {exc}", flush=True)
        return events
