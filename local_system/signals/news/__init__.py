"""
local_system.signals.news — pluggable news / social capture suite.

Each source is a NewsAdapter that returns a list of NewsEvent, normalised to a
common schema with **event-time** (publish) UTC timestamps. The capture
orchestrator runs all configured adapters, dedups, tags, and appends new events
to state/signals/news.jsonl for later joining to price bars.

Adapters:
  rss.RssAdapter      — crypto/financial RSS feeds (feedparser, no key)
  trump.TrumpAdapter  — Donald Trump's social posts (best-effort, see module)
"""
