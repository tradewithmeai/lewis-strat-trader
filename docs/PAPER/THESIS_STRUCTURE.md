# Thesis structure & three-tier reporting plan

The deliverable is a **technical empirical thesis** (IMRaD skeleton, CS-thesis
chapter convention) with finance as the subject matter inside a methods-led
structure. Written as **one layered document where each academic level is a
superset of the level below** — not three separate write-ups. Sources for the
structure and the level distinctions are in `RELATED_WORK.md` / WORKLOG.

## Chapter skeleton (IMRaD → CS-thesis convention)

1. **Introduction & motivation** — the phenomenon; the 2025 episodes; contributions.
2. **Related work** — Krause cluster differentiated; Volfefe/Nishimura; crypto-sentiment.
3. **Background** — event-study method, realized vol, the look-ahead/circularity
   problem, multiple-testing, purged CV (reader-onboarding chapter).
4. **Data** — Truth Social archive (pinned); Binance hourly; macro daily; joins.
5. **Signal construction (text-only ML)** — taxonomy, FinBERT, LLM stance,
   embeddings/novelty, bursts. *The methodological core.*
6. **Method** — burst event study; endogenous-timing-matched null; purged/embargoed
   CV; BH-FDR/Romano-Wolf; OOS trading-edge rule (all pre-registered).
7. **Results** — *[BLOCKED until Phase 2]*; exploratory Phase-0 shown as such.
8. **Case study** — the Apr-9 "directive" episode; n=2 stated; allegations cited.
9. **Discussion / limitations** — co-movement, clustering, regime-specificity.
10. **Conclusion** — *[BLOCKED until Phase 2]*.
(+ optional **AI-augmented research methodology** chapter — see below.)
PhD form trims to an odd 5–9 chapters by merging (e.g. 2+3, 9+10).

## Three tiers — what each level adds

Each tier is the previous one plus more scope/rigor/originality. Word counts are
the standard academic ranges.

### Tier 1 — Bachelor's / undergraduate (5–15k words)
- **Bar:** competence — define question, review lit, apply *standard* methods correctly.
- **Content:** chapters 1–4, a *single-asset* (BTC) Phase-0 event study + the
  basic pre-registered Phase-2 regression, conclusion. Standard event-study +
  bootstrap + OLS.
- **Status:** essentially in hand once Phase 2 runs on BTC.

### Tier 2 — Master's (15–25k words)  ← realistic target
- **Bar:** independent project, *advanced* methods, fills a clearly bounded gap.
- **Adds:** the full text-only ML classification pipeline as a contribution;
  multi-asset (BTC/ETH/SOL) + macro; the endogenous-timing-matched null; purged/
  embargoed walk-forward CV; BH-FDR multiple-testing correction; the OOS
  tradeable-edge test; the case study. The bounded gap vs Krause: intraday +
  full-corpus systematic classification + timing control.
- **Status:** the realistic ceiling for the core finance work; a stretch but reachable.

### Tier 3 — PhD-level (40–80k words)  ← aspirational, direction of travel
- **Bar:** *substantial original* contribution — new method/theory or major
  empirical discovery; publishable; defensible to experts.
- **Adds (all needed, not just one):**
  - The full multi-phase program incl. Phase 3 (characterising / eventually
    predicting counter-intuitive directives) developed as N grows.
  - **The AI-augmented-research methodology as its own contribution** (below).
  - Breadth: placebo actors (other officials), cross-regime stability, additional
    asset classes / venues, alternative vol estimators, sub-period sensitivity.
  - Deeper theory: a formal treatment of endogenous-timing-controlled event
    studies for autocorrelated-volatility assets.
- **Honest caveat:** the current single 1–4h vol finding is **not** PhD-sized.
  Reaching this bar requires sustained additional contribution + breadth + time.
  Treat as the long-run direction, not a near deliverable.

## The AI-augmentation angle (the part the user cares most about)

The most novel element is **not** the finance result (Krause partly occupies that
ground) but the *meta* story: a researcher with the domain ideas but not the
current execution ability produces graduate-level empirical work with AI
assistance. Treated two ways:

1. **As a measurable claim with the WORKLOG as evidence.** `docs/WORKLOG.md`
   records the **division of labour**: human supplies domain hypotheses and
   direction (the manipulation instinct, pointing at the Apr-9 post, the reframe
   to ML); AI supplies implementation, analysis, and adversarial validation. That
   trail is *data* for the claim, not anecdote. Possible quantifications: human-
   decision vs AI-execution counts per phase; time-to-result; methods used that
   the human states they could not have implemented unaided.
2. **As a reflective chapter / companion paper** — "AI-augmented empirical
   research: a case study." Topical for an AI / meta-science / education venue.

**Honesty constraint (non-negotiable):** this is *capability augmentation*
("could do at uni, not unaided now"), NOT autonomous AI science. Human ideas and
direction are real and the human's; AI is the execution multiplier. Overclaiming
here would be the easiest thing for a reviewer to puncture.

**Audience split:** the finance result → q-fin/SSRN; the AI-augmentation story →
an AI/meta-science venue. They coexist inside the thesis (the reflective chapter);
as *published papers* they are two distinct products.

## Open decisions for the human author(s)
- Confirm layered-superset approach (vs three standalone documents).
- Which tier is the *primary* near-term target (recommend: master's core).
- Whether the AI-augmentation chapter is in-thesis, a companion paper, or both.
- Real author name(s)/affiliation; intended institution if this maps to an
  actual degree submission (formatting rules vary by university).
