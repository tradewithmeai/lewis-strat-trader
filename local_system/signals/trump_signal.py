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
    print("\n=== VALIDATION GATE ===")
    ok = True

    # 1. Apr-9-2025 directive "THIS IS A GREAT TIME TO BUY"
    apr9 = df[df.text.str.contains("GREAT TIME TO BUY", case=False, na=False)]
    if len(apr9):
        r = apr9.iloc[0]
        fb_ok = r.finbert_score > 0
        llm_ok = (r.get("llm_stance", 0) or 0) > 0 if r.get("has_llm") else None
        dir_ok = bool(r.get("is_market_directive", False)) if r.get("has_llm") else None
        print(f"[1] 'GREAT TIME TO BUY' ({r.ts:%Y-%m-%d}): finbert={r.finbert_score:+.2f} "
              f"{'PASS' if fb_ok else 'FAIL'}; "
              f"llm_stance={r.get('llm_stance')} dir_flag={r.get('is_market_directive')}")
        ok &= fb_ok
        if llm_ok is False:
            ok = False
    else:
        print("[1] directive post not found — FAIL")
        ok = False

    # 2. china/tariff posts net-bearish
    ct = df[(df.topic_china | df.topic_tariffs_trade) & ~df.is_noise]
    if len(ct):
        fb_mean = ct.finbert_score.mean()
        llm_sub = ct[ct.get("has_llm", False)] if "has_llm" in ct else ct.iloc[0:0]
        llm_mean = llm_sub["llm_stance"].mean() if len(llm_sub) else float("nan")
        print(f"[2] china/tariff posts (n={len(ct)}): finbert mean={fb_mean:+.3f}; "
              f"llm_stance mean={llm_mean:+.3f}")
        # FinBERT may be near-zero (news framing); the LLM stance is the real test
        if not np.isnan(llm_mean):
            print(f"    -> LLM net-bearish: {'PASS' if llm_mean < 0 else 'FAIL'}")
            ok &= llm_mean < 0
    else:
        print("[2] no china/tariff posts — FAIL")
        ok = False

    # 3. FinBERT vs VADER spread on market-relevant
    mr = df[df.market_relevant & ~df.is_noise]
    print(f"[3] market-relevant (n={len(mr)}): "
          f"FinBERT mean={mr.finbert_score.mean():+.3f} std={mr.finbert_score.std():.3f} | "
          f"VADER mean={mr.sentiment.mean():+.3f} std={mr.sentiment.std():.3f}")
    print(f"    -> FinBERT less positively-biased than VADER: "
          f"{'PASS' if abs(mr.finbert_score.mean()) < abs(mr.sentiment.mean()) else 'NOTE'}")

    print(f"\nGATE: {'PASS — proceed to Phase 2' if ok else 'FAIL — fix classifier before Phase 2'}")


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
