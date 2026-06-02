"""
trump_signal_llm.py — LLM directive/stance layer (Phase 1, hard cases).

FinBERT (trump_signal_local) gives market-news sentiment but is blind to
Trump's idiom ("GREAT TIME TO BUY", "Patriot", sarcasm, policy hints). This
layer sends the market-relevant subset to an OpenAI model for the nuanced
directional read FinBERT can't do.

DESIGN for this account's constraints (250k free tokens/day, prone to cutoffs):
  - Batched: ~20 posts per request, one JSON array out -> amortises the prompt.
  - Budget-aware: tracks token spend, stops before the daily cap.
  - Checkpointed: appends each post's result to a JSONL immediately; a cutoff
    loses at most the in-flight batch. Re-running skips already-done ids
    (resumable).
  - Text-only: the model is explicitly told to judge from the post alone and
    NOT use hindsight about what the market did (no lookahead -> Phase 2 stays
    non-circular).

Output: state/signals/trump_signal_llm.jsonl  (one row per classified post)
    id, llm_stance (-2..+2), conviction (0..1), is_policy_signal,
    is_market_directive, topic, rationale

Usage:
    uv run --extra research python -m local_system.signals.trump_signal_llm
    OPENAI_CLASSIFY_MODEL=gpt-4.1  ... (override model)
    --max-tokens 240000   daily budget cap (default)
    --limit N             classify only first N pending (smoke test)
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

LOCAL_PARQUET = Path("state/signals/trump_signal_local.parquet")
OUT_JSONL = Path("state/signals/trump_signal_llm.jsonl")
BUDGET_STATE = Path("state/signals/trump_llm_budget.json")

MODEL = os.environ.get("OPENAI_CLASSIFY_MODEL", "gpt-4.1-mini")
BATCH = 20
DAILY_CAP = 240_000  # stay under the 250k/day free tier

STANCE_MAP = {
    "strong_bearish": -2, "bearish": -1, "neutral": 0, "bullish": 1, "strong_bullish": 2,
}

SYSTEM = (
    "You are a markets analyst labelling social-media posts by Donald Trump for "
    "their likely SHORT-TERM effect on risk assets (US equities and crypto). "
    "Judge ONLY from the post text and what a trader would infer at the moment "
    "it was posted. Do NOT use any hindsight about what markets actually did. "
    "Many posts are political noise with no market content — label those neutral, "
    "conviction 0. Return STRICT JSON only."
)

INSTRUCTION = (
    "For each post in the array, return an object with fields:\n"
    "  i: the post's index (echo it back)\n"
    "  risk_stance: one of strong_bullish, bullish, neutral, bearish, strong_bearish "
    "(the direction a trader would lean for stocks/crypto on reading this)\n"
    "  conviction: 0.0-1.0 (how forceful and market-specific the signal is)\n"
    "  is_policy_signal: true if it hints at a concrete policy action "
    "(tariff, rate, trade deal, sanctions, fiscal)\n"
    "  is_market_directive: true if it explicitly tells people to buy/sell or "
    "predicts a market move (e.g. 'great time to buy', 'markets will boom')\n"
    "  topic: tariffs|china|fed|crypto|dollar|energy|markets|fiscal|geopolitics|other\n"
    "  rationale: <= 12 words\n"
    'Respond as {"results": [ ... ]} with one object per input post.'
)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _load_budget() -> int:
    if BUDGET_STATE.exists():
        d = json.loads(BUDGET_STATE.read_text())
        if d.get("date") == _today():
            return int(d.get("tokens", 0))
    return 0


def _save_budget(tokens: int) -> None:
    BUDGET_STATE.write_text(json.dumps({"date": _today(), "tokens": tokens}))


def _done_ids() -> set[str]:
    if not OUT_JSONL.exists():
        return set()
    ids = set()
    for line in OUT_JSONL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                ids.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass
    return ids


def _select_pending(df: pd.DataFrame, done: set[str]) -> pd.DataFrame:
    # Hard cases = market-relevant, non-noise posts (where directional idiom
    # matters). FinBERT already covers the bulk sentiment.
    hard = df[df.market_relevant & ~df.is_noise].copy()
    hard = hard[~hard["id"].astype(str).isin(done)]

    # Priority ordering so a budget-truncated run still covers the most
    # paper-relevant posts first: directives/reassurance, then the Phase-2 topic
    # set, then posts where FinBERT is least confident (LLM adds most there),
    # then novelty. A partial day's run is therefore not a random subset.
    import numpy as np

    prio = np.zeros(len(hard))
    prio += 100 * (hard["topic_market_directive"] | hard["topic_reassurance"]).to_numpy()
    for t in ("topic_china", "topic_tariffs_trade", "topic_fed_rates",
              "topic_crypto", "topic_dollar"):
        if t in hard:
            prio += 10 * hard[t].to_numpy()
    prio += 5 * (hard["finbert_score"].abs() < 0.15).to_numpy()  # low confidence
    prio += hard["novelty_7d"].fillna(0).to_numpy()
    hard = hard.assign(_prio=prio).sort_values("_prio", ascending=False)
    return hard.drop(columns="_prio").reset_index(drop=True)


def _classify_batch(client, posts: list[dict]) -> tuple[list[dict], int]:
    user = INSTRUCTION + "\n\nPOSTS:\n" + json.dumps(
        [{"i": p["i"], "text": p["text"][:480]} for p in posts], ensure_ascii=False
    )
    resp = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
        response_format={"type": "json_object"},
        temperature=0,
    )
    tokens = resp.usage.total_tokens if resp.usage else 0
    parsed = json.loads(resp.choices[0].message.content)
    return parsed.get("results", []), tokens


def main() -> None:
    limit = None
    cap = DAILY_CAP
    argv = sys.argv[1:]
    for i, a in enumerate(argv):
        if a == "--limit":
            limit = int(argv[i + 1])
        elif a == "--max-tokens":
            cap = int(argv[i + 1])

    if not LOCAL_PARQUET.exists():
        print(f"{LOCAL_PARQUET} missing — run trump_signal_local first.")
        sys.exit(1)
    df = pd.read_parquet(LOCAL_PARQUET)
    df["id"] = df["id"].astype(str)

    done = _done_ids()
    pending = _select_pending(df, done)
    if limit:
        pending = pending.head(limit)
    spent = _load_budget()
    print(f"model: {MODEL} | pending: {len(pending)} | already done: {len(done)} | "
          f"budget used today: {spent}/{cap}")
    if pending.empty:
        print("Nothing to classify.")
        return

    from openai import OpenAI

    client = OpenAI()

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    fout = OUT_JSONL.open("a", encoding="utf-8")
    n_done = 0
    for s in range(0, len(pending), BATCH):
        if spent >= cap:
            print(f"\n[budget] hit daily cap ({spent}/{cap}) — stopping cleanly. "
                  f"Re-run tomorrow to continue ({len(pending) - n_done} posts left).")
            break
        chunk = pending.iloc[s : s + BATCH]
        posts = [{"i": j, "text": t, "id": rid}
                 for j, (t, rid) in enumerate(zip(chunk["text"], chunk["id"]))]
        try:
            results, tokens = _classify_batch(client, posts)
        except Exception as exc:  # noqa: BLE001
            print(f"\n[error] batch {s}: {exc} — stopping (resumable).")
            break
        spent += tokens
        by_i = {r.get("i"): r for r in results}
        for p in posts:
            r = by_i.get(p["i"], {})
            stance = STANCE_MAP.get(str(r.get("risk_stance", "neutral")).lower(), 0)
            row = {
                "id": p["id"],
                "llm_stance": stance,
                "conviction": float(r.get("conviction", 0) or 0),
                "is_policy_signal": bool(r.get("is_policy_signal", False)),
                "is_market_directive": bool(r.get("is_market_directive", False)),
                "topic": str(r.get("topic", "other")),
                "rationale": str(r.get("rationale", ""))[:120],
            }
            fout.write(json.dumps(row, ensure_ascii=False) + "\n")
            n_done += 1
        fout.flush()
        _save_budget(spent)
        print(f"  batch {s // BATCH + 1}: +{tokens} tok (total {spent}/{cap}) | "
              f"{n_done}/{len(pending)} done", flush=True)

    fout.close()
    print(f"\n[done] classified {n_done} posts this run. tokens today: {spent}/{cap}")


if __name__ == "__main__":
    main()
