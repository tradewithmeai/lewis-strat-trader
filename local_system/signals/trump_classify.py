"""
trump_classify.py — classify archived Trump posts into a market-event table.

Reads the pinned archive (see trump_archive.py) and emits
``state/signals/trump_events.parquet`` — the event-timeline variable for the
event study. One row per post:

    ts             tz-aware UTC post time (event time — the only join key)
    topic_*        boolean topic dummies (keyword taxonomy below)
    market_relevant  any economic topic hit (geopolitics tracked separately)
    sentiment      VADER compound in [-1, 1]  (crude: VADER is market-blind and
                   Trump's superlative style skews positive — topic dummies are
                   expected to carry more signal; sentiment is the v1 scalar)
    engagement     log1p(favourites) minus its trailing 30-day median — a
                   *relative* attention proxy (raw counts drift over the years)
    burst_id       posts <30 min apart share an id; bursts are the natural
                   clustering unit for standard errors (10-posts-in-7-minutes
                   is common, and within a burst moves can't be attributed to
                   one post)
    is_noise       endorsement / congratulation / pure-media boilerplate

Deliberately rule-based and dependency-light: reproducible, no API, no
look-ahead (uses post text + timestamp only). An LLM classifier on the
market_relevant subset is the v2 upgrade path.

Usage:
    uv run python -m local_system.signals.trump_classify        # build + summary
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from local_system.signals.trump_archive import load as load_archive

OUT_PATH = Path("state/signals/trump_events.parquet")

# --- topic taxonomy -------------------------------------------------------
# Word-boundary regexes, case-insensitive. Economic topics drive
# market_relevant; geopolitics is risk-off-relevant but flagged separately.
TOPICS: dict[str, str] = {
    "tariffs_trade": r"tariff|trade (?:deal|war|deficit|agreement)|import tax|exports?\b|"
    r"reciprocal|dumping|usmca|nafta|trade barrier|liberation day",
    "china": r"\bchina\b|\bchinese\b|\bxi\b|beijing|taiwan",
    "fed_rates": r"\bfed\b|federal reserve|\bpowell\b|interest rate|rate cuts?|rate hikes?|"
    r"\binflation\b|\bcpi\b|monetary",
    "crypto": r"bitcoin|\bbtc\b|crypto|digital asset|ethereum|stablecoin|\bmining\b.*coin|"
    r"\bsec\b.*crypto|strategic.*reserve.*(?:bitcoin|crypto)",
    "dollar": r"\bdollar\b|\bcurrency\b|devalu|\bbrics\b|reserve currency",
    "energy_oil": r"\boil\b|\bopec\b|\bdrill\b|gas(?:oline)? price|energy (?:price|cost|dominance)|"
    r"strategic petroleum",
    "markets": r"stock market|\bdow\b|s ?& ?p ?500|nasdaq|401\(?k\)?|stock price|all.time high",
    "taxes_fiscal": r"\btax(?:es|ation)?\b|spending bill|debt ceiling|\bbudget\b|\bdeficit\b|"
    r"big,? beautiful bill|govt? shutdown|government shutdown",
    "geopolitics": r"\brussia\b|ukraine|putin|\biran\b|israel|\bnuclear\b|north korea|"
    r"missile|\bwar\b|ceasefire|\bnato\b",
    # explicit market directives — the "THIS IS A GREAT TIME TO BUY!!! DJT"
    # class (2025-04-09, 4h before the tariff-pause rally; the accused-
    # manipulation posts). Policy keywords miss these entirely.
    "market_directive": r"time to buy|buy now|great time to (?:buy|invest)|"
    r"buy stocks?|markets? (?:will|are going to) (?:boom|soar|go (?:way )?up)|"
    r"stock market (?:is|will be) (?:up|booming|soaring)",
    # calm-the-market reassurance — fires almost exclusively during stress
    # ("BE COOL! Everything is going to work out well", "don't panic")
    "reassurance": r"be cool|don'?t panic|panican|everything (?:is going to|will) work out|"
    r"don'?t be (?:weak|stupid)|hang tough|be patient[,.!]",
}
ECON_TOPICS = [t for t in TOPICS if t != "geopolitics"]

NOISE_RE = re.compile(
    r"complete and total endorsement|my great honor to endorse|happy birthday|"
    r"congratulations|will be interviewed|tune in|enjoy!|\bmaga\b.*patriot.*endorse",
    re.IGNORECASE,
)

BURST_GAP_MIN = 30  # posts closer than this share a burst_id


def classify() -> pd.DataFrame:
    df = load_archive()
    text = df["text"]

    # topic dummies
    for topic, pattern in TOPICS.items():
        df[f"topic_{topic}"] = text.str.contains(pattern, case=False, regex=True)
    df["market_relevant"] = df[[f"topic_{t}" for t in ECON_TOPICS]].any(axis=1)
    df["is_noise"] = text.str.contains(NOISE_RE) | (text == "")

    # sentiment — VADER compound (crude v1 scalar; see module docstring)
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

    analyzer = SentimentIntensityAnalyzer()
    df["sentiment"] = [
        analyzer.polarity_scores(t)["compound"] if t else 0.0 for t in text
    ]

    # engagement — log favourites relative to trailing 30-day median
    lf = np.log1p(df["favourites"].astype(float))
    trailing = (
        pd.Series(lf.values, index=df["ts"]).rolling("30D").median().values
    )
    df["engagement"] = lf - trailing

    # burst ids — new burst when gap to previous post > 30 min
    gaps = df["ts"].diff().dt.total_seconds().div(60).fillna(np.inf)
    df["burst_id"] = (gaps > BURST_GAP_MIN).cumsum()

    return df


def main() -> None:
    df = classify()
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PATH, index=False)

    n = len(df)
    print(f"events written: {n} -> {OUT_PATH}")
    print(f"range: {df.ts.min()} -> {df.ts.max()}")
    print(f"market_relevant: {df.market_relevant.sum()} ({df.market_relevant.mean():.1%})")
    print(f"noise: {df.is_noise.sum()} ({df.is_noise.mean():.1%})")
    print(f"bursts: {df.burst_id.nunique()}")
    print("\ntopic counts:")
    for t in TOPICS:
        col = df[f"topic_{t}"]
        print(f"  {t:<14} {col.sum():>5}  ({col.mean():.1%})")
    print("\nsentiment by relevance:")
    print(df.groupby("market_relevant")["sentiment"].describe()[["count", "mean", "std"]])


if __name__ == "__main__":
    main()
