"""
event_db.py — historical + live event database with per-event metadata + market reaction.

SCAFFOLD (I-build / Darren+Claude-extend). Normalises the captured news/social
stream (state/signals/news.jsonl, written by the news capture suite) into one
queryable table where every event carries:
  - identity + provenance (id, ts, source, url, author)
  - text (title, summary)
  - asset + category tags
  - the RESEARCH-CRITICAL part: the market REACTION — forward return on the
    relevant asset over +1h / +4h / +24h after the event, plus a |move| column
    (the volatility proxy that ties to the one validated edge: event-driven vol).

Output: state/signals/events.parquet  (rebuilt idempotently from news.jsonl).
Query:  load_event_table() -> DataFrame.

EXTENSION POINTS for Darren + Claude (grep 'EXTEND'):
  - LLM category classification (replace the keyword mapper)
  - sentiment / directional label (currently left null)
  - TradFi reactions via public data (currently crypto-lake only)
  - additional sources (add NewsAdapters upstream in local_system/signals/news/)
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from local_system.signals import SIGNALS_DIR

NEWS_LOG = SIGNALS_DIR / "news.jsonl"
EVENTS_PARQUET = SIGNALS_DIR / "events.parquet"

HORIZONS_H = (1, 4, 24)  # forward-return horizons in hours

# tag -> canonical lake symbol (EXTEND: add tradfi tickers once public-data join lands)
_ASSET_FROM_TAG = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT"}
# events with no explicit asset but a macro/policy flavour are priced against BTC
_MACRO_TAGS = {"fed", "macro", "regulation", "trump", "hack"}

# coarse category from existing keyword tags (EXTEND: LLM classifier)
_CATEGORY_FROM_TAG = {
    "fed": "monetary",
    "macro": "macro",
    "regulation": "regulation",
    "hack": "security",
    "trump": "politics",
}


def _event_id(rec: dict) -> str:
    key = (rec.get("url") or "").strip() or f"{rec.get('source')}|{rec.get('title')}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _primary_asset(tags: list[str]) -> str | None:
    for t in tags:
        if t in _ASSET_FROM_TAG:
            return _ASSET_FROM_TAG[t]
    if any(t in _MACRO_TAGS for t in tags):
        return "BTCUSDT"  # macro/policy events priced against BTC by default
    return None


def _category(tags: list[str]) -> str:
    for t in tags:
        if t in _CATEGORY_FROM_TAG:
            return _CATEGORY_FROM_TAG[t]
    return "other"


def _load_news() -> list[dict]:
    if not NEWS_LOG.exists():
        return []
    out = []
    for line in NEWS_LOG.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _price_series(asset: str):
    """1h close series for an asset over all history, or None if unavailable.

    Crypto only for now (reads the lake). EXTEND: branch to a public-data loader
    (yfinance etc.) for TradFi tickers so their events get reactions too."""
    try:
        from datetime import date, timedelta

        from local_system.lake_adapter import load_bars, resample_ohlcv

        end = date.today()
        start = end - timedelta(days=365 * 4)
        df = load_bars(asset, start, end, backfill_only=True)
        if df.empty:
            return None
        return resample_ohlcv(df, "1h")["close"]
    except Exception:
        return None


def _forward_returns(close: pd.Series, ts: pd.Timestamp) -> dict:
    """Return {ret_1h, ret_4h, ret_24h, abs_move_4h} using as-of price lookups."""
    out = {f"ret_{h}h": None for h in HORIZONS_H}
    out["abs_move_4h"] = None
    if close is None or close.empty:
        return out
    try:
        idx = close.index
        p0 = close.asof(ts)
        if pd.isna(p0) or p0 == 0:
            return out
        for h in HORIZONS_H:
            pt = close.asof(ts + pd.Timedelta(hours=h))
            if not pd.isna(pt):
                out[f"ret_{h}h"] = round(float(pt / p0 - 1.0) * 100.0, 3)
        if out.get("ret_4h") is not None:
            out["abs_move_4h"] = abs(out["ret_4h"])
    except Exception:
        pass
    return out


def build_event_table() -> pd.DataFrame:
    """Read news.jsonl, enrich, join market reaction, write events.parquet."""
    records = _load_news()
    if not records:
        print("[event_db] no news.jsonl yet — nothing to build")
        return pd.DataFrame()

    # cache one price series per asset so we load the lake once per symbol
    price_cache: dict[str, object] = {}
    rows = []
    for rec in records:
        tags = rec.get("tags") or []
        asset = _primary_asset(tags)
        ts = pd.to_datetime(rec.get("ts"), utc=True, errors="coerce")
        row = {
            "event_id": _event_id(rec),
            "ts": ts,
            "captured_at": rec.get("captured_at", ""),
            "source": rec.get("source", ""),
            "title": rec.get("title", ""),
            "summary": rec.get("summary", ""),
            "url": rec.get("url", ""),
            "author": rec.get("author", ""),
            "tags": ",".join(tags),
            "primary_asset": asset,
            "category": _category(tags),
            "sentiment": None,   # EXTEND: LLM
            "direction": None,   # EXTEND: LLM
        }
        if asset and pd.notna(ts):
            if asset not in price_cache:
                price_cache[asset] = _price_series(asset)
            row.update(_forward_returns(price_cache[asset], ts))
        else:
            row.update({f"ret_{h}h": None for h in HORIZONS_H})
            row["abs_move_4h"] = None
        rows.append(row)

    df = pd.DataFrame(rows).dropna(subset=["ts"]).sort_values("ts").reset_index(drop=True)
    df = df.drop_duplicates(subset=["event_id"], keep="last")
    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(EVENTS_PARQUET, index=False)
    n_react = int(df["ret_4h"].notna().sum()) if "ret_4h" in df else 0
    print(f"[event_db] wrote {len(df)} events -> {EVENTS_PARQUET} ({n_react} with market reaction)")
    return df


def load_event_table() -> pd.DataFrame:
    """Load the built events table for querying (empty frame if not built yet)."""
    if not EVENTS_PARQUET.exists():
        return pd.DataFrame()
    return pd.read_parquet(EVENTS_PARQUET)


if __name__ == "__main__":
    build_event_table()
