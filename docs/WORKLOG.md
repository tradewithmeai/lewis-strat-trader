# Work log — lewis-strat-trader

A chronological journal of every meaningful decision, test, run, and dead-end.
Newest entries are appended at the bottom. Maintained by the `/worklog` skill
(narrative, written by the agent from the conversation) plus an automatic
`post-commit` git hook (deterministic spine in `state/commit_log.tsv`).

Each entry covers the work leading up to one or more commits. **Why** matters as
much as **what** — dead-ends and rejected approaches are recorded deliberately,
because knowing what *didn't* work is the expensive knowledge.

Format per entry:
```
## YYYY-MM-DD HH:MM UTC — <title>            [commit <short-hash>]
**Context:** why this was undertaken
**Did:** what was built/run/changed
**Tested:** commands run + results (numbers, p-values, pass/fail)
**Decided:** the call made and the reasoning
**Dead-ends / caveats:** what was rejected and why
**Next:** what this sets up
```

---

## 2026-06-02 — Trump Truth Social event study (Phase 0)   [commits 35a375c → c122e91]

**Context:** User wants to study market reactions to Trump's Truth Social posts
("the king of market manipulation") — classify posts for sentiment/message, mark
an event-time timeline variable, regress price + macro reactions against it. A
classic event-study design.

**Did / Tested / Decided (the arc):**
- **Data source hunt.** The live `trump.py` adapter (trumpstruth.org RSS) only
  yields ~30 recent posts. Found the **CNN Truth Social archive** (successor to
  the retired stiles/trump-truth-social-archive): 33,712 posts Feb 2022→now,
  refreshed ~5 min, free, as parquet. Built `trump_archive.py` to ingest +
  **pin a frozen snapshot** (`state/signals/trump_archive.parquet` +
  `.meta.json`) — reproducibility: the live file changes every few minutes, so
  analysis must run against the pin. *Decided:* pin, don't re-pull per run.
- **Classifier** (`trump_classify.py`): keyword topic taxonomy (tariffs, china,
  fed, crypto, dollar, energy, markets, fiscal, geopolitics), a market-relevance
  funnel (~8% of posts), burst IDs (posts <30 min apart = one burst — the
  clustering unit, since 10-posts-in-7-min bursts are common and within-burst
  moves can't be attributed to one post), VADER sentiment as a v1 scalar.
- **Join validation** on the Apr-2-2025 "Liberation Day" selloff confirmed
  timestamps line up (BTC −2.4%/h that evening) — caught/avoided a timezone bug.
- **Event study** (`_event_study_trump.py`): burst-level, vs a bootstrap null
  matched on hour-of-day, era-split at inauguration (2025-01-20), day-clustered
  OLS. Added `binance_klines.py` to fetch ETH/SOL hourly history the lake lacks.
- **User flagged the manipulation posts** ("It's time to buy" before the tariff
  reversal). The exact post — **"THIS IS A GREAT TIME TO BUY!!! DJT"** (Apr 9
  2025, ~4h before the 90-day tariff pause). Key catch: it contains NO policy
  keywords, so the taxonomy missed it. Added `market_directive` + `reassurance`
  topic classes to capture this accused-manipulation class.
- **Advisor caught the decisive confound:** the hour-of-day null doesn't control
  for *volatility clustering* — he may post *because* markets are already moving
  (endogenous timing), which would manufacture a fake vol effect. Rebuilt the
  null to match on **trailing-24h-vol quintile** + added an all-bars regression
  of forward vol on an event dummy controlling for trailing vol.

**Result (the finding):**
- **1–4h forward-vol bump SURVIVES** the vol-matched null (BTC +5.1bp/4h
  p=0.008; ETH similar; SOL in-office p=0.033). The **24h effect died** — that
  was pure vol clustering.
- **china/tariff posts → −9 to −18bp next hour**, same sign all 3 assets (but
  BTC/ETH/SOL co-move 0.92, so that's ~one observation, not three).
- **VADER sentiment DEAD** (sign-flips; Trump superlatives score angry tariff
  rants +0.97).
- **`market_directive` huge but n=2** — case study, not statistics. Both buy-
  directives preceded big rallies. It's a leading indicator of his *own* coming
  policy action → belongs in a real-time alert tier, not a regression.
- Written up in `docs/TRUMP_EVENT_STUDY.md`.

**Dead-ends / caveats:** unmatched null overstated the effect ("in-office only"
was partly an artifact); macro daily panel underpowered (Dec-2024+ only, nothing
significant). Correlation/reaction not causation.

**Next:** turn findings into (1) a live alert tier, (2) strategy features.

## 2026-06-02 — Alert tier wired into paper_trader   [commit 1c4753b]

**Context:** Task 1 of the post-findings plan (advisor-ordered alert → overlay →
classifier). The alert makes no statistical claim, so it ships fast and safe.

**Did:** `trump_alert.py` — classifies live-feed posts into tiers (A =
directive/reassurance, B = china/tariffs, C = other relevant), writes graded
alerts to `state/alerts.jsonl` (already read by the status dashboard). Wired a
rate-gated `check_and_alert()` into the paper_trader tick loop (observational,
never touches positions). Tightened the noise filter to drop congressional
endorsement spam; **alerts limited to Tier-A/B only** (C was drowning in noise).

**Tested:** `--check-once` against live feed — today's posts are all endorsements,
correctly produce zero A/B alerts. Apr-9 directive still classifies correctly.

**Decided:** alert-only, no auto-trade (guardrail: paper/research only).

## 2026-06-02 — Vol overlay: built, validated, REJECTED   [commits 3d9d813, 4637ec3]

**Context:** Task 2 — use the robust 1–4h vol finding as a *risk overlay* (not
alpha): suppress new entries during the post-burst elevated-vol window. Added an
`entry_filter` hook to the backtester; `trump_overlay.py` marks the 4h window.

**Tested:** `_val_trump_overlay.py` — 10 disjoint annual windows, breakout
strategy with vs without the overlay. Found a bug first (filter forced exits
in-position → 80-130 trades vs 2-7); fixed to suppress flat-position entries
only. Clean result: **delta Sharpe ≈ 0.000 in nearly every window** — same
trades, same Sharpe.

**Decided / Dead-end:** **REJECTED.** User correctly called this out as testing
the wrong thing — breakout trades on 40-bar price channels and only fires 2-7
times/year; a 4h window covering ~1-4% of bars almost never coincides with an
entry. Gating a price-channel strategy by Trump windows is meaningless. The
overlay machinery (`entry_filter` hook) stays as reusable plumbing; the claim
that it *helps* does not. The right idea — a strategy that fires *because* of a
post — is deferred into the bigger ML program below.

## 2026-06-02 — Reframe: full ML program (Phases 1–3) + toolchain   [commits b28dcb8, 0309e2a]

**Context:** User reframed the whole effort ("more AI than red/green"): (1)
timeline ALL posts, classify + rerank for ±signal; (2) regress reactions of all
assets + macro against the timeline with proper ML; decide if post-event trades
have value; (3) generate metrics to later predict *when* he makes these counter-
intuitive announcements. Session switched to Opus + ultracode.

**Decided (toolchain):**
- **Hybrid classification.** Local bulk (FinBERT market-aware sentiment +
  MiniLM embeddings/novelty) on all 27k text posts — free, unkillable, runs on
  the box (RTX 2070 present but PyPI torch is CPU; one-time cached run ~30-45min,
  acceptable). Plus **OpenAI gpt-4.1-mini** for the ~2.7k hard market-relevant
  cases where Trump's idiom matters — user gets 250k free tokens/day, so the LLM
  layer is **budget-aware, batched (~20/call), checkpointed per batch** so a
  daily-cap cutoff loses at most one batch (honors the `no-long-workflows-usage-
  limit` lesson — no agent fan-out, no usage burn).
- **Hard gate against lookahead:** all labels are **text-only**. A post's ±score
  must never see the return that followed, or Phase 2 becomes circular (the
  bollinger trap in ML clothing). Validation gate before Phase 2: the classifier
  must read Apr-9 directive bullish and china/tariff bearish.
- **Phase 3 reframed:** n=2 directives is not trainable. Deliver *condition
  characterization* (the Apr-9 template: market stress → bullish directive →
  policy reversal hours later) + stand up live collection so N grows. The
  predictive model is a follow-on.

**Did:** `trump_signal_local.py` (FinBERT+novelty), `trump_signal_llm.py`
(budget-aware OpenAI), `trump_signal.py` (merge + validation gate). Added a
`research` optional-deps group (torch/transformers/sentence-transformers/sklearn/
lightgbm/openai); `uv sync --extra research`.

**Tested:** local pipeline smoke test (200 posts) — works; FinBERT reads
market-relevant posts **−0.05** vs VADER **+0.31** (the market-calibration we
wanted). Full 27k run launched (CPU, in progress).

**Aside:** evaluated **Fincept Terminal** (open-source C++/Qt finance terminal).
Useful as an MIT-licensed reference for FRED/IMF/WorldBank connectors (HANDOFF
thread #6) and a possible future UI — but it's a desktop app, not a library, and
off the critical path. Bookmarked, not adopted.

**Next:** finish local run → run LLM layer → merge → **validation gate** →
Phase 2 (purged/embedded-CV regression of all assets+macro on the signal).

<!-- worklog:end-of-seed -->

## 2026-06-02 22:41 UTC — Documentation system + paper-planning scaffold   [commit 895c1a8 + pending]

**Context:** User revealed the end goal — write this up for **publication**,
with the user as lead and AI doing most of the execution, sharing credit. That
raises the bar to peer-review standards and is *why* a full method trail matters.
First they asked for automatic documentation of every twist/turn/decision; then
they clarified the target: a **technical thesis** ("more tech than finance"),
with the **AI-augmentation angle** as the primary interest, delivered at
**three levels — bachelor's, master's, PhD.**

**Did:**
- **Work-log system** (895c1a8): `/worklog` skill (`.claude/skills/worklog/`)
  that reads the conversation and appends structured entries to
  `docs/WORKLOG.md`; a `post-commit` git hook (`scripts/post-commit` →
  `.git/hooks/`) that records a deterministic commit spine to gitignored
  `state/commit_log.tsv`; seeded WORKLOG with the full session history; memory
  feedback `worklog-commit-ritual` so the ritual survives sessions.
- **Paper scaffold** (`docs/PAPER/`): `PREREGISTRATION.md` (frozen Phase-2 plan),
  `RELATED_WORK.md` (lit positioning), `OUTLINE.md` (journal-paper view),
  `THESIS_STRUCTURE.md` (IMRaD/CS-thesis skeleton + the three-tier mapping + the
  AI-augmentation treatment).

**Tested:** post-commit hook fired on its own commit (895c1a8) and correctly
wrote the spine line to `state/commit_log.tsv` — system verified end-to-end.

**Decided (with rationale):**
- **Skill, not agent**, for the narrative log: a subagent starts cold without the
  conversation, so only a model-run skill can extract decisions from the chat.
  Hook handles the automatic trigger; skill handles the reasoning. Run `/worklog`
  *before* committing so the entry lands in the same commit (no dirty-tree loop).
- **Pre-registration frozen NOW**, before Phase-2 results — the git timestamp is
  the credibility. Froze: signal def, asset+macro lists, 1/4/24h horizons,
  purged+embargoed walk-forward CV (embargo = 24h), the era+trailing-vol-quintile
  null, **BH-FDR q=0.10** (primary) + Romano-Wolf (robustness) multiple-testing
  correction, and the OOS tradeable-edge rule (net-of-cost Sharpe CI lower bound
  > 0 on the final-20%-by-time holdout).
- **Phase 0 = exploratory, Phase 2 = confirmatory.** Advisor flagged that the
  WORKLOG itself documents specification search (the `liberation day` keyword was
  added after seeing Apr 2; `market_directive` after the user pointed at Apr 9),
  so the event-study results must be labelled hypothesis-generating, not confirmed.
- **Authorship honesty:** an AI cannot be a named author (arXiv/ICMJE/Nature/
  Science policy); humans author, AI assistance is disclosed in methods/ack.
  Told the user up front rather than at submission.
- **Three tiers as a layered superset**, not three documents: bachelor's
  (single-asset, standard methods — ~in hand post-Phase-2), master's (full ML
  pipeline + multi-asset + timing control + purged CV + FDR + tradeable-edge —
  the realistic target), PhD (full program + AI-methodology contribution +
  breadth — aspirational; the single 1–4h vol finding is NOT PhD-sized, said so).
- **AI-augmentation = capability augmentation, not autonomous science.** The
  WORKLOG's human-direction-vs-AI-execution division of labour is the *evidence
  base* for that claim. Finance result → q-fin/SSRN; AI-augmentation story → an
  AI/meta-science venue; they coexist as a reflective thesis chapter.

**Dead-ends / caveats:** "first rigorous study" claim **killed** by a targeted
SSRN/arXiv search — **David Krause** has several Trump-and-crypto event-study
working papers. Repositioned our niche as the differentiators Krause lacks:
intraday (1–4h) resolution, systematic full-corpus ML classification (vs hand-
curated events), volatility + the clustering caveat, and the endogenous-timing
control. The advisor also downgraded the "validation gate" to a build-consistency
smoke test (near-tautological — the directive class was built to catch Apr 9), so
it must not be cited as evidence of predictive skill.

**Next:** finish the in-flight local FinBERT/embeddings run → LLM hard-case layer
→ merge → the (smoke-test) validation gate → execute the pre-registered Phase 2.
Open author decisions noted in `THESIS_STRUCTURE.md` (primary tier, AI-chapter
placement, venue, byline).

## 2026-06-02 22:50 UTC — Phase 1 execution: local layer complete, LLM layer validated + launched   [commit ab9f1a3 + pending]

**Context:** Run the frozen Phase-1 signal pipeline at full scale to produce the
text-only event signal the pre-registered Phase 2 needs.

**Did / Tested:**
- **Local layer complete** — FinBERT + MiniLM embeddings + causal 7d novelty on
  all **27,387** text posts (`trump_signal_local.parquet`, `trump_embeddings.npy`
  27387×384). ~1h on CPU (PyPI torch is CPU-only; RTX 2070 unused — acceptable
  one-time cached cost).
- **FinBERT sanity vs known events:** china **−0.152** (bearish ✓), crypto
  **+0.157** (✓), market_directive **+0.477** (✓), Apr-9 directive **+0.169**
  (mild), **tariffs +0.000** (FinBERT misses that tariffs are risk-off). The
  weak spots (tariffs, mild directive) are exactly the LLM layer's job. On
  market-relevant posts FinBERT mean **−0.012** vs VADER **+0.370** — the
  market-calibration upgrade confirmed at scale.
- **LLM hard-case layer validated** (gpt-4.1-mini, 40-post smoke test, ~3.0k
  tokens/batch): **"THIS IS A GREAT TIME TO BUY!!! DJT" → stance +2, conviction
  1.0, is_market_directive=True** (vs FinBERT's mild +0.17 — the LLM reads the
  maximal directive). "MARKETS going to BOOM" → +1/directive; "calls for Fed
  rate cuts" → +2/directive+policy; china "hit much harder than USA" → +1
  (correct nuanced read: China losing = bullish US); noise/political → 0/conv 0.
- Added **priority ordering** to the hard-case selector (`ab9f1a3`): directives/
  reassurance → Phase-2 topics → low-FinBERT-confidence → novelty, so a
  budget-truncated run covers the most paper-relevant posts first (not a random
  subset).
- **Full budgeted run launched** (background): 1,851 market-relevant non-noise
  posts; ~93 batches × ~3k tok ≈ 281k > the 240k/day free cap, so it processes
  ~80% today, checkpoints to `trump_signal_llm.jsonl` (resumable, skips done
  ids), and finishes tomorrow.

**Decided:** hybrid confirmed correct — FinBERT handles bulk directional
sentiment; LLM supplies the idiom/directive nuance FinBERT can't (tariffs,
maximal buy-directives). Budget-aware checkpointing chosen over a one-shot run so
the daily free-tier cap cannot lose progress (honors the usage-limit lesson).

**Dead-ends / caveats:** none new. Note the mixed labelling (LLM where available,
FinBERT otherwise) is a disclosed methodological seam, already in the
pre-registration's blended-signal definition.

**Next:** while the LLM run completes (today/tomorrow), build the Phase-2
confirmatory harness implementing `PREREGISTRATION.md` exactly (OLS+clustered SEs
with trailing-vol control; LightGBM with purged/embargoed CV; BH-FDR; OOS
tradeable-edge). Build it BEFORE seeing results (reduces researcher DOF); the
real confirmatory run is gated on signal completeness — do not run on partial
signal and report as confirmatory.

## 2026-06-02 23:05 UTC — Phase 2 harness built (gated) + nested publication roadmap   [commit pending]

**Context:** (1) Build the confirmatory analysis code against the frozen
pre-registration while the LLM signal completes. (2) Lead author set the overall
publication strategy — a nested escalation across rigor tiers.

**Did:**
- **`_phase2_reaction.py`** — implements `PREREGISTRATION.md`: burst-level panel
  from `trump_signal.parquet`; per-asset OLS `target ~ signal + novelty + topic
  dummies + trailing_vol_24` with day-clustered SEs; BH-FDR (q=0.10) across the
  whole p-value grid; OOS tradeable-edge (final 20% by time, sign(signal) rule,
  net of 0.24% cost, block-bootstrap Sharpe CI). Two run modes: `--smoke`
  (mechanical test on partial signal → scratch file) and `--confirm` (real run;
  **refuses unless LLM coverage ≥ 95%** of market-relevant posts). Syntax-checked;
  not yet run (signal incomplete).
- **`docs/PAPER/ROADMAP.md`** — the nested plan.

**Decided (with rationale):**
- **Build-before-results discipline:** the confirmatory harness is written and
  committed before any Phase-2 number is seen, and `--confirm` is hard-gated on
  signal completeness, so partial-signal numbers can't leak in as confirmatory.
  Reduces researcher degrees-of-freedom — the credibility point for the paper.
- **Nested publication roadmap** (lead author): object track
  undergrad=finance paper (pause/ship) → master's=AI-boost paper → PhD=unified
  thesis (both, designed from the undergrad submission); plus a conditional meta
  track (the *process* as its own research object) if the PhD lands. Adopted with
  four guard-rails: (1) each tier ships independently — lower tiers NOT contingent
  on the PhD; (2) the AI-boost track is **robust to a null finance result** (a
  pre-registered null with no p-hacking is a *stronger* augmentation story than
  "found alpha") — the most important property, since Phase 2 will likely be null;
  (3) meta-recursion is optional/aspirational, not load-bearing; (4) the WORKLOG
  is doubly load-bearing (evidence base for both the AI-boost paper and the meta
  track) — validates the documentation system.
- **Grounding:** these are works *at* degree levels of rigor (papers/preprints),
  not enrolled-degree submissions; flagged to keep expectations clean.

**Dead-ends / caveats:** none. LLM run in flight (340 labels so far).

**Next:** let the LLM layer finish (resumes tomorrow at the daily cap) → run
`trump_signal.py` merge → Phase 2 `--smoke` to verify mechanically → when
coverage ≥95%, `--confirm` → draft the undergrad finance paper. Advisor review of
the Phase-2 implementation recommended before the confirmatory run.
