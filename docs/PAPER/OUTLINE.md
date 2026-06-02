# Paper outline & framing decisions

**Working title (draft):** *Posts as Events: Intraday Crypto Reactions to a Head
of State's Social-Media Communications, with an Endogenous-Timing Control*

**Status:** scaffold. Results/Conclusion sections are intentionally **blocked
until Phase 2 lands** — the paper's spine depends on whether the tradeable-edge
test comes back null (likely) or not. Either is a real paper.

**Target venue (default, revisit):** arXiv (q-fin.ST / econ.GN) + SSRN working
paper first — that is where the direct competitors (Krause) publish — then
extend toward a finance / computational-social-science journal if the empirics
warrant. This default sets a moderate robustness apparatus; a journal target
would add more (alternative vol estimators, sub-period stability, placebo actors).

## Authorship & disclosure (decided)

- Human collaborator(s) are the author(s). An AI assistant is **not** listed as
  an author (arXiv / ICMJE / Nature / Science policy: authorship requires
  accountability an AI cannot hold). AI assistance is disclosed in a Methods /
  Acknowledgements statement and the open-source pipeline is cited. Credit is
  shared as contribution + tooling disclosure, not a byline.
- Full reproducibility trail: `docs/WORKLOG.md` + pinned data + committed code.

## Framing rules (non-negotiable)

- **Exploratory vs confirmatory split.** Phase 0 (event study,
  `TRUMP_EVENT_STUDY.md`) = exploratory / hypothesis-generating; its taxonomy was
  refined on observed 2025 episodes. Phase 2 (pre-registered, `PREREGISTRATION.md`)
  = confirmatory. State this explicitly; never present Phase 0 as confirmed.
- **Neutral language.** "Informational content of official communications",
  "abnormal returns/volatility around posts". Report manipulation/insider-trading
  allegations as **dated, cited fact**; do **not** conclude manipulation.
- **Effect-size honesty.** Lead with the modest, short-horizon (1–4h) vol effect;
  disclose BTC/ETH/SOL co-movement (~0.92 → ~one factor) and the SOL full-sample
  null; note the 24h effect was clustering. Underclaiming is the contribution.
- **The "validation gate" is a build-consistency smoke test, not evidence of
  skill** (it is near-tautological: the directive class was built to catch Apr 9).
  Do not cite it as validation.

## Structure

1. **Introduction** — the phenomenon (a head of state whose posts can precede the
   policy they concern); the three 2025 episodes as motivation; our three
   contributions (systematic corpus classification; intraday resolution;
   endogenous-timing control). Explicit "to our knowledge, first to jointly…".
2. **Related work** — see `RELATED_WORK.md` (Krause cluster differentiated;
   Volfefe/Nishimura background; crypto-sentiment background).
3. **Data** — CNN Truth Social archive (33,712 posts, pinned); Binance hourly
   crypto; macro daily panel. Event-time UTC; no-lookahead joins; the Liberation-
   Day join validation.
4. **Signal construction (text-only)** — taxonomy; FinBERT; LLM stance on hard
   cases; novelty; bursts. Emphasise no forward data enters labels.
5. **Method** — burst-level event study; the era + trailing-vol-matched null;
   purged/embargoed walk-forward CV; BH-FDR / Romano-Wolf; the OOS trading-edge
   decision rule. (All pre-registered.)
6. **Results** — *[BLOCKED until Phase 2]*. Exploratory Phase-0 findings shown as
   such; confirmatory Phase-2 results with corrected p-values; the tradeable-edge
   verdict.
7. **Case study** — the Apr-9 "directive" episode timeline (post → 4h → policy
   reversal), as a qualitative illustration of the directive class; n=2 stated
   plainly; allegations cited.
8. **Discussion / limitations** — co-movement; clustering; regime-specificity
   (second-term tariff war); engagement-not-known-at-post-time; classifier idiom
   limits; reaction ≠ causation.
9. **Conclusion** — *[BLOCKED until Phase 2]*.

## Phase 3 (separate future paper, not this one)

"Predicting *when* counter-intuitive directives occur" is **not** deliverable
now (n=2 directives — not trainable). This paper instead **characterises the
conditions** around the known episodes (the Apr-9 template: recent market stress
→ bullish directive → policy reversal) as a testable hypothesis, and the live
collection pipeline grows the labelled set for a future timing study.

## Open decisions for the human author(s)
- Venue: arXiv/SSRN working paper first (default) vs aim directly at a journal.
- How prominent to make the "directive/manipulation" episodes (motivating hook
  vs a contained case-study section — current plan is the latter, for legal/tone
  safety).
- Real author name(s) / affiliation for the byline.
