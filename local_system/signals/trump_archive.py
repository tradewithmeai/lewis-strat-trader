"""
trump_archive.py — full historical archive of Trump's Truth Social posts.

Source: CNN's public mirror of the Truth Social archive (successor to the
stiles/trump-truth-social-archive scraper, which pointed here when it was
retired in Oct 2025):

    https://ix.cnn.io/data/truth-social/truth_archive.parquet

Coverage: Feb 2022 -> now, ~33k+ posts, refreshed every ~5 minutes upstream.
No key required. Schema: id, created_at (ISO UTC), content (HTML), url,
media, replies_count, reblogs_count, favourites_count.

Reproducibility: analysis must run against a *pinned* local snapshot
(``state/signals/trump_archive.parquet``), never the live URL — the upstream
file changes every few minutes. ``refresh()`` re-downloads and overwrites the
pin, recording pull metadata in ``state/signals/trump_archive.meta.json``.

``load()`` returns a normalised DataFrame:
    ts (tz-aware UTC), text (HTML stripped), url, has_media,
    replies, reblogs, favourites
sorted ascending by ts, empty-text rows (pure media posts) kept but flagged.

Usage:
    uv run python -m local_system.signals.trump_archive            # load pin, print summary
    uv run python -m local_system.signals.trump_archive --refresh  # re-download first
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

import pandas as pd

ARCHIVE_URL = "https://ix.cnn.io/data/truth-social/truth_archive.parquet"
PIN_PATH = Path("state/signals/trump_archive.parquet")
META_PATH = Path("state/signals/trump_archive.meta.json")

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(raw: str | None) -> str:
    """Plain text from the archive's HTML content field."""
    if not raw:
        return ""
    # <br> and </p> act as separators, not deletions
    raw = re.sub(r"<br\s*/?>|</p>", " ", raw, flags=re.IGNORECASE)
    return _WS_RE.sub(" ", unescape(_TAG_RE.sub("", raw))).strip()


def refresh() -> None:
    """Download the live archive and overwrite the local pin + metadata."""
    import urllib.request

    print(f"[trump_archive] downloading {ARCHIVE_URL} ...", flush=True)
    req = urllib.request.Request(ARCHIVE_URL, headers={"User-Agent": "research/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = resp.read()
        etag = resp.headers.get("ETag", "")
        last_modified = resp.headers.get("Last-Modified", "")
    PIN_PATH.parent.mkdir(parents=True, exist_ok=True)
    PIN_PATH.write_bytes(data)
    n = len(pd.read_parquet(PIN_PATH))
    META_PATH.write_text(
        json.dumps(
            {
                "url": ARCHIVE_URL,
                "pulled_at": datetime.now(timezone.utc).isoformat(),
                "etag": etag,
                "last_modified": last_modified,
                "bytes": len(data),
                "rows": n,
            },
            indent=2,
        )
    )
    print(f"[trump_archive] pinned {n} posts ({len(data):,} bytes) -> {PIN_PATH}", flush=True)


def load() -> pd.DataFrame:
    """Normalised post table from the pinned snapshot (UTC, HTML stripped)."""
    if not PIN_PATH.exists():
        raise FileNotFoundError(
            f"{PIN_PATH} missing — run: uv run python -m local_system.signals.trump_archive --refresh"
        )
    raw = pd.read_parquet(PIN_PATH)
    out = pd.DataFrame(
        {
            "id": raw["id"].astype(str),
            "ts": pd.to_datetime(raw["created_at"], utc=True, format="mixed"),
            "text": raw["content"].map(strip_html),
            "url": raw["url"],
            "has_media": raw["media"].map(lambda m: bool(m) and str(m) not in ("[]", "")),
            "replies": raw["replies_count"].fillna(0).astype(int),
            "reblogs": raw["reblogs_count"].fillna(0).astype(int),
            "favourites": raw["favourites_count"].fillna(0).astype(int),
        }
    )
    out = out.drop_duplicates(subset="id").sort_values("ts").reset_index(drop=True)
    return out


def main() -> None:
    if "--refresh" in sys.argv:
        refresh()
    df = load()
    meta = json.loads(META_PATH.read_text()) if META_PATH.exists() else {}
    print(f"posts:     {len(df)}")
    print(f"range:     {df.ts.min()} -> {df.ts.max()}")
    print(f"with text: {(df.text != '').sum()}  media-only: {(df.text == '').sum()}")
    if meta:
        print(f"pinned at: {meta.get('pulled_at')}  etag: {meta.get('etag')}")


if __name__ == "__main__":
    main()
