"""
event_db.py — historical + live event database with per-event metadata + market reaction.

SCAFFOLD (I-build / Darren+Claude-extend). Normalises events from two sources
into one queryable table with per-event market REACTION (forward return on the
relevant asset over +1h / +4h / +24h, plus |move|_4h — the volatility proxy):

  1. Live feed   — state/signals/news.jsonl (RSS crypto media + Trump live capture)
  2. Deep archive — state/signals/trump_events.parquet (~34k Trump posts since 2022,
     pre-classified with topic flags + sentiment + market_relevant/is_noise). This
     is the multi-regime depth the validated Trump-vol study used.

Output: state/signals/events.parquet  (rebuilt idempotently; deduped by event_id).
Query:  load_event_table() -> DataFrame.

EXTENSION POINTS for Darren + Claude (grep 'EXTEND'):
  - more LEADING sources (macro prints, regulatory filings, mainstream breaking
    news) — the current live feed is crypto-media-heavy and tends to LAG price
  - LLM sentiment / directional label for the RSS items (Trump archive has sentiment)
  - TradFi reactions via public data (currently crypto-lake only)
  - non-event baseline (random windows) so "elevated vol" is a real comparison
  - null-out reactions whose horizon hasn't elapsed yet (recent events read ~0)
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta

import pandas as pd

from local_system.signals import SIGNALS_DIR

NEWS_LOG = SIGNALS_DIR / "news.jsonl"
TRUMP_EVENTS = SIGNALS_DIR / "trump_events.parquet"
EVENTS_PARQUET = SIGNALS_DIR / "events.parquet"

HORIZONS_H = (1, 4, 24)

_ASSET_FROM_TAG = {"btc": "BTCUSDT", "eth": "ETHUSDT", "sol": "SOLUSDT"}
_MACRO_TAGS = {"fed", "macro", "regulation", "trump", "hack", "china", "tariff",
               "dollar", "energy", "geopolitics", "fiscal", "directive"}

_CATEGORY_FROM_TAG = {
    "fed": "monetary", "macro": "macro", "regulation": "regulation",
    "hack": "security", "trump": "politics", "china": "trade", "tariff": "trade",
    "dollar": "macro", "energy": "macro", "geopolitics": "geopolitics",
    "fiscal": "fiscal", "directive": "directive",
}

# Trump archive topic column -> tag
_TRUMP_TOPIC_TAG = {
    "topic_tariffs_trade": "tariff", "topic_china": "china", "topic_fed_rates": "fed",
    "topic_crypto": "crypto", "topic_dollar": "dollar", "topic_energy_oil": "energy",
    "topic_markets": "markets", "topic_taxes_fiscal": "fiscal",
    "topic_geopolitics": "geopolitics", "topic_market_directive": "directive",
    "topic_reassurance": "reassurance",
}
# priority order for assigning a single category to a Trump post
_TRUMP_CATEGORY_ORDER = ["directive", "fed", "tariff", "china", "dollar",
                         "energy", "geopolitics", "fiscal"]


def _event_id(url: str, source: str, title: str) -> str:
    key = (url or "").strip() or f"{source}|{title}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]


def _primary_asset(tags: list[str]) -> str | None:
    for t in tags:
        if t in _ASSET_FROM_TAG:
            return _ASSET_FROM_TAG[t]
    if any(t in _MACRO_TAGS for t in tags):
        return "BTCUSDT"
    return None


def _category(tags: list[str]) -> str:
    for t in tags:
        if t in _CATEGORY_FROM_TAG:
            return _CATEGORY_FROM_TAG[t]
    return "other"


def _load_news_records() -> list[dict]:
    """Records from the live feed (news.jsonl)."""
    if not NEWS_LOG.exists():
        return []
    out = []
    for line in NEWS_LOG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        tags = d.get("tags") or []
        out.append({
            "ts": d.get("ts"), "source": d.get("source", ""),
            "title": d.get("title", ""), "summary": d.get("summary", ""),
            "url": d.get("url", ""), "author": d.get("author", ""),
            "tags": tags, "category": _category(tags),
            "sentiment": None, "market_relevant": None, "is_noise": None,
        })
    return out


def _load_trump_archive() -> list[dict]:
    """Records from the deep Trump archive (trump_events.parquet, ~34k posts)."""
    if not TRUMP_EVENTS.exists():
        return []
    df = pd.read_parquet(TRUMP_EVENTS)
    out = []
    for r in df.itertuples(index=False):
        d = r._asdict()
        tags = ["trump"] + [tag for col, tag in _TRUMP_TOPIC_TAG.items() if d.get(col)]
        category = "politics"
        for key in _TRUMP_CATEGORY_ORDER:
            if key in tags:
                category = _CATEGORY_FROM_TAG.get(key, "politics")
                break
        text = str(d.get("text", "") or "")
        out.append({
            "ts": d.get("ts"), "source": "trump:archive",
            "title": text[:200], "summary": text, "url": d.get("url", ""),
            "author": "realDonaldTrump", "tags": tags, "category": category,
            "sentiment": d.get("sentiment"),
            "market_relevant": bool(d.get("market_relevant")),
            "is_noise": bool(d.get("is_noise")),
        })
    return out


def _price_series(asset: str, start: date):
    """1h close series for an asset from `start` to today, or None. Crypto only.
    EXTEND: branch to a public-data loader (yfinance) for TradFi tickers."""
    try:
        from local_system.lake_adapter import load_bars, resample_ohlcv

        df = load_bars(asset, start, date.today(), backfill_only=True)
        if df.empty:
            return None
        return resample_ohlcv(df, "1h")["close"]
    except Exception:
        return None


def _forward_returns(close, ts: pd.Timestamp) -> dict:
    out = {f"ret_{h}h": None for h in HORIZONS_H}
    out["abs_move_4h"] = None
    if close is None or close.empty:
        return out
    try:
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


def build_event_table(include_trump_archive: bool = True) -> pd.DataFrame:
    """Merge live feed + Trump archive, join market reaction, write events.parquet."""
    records = _load_news_records()
    if include_trump_archive:
        records += _load_trump_archive()
    if not records:
        print("[event_db] no events to build")
        return pd.DataFrame()

    rows = []
    for rec in records:
        tags = rec.get("tags") or []
        ts = pd.to_datetime(rec.get("ts"), utc=True, errors="coerce")
        if pd.isna(ts):
            continue
        rows.append({
            "event_id": _event_id(rec.get("url", ""), rec.get("source", ""), rec.get("title", "")),
            "ts": ts,
            "source": rec.get("source", ""),
            "title": rec.get("title", ""),
            "summary": rec.get("summary", ""),
            "url": rec.get("url", ""),
            "author": rec.get("author", ""),
            "tags": ",".join(tags),
            "primary_asset": _primary_asset(tags),
            "category": rec.get("category") or _category(tags),
            "sentiment": rec.get("sentiment"),
            "market_relevant": rec.get("market_relevant"),
            "is_noise": rec.get("is_noise"),
        })

    df = pd.DataFrame(rows).sort_values("ts").drop_duplicates(subset=["event_id"], keep="last")

    # Load one price series per asset, from that asset's earliest event (so the
    # 4y+ Trump archive gets reactions without loading the lake for assets that
    # only appear in the recent live feed).
    price_cache: dict[str, object] = {}
    for asset in df["primary_asset"].dropna().unique():
        earliest = df.loc[df["primary_asset"] == asset, "ts"].min().date() - timedelta(days=7)
        price_cache[asset] = _price_series(asset, earliest)

    react = []
    for _, row in df.iterrows():
        asset = row["primary_asset"]
        if asset and asset in price_cache:
            react.append(_forward_returns(price_cache[asset], row["ts"]))
        else:
            r = {f"ret_{h}h": None for h in HORIZONS_H}
            r["abs_move_4h"] = None
            react.append(r)
    df = pd.concat([df.reset_index(drop=True), pd.DataFrame(react)], axis=1)

    SIGNALS_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(EVENTS_PARQUET, index=False)
    n_react = int(df["ret_4h"].notna().sum())
    span = f"{df['ts'].min().date()} -> {df['ts'].max().date()}"
    print(f"[event_db] wrote {len(df)} events ({span}) -> {EVENTS_PARQUET} "
          f"({n_react} with market reaction)")
    return df


def load_event_table() -> pd.DataFrame:
    if not EVENTS_PARQUET.exists():
        return pd.DataFrame()
    return pd.read_parquet(EVENTS_PARQUET)


if __name__ == "__main__":
    build_event_table()
