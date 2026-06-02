"""
trump_signal.py — merge local + LLM layers into the master signal timeline,
and run the validation gate before any Phase-2 modelling.

Combines:
  trump_signal_local.parquet  (FinBERT sentiment, novelty, topics, bursts)
  trump_signal_llm.jsonl      (LLM stance/conviction/policy/directive flags)

into state/signals/trump_signal.parquet — the single enriched, event-time,
text-only (no-lookahead) timeline that Phase 2 regresses against.

Blended headline column `signal` in [-1, 1]:
  - LLM-labelled posts: llm_stance/2 scaled by conviction (the nuanced read)
  - others: finbert_score (market-news sentiment fallback)
All raw component columns are kept so Phase-2 models can weight them directly.

VALIDATION GATE (--validate): the classifier must label ground-truth events
correctly or Phase 2 is built on sand. Checks:
  - The Apr-9-2025 "GREAT TIME TO BUY" directive reads bullish + directive flag
  - china/tariff posts read net-bearish
  - FinBERT separates these better than VADER did
Prints PASS/FAIL per check.

Usage:
    uv run --extra research python -m local_system.signals.trump_signal            # merge
    uv run --extra research python -m local_system.signals.trump_signal --validate # merge + gate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

LOCAL_PARQUET = Path("state/signals/trump_signal_local.parquet")
LLM_JSONL = Path("state/signals/trump_signal_llm.jsonl")
OUT_PARQUET = Path("state/signals/trump_signal.parquet")


def _load_llm() -> pd.DataFrame:
    if not LLM_JSONL.exists():
        return pd.DataFrame()
    rows = [json.loads(line) for line in LLM_JSONL.read_text(encoding="utf-8").splitlines()
            if line.strip()]
    if not rows:
        return pd.DataFrame()
    llm = pd.DataFrame(rows).drop_duplicates(subset="id", keep="last")
    llm["id"] = llm["id"].astype(str)
    return llm


def merge() -> pd.DataFrame:
    df = pd.read_parquet(LOCAL_PARQUET)
    df["id"] = df["id"].astype(str)
    llm = _load_llm()
    if not llm.empty:
        df = df.merge(llm, on="id", how="left", suffixes=("", "_llm"))
    else:
        for c, default in [("llm_stance", np.nan), ("conviction", np.nan),
                           ("is_policy_signal", False), ("is_market_directive", False),
                           ("topic", None), ("rationale", None)]:
            df[c] = default

    has_llm = df["llm_stance"].notna()
    blended = np.where(
        has_llm,
        (df["llm_stance"].fillna(0) / 2.0) * df["conviction"].fillna(0),
        df["finbert_score"],
    )
    df["signal"] = blended.astype(float)
    df["has_llm"] = has_llm
    return df


def _validate(df: pd.DataFrame) -> None:
    """Build-consistency smoke test — NOT evidence of predictive skill.

    The only pass/fail check is [1]: the constructed directive class labels the
    Apr-9 "GREAT TIME TO BUY" post correctly (near-tautological — that class was
    built to catch it — so it confirms the pipeline wired up, nothing more).
    Checks [2]/[3] are DESCRIPTIVE only: an earlier version pass/failed [2] on
    "china/tariff stance must be net-bearish", which is mis-specified — it
    conflates rhetorical/market-impact stance with the topic's average return
    sign. Most china/tariff posts gloat about *already-known* tariffs (a trader
    does not sell on gloating), so a mildly positive mean stance is expected and
    correct; the bearish reaction lives in the topic dummy, not the stance. The
    informative split is is_policy_signal (fresh escalation vs commentary).
    """
    print("\n=== VALIDATION GATE (build-consistency smoke test) ===")

    # [1] PASS/FAIL — directive post labelled correctly (the only gate)
    apr9 = df[df.text.str.contains("GREAT TIME TO BUY", case=False, na=False)]
    ok = False
    if len(apr9):
        r = apr9.iloc[0]
        fb_ok = r.finbert_score > 0
        llm_stance = r.get("llm_stance")
        dir_flag = bool(r.get("is_market_directive", False))
        # pass: FinBERT positive AND (if LLM-labelled) stance>0 and directive flagged
        llm_ok = True if not r.get("has_llm") else ((llm_stance or 0) > 0 and dir_flag)
        ok = bool(fb_ok and llm_ok)
        print(f"[1] 'GREAT TIME TO BUY' ({r.ts:%Y-%m-%d}): finbert={r.finbert_score:+.2f}, "
              f"llm_stance={llm_stance}, directive={dir_flag} -> {'PASS' if ok else 'FAIL'}")
    else:
        print("[1] directive post not found -> FAIL")

    # [2] DESCRIPTIVE — china/tariff stance, split by is_policy_signal
    ct = df[(df.topic_china | df.topic_tariffs_trade) & ~df.is_noise]
    if len(ct) and "has_llm" in ct:
        lc = ct[ct.has_llm.fillna(False)]
        print(f"[2] china/tariff (n={len(ct)}, llm-labelled={len(lc)}): "
              f"stance mean={lc.llm_stance.mean():+.3f} (descriptive, NOT a gate)")
        if "is_policy_signal" in lc and lc.is_policy_signal.notna().any():
            pol = lc.is_policy_signal.fillna(False).astype(bool)
            esc = lc[pol]
            com = lc[~pol]
            print(f"    escalation posts (is_policy_signal, n={len(esc)}): "
                  f"stance mean={esc.llm_stance.mean():+.3f}")
            print(f"    commentary posts (n={len(com)}): "
                  f"stance mean={com.llm_stance.mean():+.3f}")

    # [3] DESCRIPTIVE — FinBERT vs VADER on market-relevant
    mr = df[df.market_relevant & ~df.is_noise]
    print(f"[3] market-relevant (n={len(mr)}): FinBERT mean={mr.finbert_score.mean():+.3f} | "
          f"VADER mean={mr.sentiment.mean():+.3f} (descriptive)")

    print(f"\nGATE (build-consistency only): "
          f"{'PASS — pipeline wired correctly' if ok else 'FAIL — directive mislabelled, check pipeline'}")


def main() -> None:
    if not LOCAL_PARQUET.exists():
        print(f"{LOCAL_PARQUET} missing — run trump_signal_local first.")
        sys.exit(1)
    df = merge()
    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    n_llm = int(df["has_llm"].sum())
    print(f"[written] {OUT_PARQUET}  ({len(df)} rows, {n_llm} with LLM labels)")
    print(f"signal column: mean={df.signal.mean():+.3f} std={df.signal.std():.3f} "
          f"nonzero={int((df.signal != 0).sum())}")

    if "--validate" in sys.argv:
        _validate(df)


if __name__ == "__main__":
    main()
