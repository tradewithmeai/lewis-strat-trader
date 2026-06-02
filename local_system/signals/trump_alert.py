"""
trump_alert.py — classify incoming Trump posts and emit market alerts.

Classifies posts fetched from the live feed (trumpstruth.org RSS) against the
topic taxonomy from trump_classify.py and writes tier-graded alerts to
state/alerts.jsonl when a market-relevant post arrives.

Alert tiers (based on event-study findings in docs/TRUMP_EVENT_STUDY.md):

  TIER_A  market_directive  "THIS IS A GREAT TIME TO BUY"
          reassurance       "BE COOL! Everything is going to work out"
          -- These are the accused-manipulation-class posts; n=2 in the archive
             but both preceded large rallies. The post is a leading indicator
             of the poster's own upcoming policy action. Real-time alert.

  TIER_B  china / tariffs_trade
          -- Consistent negative 1h returns across all assets in regressions
             (BTC -8.7bp p=0.021, ETH -12.1bp p=0.017, SOL -17.9bp p=0.011).
             Small per-event; flag as risk-awareness signal.

  TIER_C  any other market_relevant post
          -- General elevated-vol window (~4h). Background awareness.

Usage (standalone):
    uv run python -m local_system.signals.trump_alert [--check-once]

Called from paper_trader once per tick to append new alerts without blocking
the main loop (synchronous, fast: only fetches if >= POLL_INTERVAL has passed
since last check).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Reuse the taxonomy from trump_classify without importing the full classify
# pipeline — we only need to match a single post's text at runtime.
from local_system.signals.trump_classify import ECON_TOPICS, NOISE_RE, TOPICS

ALERTS_LOG = Path("state/alerts.jsonl")
SEEN_LOG = Path("state/signals/trump_seen.jsonl")
POLL_INTERVAL = timedelta(minutes=5)   # CNN archive refreshes ~every 5 min
_last_poll: datetime | None = None

TIER = {
    "market_directive": "A",
    "reassurance": "A",
    "china": "B",
    "tariffs_trade": "B",
}

_EXPECTED_WINDOW = {
    "A": "rally / large move likely within 1-4h (n=2; treat as alert not stat)",
    "B": "modest negative return expected next 1h (BTC ~-9bp, ETH ~-12bp, SOL ~-18bp)",
    "C": "elevated vol expected next 1-4h (~+5% relative)",
}


def _topic_hits(text: str) -> list[str]:
    import re
    hits = []
    for topic, pattern in TOPICS.items():
        if re.search(pattern, text, re.IGNORECASE):
            hits.append(topic)
    return hits


def _is_noise(text: str) -> bool:
    return bool(NOISE_RE.search(text)) or not text.strip()


def _tier(topics: list[str]) -> str:
    for t in ("market_directive", "reassurance"):
        if t in topics:
            return "A"
    for t in ("china", "tariffs_trade"):
        if t in topics:
            return "B"
    econ_hits = [t for t in topics if t in ECON_TOPICS]
    return "C" if econ_hits else ""


def _load_seen() -> set[str]:
    if not SEEN_LOG.exists():
        return set()
    seen: set[str] = set()
    for line in SEEN_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                seen.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return seen


def _mark_seen(post_id: str) -> None:
    SEEN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SEEN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"id": post_id, "ts": datetime.now(timezone.utc).isoformat()}) + "\n")


def _write_alert(alert: dict) -> None:
    ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(alert) + "\n")


def check_and_alert(force: bool = False) -> list[dict]:
    """Fetch the live feed, classify new posts, append alerts. Returns new alerts."""
    global _last_poll
    now = datetime.now(timezone.utc)
    if not force and _last_poll and (now - _last_poll) < POLL_INTERVAL:
        return []
    _last_poll = now

    from local_system.signals.news.trump import TrumpAdapter
    from local_system.signals.trump_archive import strip_html

    adapter = TrumpAdapter(max_items=50)
    try:
        raw_events = adapter.fetch()
    except Exception as exc:  # noqa: BLE001
        print(f"[trump_alert] feed fetch failed: {exc}", flush=True)
        return []

    seen = _load_seen()
    new_alerts: list[dict] = []

    for ev in raw_events:
        post_id = ev.url or ev.title[:80]
        if post_id in seen:
            continue
        _mark_seen(post_id)

        text = strip_html(ev.summary) or ev.title
        if _is_noise(text):
            continue

        topics = _topic_hits(text)
        t = _tier(topics)
        # Only alert on Tier-A (directive/reassurance) and Tier-B (china/tariffs).
        # Tier-C ("any market_relevant") is too broad for actionable alerts —
        # it is tracked in trump_events.parquet for the event study but not paged.
        if t not in ("A", "B"):
            continue

        alert = {
            "ts": ev.ts,
            "source": "trump:truthsocial",
            "tier": t,
            "topics": topics,
            "expected": _EXPECTED_WINDOW[t],
            "message": (
                f"[TRUMP TIER-{t}] {', '.join(topics)} | {ev.ts[:16]} | "
                + text[:120].encode("ascii", "replace").decode()
            ),
            "text": text[:500],
            "url": ev.url,
        }
        _write_alert(alert)
        new_alerts.append(alert)
        print(
            f"[trump_alert] TIER-{t} | {', '.join(topics)} | "
            + text[:80].encode("ascii", "replace").decode(),
            flush=True,
        )

    return new_alerts


def main() -> None:
    import sys

    force = "--check-once" in sys.argv
    alerts = check_and_alert(force=True)
    if alerts:
        print(f"\n{len(alerts)} new alert(s):")
        for a in alerts:
            print(f"  {a['message']}")
    else:
        print("No new market-relevant posts.")


if __name__ == "__main__":
    main()
