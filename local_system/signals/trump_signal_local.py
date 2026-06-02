"""
trump_signal_local.py — local ML signal extraction (Phase 1, bulk layer).

Enriches every text post with market-aware features computed locally on the
RTX 2070 (or CPU), no API, no usage limit. Text-only — NO forward returns ever
touch these labels (that would make Phase 2 circular; see
docs/TRUMP_EVENT_STUDY.md and RESEARCH_NOTE.md on the lookahead trap).

Features written to state/signals/trump_signal_local.parquet:

    finbert_pos/neg/neu   ProsusAI/finbert class probabilities (financial-news
                          sentiment — the market-aware replacement for VADER,
                          which scored angry tariff rants +0.97)
    finbert_score         P(pos) - P(neg)  in [-1, 1]
    novelty_7d            1 - max cosine similarity to the embeddings of posts
                          in the trailing 7 days (causal). Repetitive
                          endorsements -> ~0; first-of-kind threats -> ~1.
                          A novel post is a priori more market-moving than the
                          40th near-duplicate of the day.
    emb_*                 sentence-embedding (MiniLM, 384-d) persisted to
                          trump_embeddings.npy for Phase-2 clustering / the LLM
                          hard-case selector.

Carries over id/ts/topic dummies/market_relevant/burst_id/is_noise from
trump_classify so this file is the single enriched timeline.

Usage:
    uv run --extra research python -m local_system.signals.trump_signal_local
    uv run --extra research python -m local_system.signals.trump_signal_local --limit 500   # smoke test
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT_PARQUET = Path("state/signals/trump_signal_local.parquet")
OUT_EMB = Path("state/signals/trump_embeddings.npy")
EVENTS_PATH = Path("state/signals/trump_events.parquet")

FINBERT_MODEL = "ProsusAI/finbert"
EMB_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
NOVELTY_WINDOW_DAYS = 7
BATCH = 64


def _device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:  # noqa: BLE001
        return "cpu"


def _finbert_scores(texts: list[str], device: str) -> np.ndarray:
    """Return (n, 3) array of [P(pos), P(neg), P(neu)] from ProsusAI/finbert."""
    import torch
    from transformers import AutoModelForSequenceClassification, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(FINBERT_MODEL)
    model = AutoModelForSequenceClassification.from_pretrained(FINBERT_MODEL).to(device)
    model.eval()
    # ProsusAI/finbert label order: 0=positive, 1=negative, 2=neutral
    label_order = model.config.id2label  # confirm at runtime
    pos_i = next(i for i, l in label_order.items() if l.lower().startswith("pos"))
    neg_i = next(i for i, l in label_order.items() if l.lower().startswith("neg"))
    neu_i = next(i for i, l in label_order.items() if l.lower().startswith("neu"))

    out = np.zeros((len(texts), 3), dtype=np.float32)
    with torch.no_grad():
        for s in range(0, len(texts), BATCH):
            batch = texts[s : s + BATCH]
            enc = tok(batch, return_tensors="pt", truncation=True, max_length=256,
                      padding=True).to(device)
            probs = torch.softmax(model(**enc).logits, dim=-1).cpu().numpy()
            out[s : s + len(batch), 0] = probs[:, pos_i]
            out[s : s + len(batch), 1] = probs[:, neg_i]
            out[s : s + len(batch), 2] = probs[:, neu_i]
            print(f"  finbert {min(s + BATCH, len(texts))}/{len(texts)}", end="\r", flush=True)
    print()
    return out


def _embeddings(texts: list[str], device: str) -> np.ndarray:
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(EMB_MODEL, device=device)
    emb = model.encode(
        texts, batch_size=BATCH, show_progress_bar=True, normalize_embeddings=True
    )
    return np.asarray(emb, dtype=np.float32)


def _novelty(ts: pd.Series, emb: np.ndarray) -> np.ndarray:
    """1 - max cosine sim to embeddings of posts within the trailing window.

    Causal: only posts strictly before the current one. Embeddings are
    L2-normalised so dot product == cosine. O(n * window_count) — fine for 27k
    posts with a 7-day window.
    """
    tsv = ts.values.astype("datetime64[s]")
    window = np.timedelta64(NOVELTY_WINDOW_DAYS * 24 * 3600, "s")
    nov = np.ones(len(emb), dtype=np.float32)
    lo = 0
    for i in range(len(emb)):
        # advance lower bound so [lo, i) covers only the trailing window
        while tsv[i] - tsv[lo] > window:
            lo += 1
        if i > lo:
            sims = emb[lo:i] @ emb[i]
            nov[i] = float(1.0 - sims.max())
    return nov


def main() -> None:
    limit = None
    for a in sys.argv[1:]:
        if a.startswith("--limit"):
            limit = int(a.split("=")[-1]) if "=" in a else int(sys.argv[sys.argv.index(a) + 1])

    if not EVENTS_PATH.exists():
        print(f"{EVENTS_PATH} missing — run trump_classify first.")
        sys.exit(1)
    df = pd.read_parquet(EVENTS_PATH)
    df = df[df.text.str.len() > 0].reset_index(drop=True)
    if limit:
        df = df.head(limit).reset_index(drop=True)

    device = _device()
    print(f"device: {device} | posts: {len(df)}")

    texts = df["text"].tolist()
    print("computing FinBERT sentiment...")
    fb = _finbert_scores(texts, device)
    print("computing embeddings...")
    emb = _embeddings(texts, device)
    print("computing novelty (causal 7d)...")
    nov = _novelty(df["ts"], emb)

    df["finbert_pos"] = fb[:, 0]
    df["finbert_neg"] = fb[:, 1]
    df["finbert_neu"] = fb[:, 2]
    df["finbert_score"] = fb[:, 0] - fb[:, 1]
    df["novelty_7d"] = nov

    OUT_PARQUET.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT_PARQUET, index=False)
    np.save(OUT_EMB, emb)
    print(f"\n[written] {OUT_PARQUET}  ({len(df)} rows)")
    print(f"[written] {OUT_EMB}  {emb.shape}")

    # quick sanity: FinBERT vs VADER on market-relevant posts
    mr = df[df.market_relevant]
    print(f"\nmarket-relevant posts: {len(mr)}")
    print(f"  FinBERT score  mean={mr.finbert_score.mean():+.3f}  std={mr.finbert_score.std():.3f}")
    print(f"  VADER sentiment mean={mr.sentiment.mean():+.3f}  std={mr.sentiment.std():.3f}")
    print(f"  novelty_7d      mean={df.novelty_7d.mean():.3f}")


if __name__ == "__main__":
    main()
