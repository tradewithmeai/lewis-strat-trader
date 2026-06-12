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

## 2026-06-02 23:30 UTC — LLM layer 89% done; gate fixed; signal sign-inversion ruled out; Phase 2 verified   [commit pending]

**Context:** Run the LLM layer to scale, merge, and verify the Phase-2 harness
mechanically while watching for signal-quality problems.

**Did / Tested:**
- LLM layer hit the daily cap cleanly: **1,640 / ~1,851 labels (89%)**, 242,598
  tokens (UTC still 2026-06-02 so the budget guard correctly blocked the last
  ~211 posts; they finish on the next run after UTC midnight). Merged →
  `trump_signal.parquet` (27,387 rows, 1,640 LLM-labelled; signal mean −0.077).
- **Validation gate rewritten** (advisor): the old pass/fail on "china/tariff
  stance must be net-bearish" was **mis-specified** — it conflated rhetorical/
  market-impact stance with the topic's average return sign. Now: check [1]
  (directive labelled correctly) is the only pass/fail (build-consistency,
  near-tautological); [2]/[3] are descriptive. Gate PASSES.
- **Investigated a real worry:** the is_policy_signal split showed escalation
  posts at stance **+0.291** vs commentary **−0.042** — looked like the signal
  was sign-inverted on the market-moving posts (Trump announces tariffs
  triumphantly). **Checked the actual labels:** on the Oct-10-2025 −12% crash,
  the hostile-escalation posts ("China is becoming very hostile", "extraordinarily
  aggressive position") were correctly **−1 (bearish)**; the +2 escalation posts
  are mostly genuinely-bullish content (GDP 4.3% beat, "Record Stock Market").
  Conclusion: **no sign inversion** — the +0.291 is composition (is_policy_signal
  sweeps in good-news posts), and the classifier reads hostile escalations
  bearish and good news bullish. No re-run needed; the advisor's "prompt is fine"
  call holds. (Great paper note: we tested for tone-bias and the classifier is sound.)
- **Phase-2 harness verified mechanically** (`--smoke`, partial signal, scratch
  output — NOT confirmatory): OLS grid + BH-FDR + OOS edge all execute. Caught and
  fixed a gap — `load_bursts` wasn't carrying `is_policy_signal` through burst
  aggregation, so the policy/commentary edge split silently vanished; now prints.
  Smoke result: **no tradeable edge** on any asset/subset (sign(signal) rule loses
  net of 0.24% cost trading every burst) — the anticipated null, on partial data.
- Fixed a `~` on object-dtype-bool bug in the gate (`~True == -2` → KeyError);
  added `.astype(bool)`.

**Decided:** signal stands as-is (no prompt change, no costly re-run) — evidence
ruled out the sign-inversion worry. Phase-2 trading rule kept as pre-registered
(sign(signal), every burst); the policy/commentary split is the informative
secondary lens (advisor). Confirmatory run still gated on ≥95% coverage + a
methodology review.

**Next:** methodology review + deepened literature review via an agent fan-out
(the advisor-recommended pre-confirmatory review, parallelised); LLM layer
finishes after UTC midnight → ≥95% coverage → `--confirm`.

## 2026-06-03 — Agent fan-out review + KEYSTONE: vol effect survives day-block null   [commit pending]

**Context:** User said "fan out agents" (ultracode on). Ran a single-phase
14-agent fan-out (8 literature librarians + 6 methodology critics) to deepen the
related-work and adversarially audit the pre-registered Phase 2 before the
confirmatory run. Then acted on the most consequential critique.

**Did / Tested:**
- **Fan-out** (`paper-lit-and-method-review`, 14 agents, 252 tool calls, 704k
  subagent tokens, ~16min): harvested **65 verified citations** (8 slices →
  `RELATED_WORK_VERIFIED.md`) and **27 methodology issues (14 high, 13 medium)**
  → `METHODOLOGY_REVIEW.md`. Raw result preserved at
  `state/signals/_fanout_review_raw.json`. Kept it a single-phase fan-out + commit
  immediately (no multi-phase mega-workflow) per the usage-limit lesson.
- **Advisor triage:** the decisive critique was that the i.i.d. bootstrap null is
  anti-conservative (understates variance) — which threatens RQ1, the *only*
  positive finding. The advisor said: test RQ1 under a **day-block-resampled
  null** first (it needs nothing — no LLM signal, no 95% coverage); it tells us
  which paper we're writing. Don't fix all 14 (tightening a null changes nothing
  for the already-null RQ2/RQ3); single regime + n=2 + 0.92 co-move are data
  ceilings, not bugs. Drop the strong "confirmatory" claim → exploratory/
  observational (dissolves the temporal-firewall dilemma).
- **Implemented** `null_distribution_dayblock` (reproduces the event's calendar-
  day cluster structure: D substitute days × c_d hours each) + a `vol_balance`
  table, in `_event_study_trump.py`. Re-ran RQ1 on BTC.

**Result — KEYSTONE (the headline survives):** the 1–4h forward-vol effect is
significant under THREE independent specs:
  - vol-quintile-matched i.i.d. null: vol_1h p=0.018, vol_4h p=0.010 (full)
  - day-clustered null: vol_1h **p=0.001**, vol_4h **p=0.005** (full); 2025+ p=0.000
  - cluster-robust regression w/ trailing-vol control: vol_4h +5.2bp p=0.007 (full),
    +6.3bp p=0.015 (2025+)
  The **balance table refutes endogenous timing**: event-hour trail_vol_24
  mean=223bp ≈ pool 225bp — he isn't just posting into already-high vol, yet
  forward vol rises. 24h effect stays dead (clustering). So: **a modest, robust
  1–4h volatility effect; no directional edge (RQ2/RQ3 null)** is the defensible
  spine — we have a (careful, honest) paper.

**Decided:** RQ1 is real and robust → proceed. Reframe the study as
exploratory/observational (not strong-confirmatory) — honest given the data
ceilings, and it dissolves the temporal-firewall problem. Adopt the cheap/
high-leverage fixes (FinBERT-only robustness signal vs the LLM-training-leak;
freeze+hash the label set; pin the LLM snapshot; **placebo-actor** control as the
top addition). Frame FWER/co-movement-collapse/RQ3-gating honestly as
pre-registered choices rather than engineering rigor onto an expected null.

**Dead-ends / caveats:** the day-block null came back *more* significant than the
i.i.d. one — because it relaxes vol-matching (era+clustering only) while the i.i.d.
null is vol-stratum-matched; they differ on two axes. So the **cluster-robust
regression is the primary inference** (properly handles clustering AND the
trailing-vol control); the two nulls corroborate. Reported transparently — do not
cite the day-block p=0.001 as "the conservative number".

**Next:** by-hand dated AMENDMENT to `PREREGISTRATION.md` (keep original frozen):
exploratory reframing + the adopted fixes. Then FinBERT-only robustness rerun +
placebo-actor design. LLM layer finishes after UTC midnight.

## 2026-06-03 01:10 UTC — Pre-reg Amendment 1, LLM layer 100% + frozen, Phase 2 run   [commits 5446391, 4292e24 + pending]

**Context:** Land the amendment, complete + freeze the signal, and run the
(now-exploratory) Phase 2. (Catch-up entry: 5446391 and 4292e24 were committed
with only the hook spine; narrated here.)

**Did / Tested:**
- **Pre-registration Amendment 1** (5446391): original sections 1–8 kept frozen;
  appended a dated amendment — study relabelled **exploratory/observational**
  (data ceilings: single regime, n=2 directives, 0.92 co-move; temporal firewall
  dropped as inapplicable); cluster-robust regression = primary inference, two
  bootstrap nulls corroborate; adopted fixes listed (FinBERT-only robustness,
  freeze+hash labels, separate constructs, placebo actor, BTC-primary,
  directive-gated RQ3); ceilings acknowledged as limitations not engineered around.
- **LLM layer 100%** (UTC rolled to 2026-06-03 → budget reset): last 211 posts
  labelled in 31.9k tokens. **All 1,851 market-relevant non-noise posts covered.**
  Gate PASSES.
- **Froze + hashed the label set** (4292e24): `docs/PAPER/SIGNAL_MANIFEST.json` —
  pinned archive etag, the 3 models, SHA-256 of the LLM jsonl
  (64275ed8…) and merged signal (b9f9d17f…), seed 42. Honest caveat recorded: the
  `gpt-4.1-mini` alias resolved to the 2025-04-14 snapshot but per-call
  system_fingerprint was not captured, so bit-identical repro would need an
  explicit-snapshot re-label.
- **Phase-2 harness amendment-aligned before the real run:** added `finbert_score`
  as a SEPARATE OLS covariate (don't-blend fix); RQ3 edge test now runs BOTH the
  LLM-blended signal AND a **FinBERT-only** signal (LLM-leak robustness), each
  split by policy/escalation; header relabelled EXPLORATORY. Ran `--confirm` at
  100% coverage (result in the next entry / `docs/PAPER/PHASE2_RESULTS.md`).

**Decided:** make the harness amendment-compliant BEFORE writing the real results
file, so PHASE2_RESULTS.md is not the un-amended spec. FinBERT-only RQ3 is the
cheap, highest-leverage fix (kills the LLM-leak objection for the directional
claim) — added now rather than deferred.

**Next:** record the Phase-2 result; placebo-actor experiment; begin the undergrad
finance paper draft.

## 2026-06-03 01:20 UTC — Phase 2 result: RQ2/RQ3 NULL (robust, incl. FinBERT-only)   [commit pending]

**Did / Tested:** ran the exploratory Phase 2 at 100% coverage →
`docs/PAPER/PHASE2_RESULTS.md`.

**Result:**
- **RQ2 NULL** — the continuous directional `signal` is insignificant on every
  asset×horizon (all p>0.4); FinBERT-only signal likewise null.
- **RQ3 NULL on all 12 cells** (3 assets × {all,policy} × {LLM,FinBERT}): every
  one loses money net of 0.24% cost (Sharpe −6 to −15). Robust to signal source →
  NOT an LLM-leak artifact.
- **8 BH-FDR "survivors" are ALL `topic_market_directive`** = the n=2 directive
  class (betas +166 to +724bp, p=0.000) — a 2-observation-dummy artifact, reported
  as the case study, NOT confirmed alpha. Added a hand-written interpretation
  header to PHASE2_RESULTS.md so it can't be misread as 8 findings.
- `topic_china` −1h (−8 to −17bp, p~0.02–0.03) present but does NOT survive FDR;
  reported as a consistency check (tariffs risk-off is known), not novelty.

**Decided:** the paper's empirical spine is now complete and clean — **posts move
1–4h VOLATILITY (RQ1, robust), not DIRECTION (RQ2/RQ3 null after costs)**; the
"buy" directives are an n=2 case study. This is the honest, publishable result
the project's whole methodology was built to reach (and the AI-boost narrative is
robust to it — a pre-registered null with no p-hacking).

**Next:** placebo-actor experiment (top remaining robustness — separates "Trump's
text" from "any salient poster"); then draft the undergrad finance paper from
RQ1 (positive) + RQ2/RQ3 (null) + the directive case study.

## 2026-06-03 01:35 UTC — Content placebo: vol effect is market-content-specific   [commit pending]

**Context:** Run the methodology-review's top addition — a placebo control to
separate "Trump's market *content* moves vol" from "any Trump post / time-of-day
coincides with vol".

**Did:** added `load_bursts(placebo=True)` + a `--placebo` mode to
`_event_study_trump.py` that runs the IDENTICAL vol pipeline on Trump's
NON-market-relevant non-noise posts (7,232 bursts — 5× the 1,422 treatment, so
higher power) → `docs/PAPER/PLACEBO_RESULTS.md`. Guarded the topic-dummy
regression against all-zero columns (placebo leaves them False).

**Result — content-specificity confirmed:** under the primary cluster-robust
regression, the placebo is NULL on all vol horizons (vol_4h +1.0bp p=0.232 full,
+1.6bp p=0.214 2025+; vol_1h +0.5bp p=0.390) vs treatment (+5.2bp p=0.007 full,
+6.3bp p=0.015 2025+). ~5× effect-size gap. Vol-matched i.i.d. null agrees
(placebo p=0.30–0.97). Trailing vol balanced (placebo event 224bp ≈ pool 228bp).
→ the 1–4h vol effect is the market CONTENT, not "Trump posted" or time-of-day.

**Methodological by-catch:** the day-block null flagged placebo vol_1h at
p=0.014/0.049 on a negligible +0.4bp gap — **the day-block null is
anti-conservative at large n** (tiny SE over 7,229 bursts). This confirms
Amendment 1's choice of the **cluster-robust regression as PRIMARY** and demotes
the day-block null to a sanity check (logged in PLACEBO_RESULTS.md). The placebo
audited the inference method, not just the finding.

**Dead-ends / caveats:** this is a *content* (within-actor) placebo. A
*different-actor* placebo needs a clean second high-salience feed (Musk = a
positive not negative control), none readily available → logged as future work,
stated as a limitation rather than forced.

**Next:** draft the undergrad finance paper — RQ1 (vol effect, robust + placebo-
confirmed content-specific) + RQ2/RQ3 (null, incl. FinBERT-only) + directive
n=2 case study.

## 2026-06-03 02:00 UTC — Progress tracker + dashboard view + nightly sign-off routine   [commit pending]

**Context:** User reframed toward a build-in-public dissertation: each night at
sign-off, update the day's progress and plot it along an undergrad → master's →
PhD timeline, published in the web UI. (Bigger vision — public UI for crowd-
sourced strategy tests, a faceless crypto-numbers video service via their social
studio, VPS+GPU deploy with an autonomous collector agent — acknowledged but
deliberately deferred; dissertation first.)

**Did:**
- `docs/PAPER/progress.json` — three-tier milestone model (status done/active/todo
  + dates), accurate to reality: **undergrad 83%** (7/9 done — analysis complete,
  only draft + submission left), master's 12%, phd 0%.
- `dashboard.py` — new **Research Progress** view (first tab): per-tier completion
  bars, cumulative-milestones-over-time line, and per-tier milestone tables.
  Syntax-checked; progress.json drives it.
- `.claude/skills/signoff/SKILL.md` — `/signoff` nightly routine: runs the
  worklog narrative, refreshes the progress tracker (conservative — `done` only
  when committed+verified), commits, prints an end-of-day summary (tier %s + the
  one thing queued next). Composes with `/worklog`.

**Decided:** keep the progress tracker honest/conservative (it's published —
understating beats overstating); make Research Progress the default dashboard tab
so the build-in-public timeline is the first thing a visitor sees.

**Next:** undergrad paper draft (the active milestone u8); the `/signoff` routine
now records each day onto the published timeline.

## 2026-06-03 23:30 UTC — VPS migration kit + first remote push   [commit 80efaca]

**Context:** User asked if we're ready to move to a VPS (with cloud GPU) for the
build-in-public phase. Assessed readiness and cleared what could be done without
the box yet.

**Did / Tested:**
- Readiness check: 29 commits were unpushed; confirmed **no secrets tracked**
  (`.env` is not in the repo — the OpenAI key is an env var; only `.env.example`
  is tracked). Confirmed the Trump pipeline is **API-self-sufficient** (CNN
  archive download + Binance klines), so the multi-GB lake does NOT need copying
  for the dissertation work — only the strategy system (`paper_trader`/`reflect`)
  needs it.
- `docs/VPS_SETUP.md` — bootstrap kit: clone + `uv sync --extra research`, the
  CUDA-torch swap for GPU, env vars (LAKE_ROOT required at import even for klines
  fallback), deterministic signal regen from the pinned archive w/ manifest
  hash-check, run commands, the two-residents split (Claude analyst + Hermes
  collector), and the security rules (paper-only, detached supervised processes).
- **Pushed all 30 commits to `origin/main`** (the session's entire body of work
  is now backed up remotely). First push attempt was correctly blocked by the
  harness (direct push to default branch, unauthorized); proceeded once the user
  explicitly authorized.

**Decided:** GPU move is worth it — FinBERT ~2min vs ~40, and we can move LLM
classification fully local to drop the OpenAI 250k/day cap AND fix the
alias-reproducibility caveat. Don't copy the lake for dissertation work (APIs
suffice). Lake sync only if the strategy system runs on the VPS too.

**Dead-ends / caveats:** the VPS move is gated on details only the user has —
which Hermes agent (install docs), VPS OS/GPU specs, and how Claude Code is
launched there. Logged in VPS_SETUP.md §9; no box yet (user setting it up soon).

**Next:** undergrad paper draft (milestone u8). VPS bootstrap when the box exists.

## 2026-06-04 20:29 UTC — Undergraduate paper: full IMRaD first draft   [commit f622ef9]

**Context:** User: "do the undergrad paper draft now" → "continue". This is the
active milestone u8 — the last analytical work (RQ1 effect, placebo, RQ2/RQ3 null,
directive case study, methodology review, verified citations) was already done, so
the task was to assemble it into a publishable finance paper, not to run new
experiments.

**Did:**
- `docs/PAPER/UNDERGRAD_PAPER.md` — complete IMRaD draft. Title: *"Posts as
  Events: Intraday Cryptocurrency Volatility Around a Head of State's Social-Media
  Communications."* Sections: Abstract; 1 Introduction (three episodes, RQ1/2/3,
  four contributions); 2 Related work; 3 Data; 4 Signal construction (text-only);
  5 Method (cluster-robust regression = primary inference, two corroborating
  nulls, balance table, BH-corrected RQ2/RQ3, block-bootstrap Sharpe CI); 6
  Results (6.1 RQ1 vol effect, 6.2 content placebo, 6.3 RQ2/RQ3 null, 6.4
  directive case study n=2, 6.5 macro panel); 7 Discussion/limitations; 8
  Conclusion; Reproducibility & disclosure; References.
- Headline numbers carried verbatim from the frozen results: BTC event dummy
  **+3.06 bp @1h (p=0.018)**, **+5.18 bp @4h (p=0.007)**; 24h null (−0.89 bp,
  p=0.795); placebo 4h +1.04 bp (p=0.232) on 7,232 bursts (~5× treatment, no
  effect); RQ2/RQ3 directional null (all p>0.4; OOS Sharpe ≈ −6 to −15 across all
  12 cells incl. FinBERT-only); directive case study n=2 (9 Apr "GREAT TIME TO
  BUY", BTC ~+5.6% @4h).

**Tested:** No new computation — advisor review of the draft, not a re-run. Advisor
verdict: "strong draft… don't rewrite it," flagged two presentation blind spots,
both of which are edits to how existing results are reported:
1. **Placebo 24h omission** — §6.2 originally said "no volatility effect" but the
   placebo's 24h coefficient is significantly *negative* (−5.39 bp, p=0.004).
   Fixed: now reported explicitly as an unexplained opposite-sign large-sample
   artefact, not interpreted as a post effect, and noted to mirror the treatment's
   own null 24h coefficient (−0.89 bp).
2. **Nominal p-values** — RQ1 headline p-values were reported without stating they
   are uncorrected. Fixed: added a framing note at the top of §6 — p-values are
   nominal except RQ2/RQ3 (Benjamini–Hochberg); the RQ1 multiplicity safeguard is
   *consistency* across 2 horizons × 3 assets × 2 nulls + the placebo contrast,
   read in the exploratory/observational spirit, not a corrected threshold.

**Decided:** Apply both fixes as presentation edits rather than re-opening the
analysis (advisor: "edits to how you present results you already have — not new
experiments"; "don't rewrite it"). Marked **u8 done** (draft complete + committed),
kept **u9 (public submission) open** — conservative per the published-tracker rule.
Resisted expanding scope: the draft stands on the evidence already in hand.

**Dead-ends / caveats:** The draft deliberately frames RQ1 as a volatility/timing
signal, *not* an alpha source (effect is ~5–8% relative vol rise, untradeable per
RQ3); the directive class is an n=2 case study with no statistical inference. These
are honesty guards, not findings to be strengthened later without more events.

**Next:** u9 — public submission (arXiv q-fin / SSRN): needs an author/affiliation
+ AI-authorship disclosure decision from the user before posting. Master's tier
(AI-boost paper, m1/m2) is the next analytical front.

## 2026-06-04 21:12 UTC — Submission package: citable-record route + Overleaf/SSRN artifacts   [commit pending]

**Context:** User's end goal is publishing; immediate target chosen = a public
*citable record* of the undergraduate paper. No local LaTeX/pandoc on the box.

**Did:**
- Installed pandoc ephemerally via `uv run --with pypandoc-binary` (39 MB bundled
  binary, no system/admin install). pandoc 3.9.
- Generated `docs/PAPER/submission/paper.tex` (standalone, real \title/\author/
  \date block) and `paper.docx` from `UNDERGRAD_PAPER.md`, stripping the internal
  draft-status scaffolding and adding a title/author(TBD)/date metadata block.
- `docs/PAPER/SUBMISSION.md` — the route, lowest-friction first: **OSF** (register
  the pre-registration → DOI) + **Zenodo** (DOI from a GitHub release or PDF) →
  **SSRN** (PDF from the .docx; JEL G14/G12/C58) → **arXiv** q-fin.ST/TR (later;
  endorsement hurdle) → journal (optional). Plus the human-only gates: author
  name/affiliation, AI-assistance disclosure wording, license, venue choice.
- `progress.json`: u9 (public submission) todo → **active** (artifacts + checklist
  exist; actual posting gated on the human-only decisions).

**Decided (advisor-guided):**
- Don't hand-convert and don't install system LaTeX — use `pypandoc-binary`.
- **Compile with XeLaTeX, not pdfLaTeX** — the paper is full of unicode (en-dash,
  ×, ≈, "bp") that pdfLaTeX rejects. Documented in SUBMISSION.md.
- Keep references a **formatted list**, not BibTeX \cite machinery — BibTeX is a
  journal-submission concern, not needed for a citable record.
- **Decouple the citable record from LaTeX:** OSF/Zenodo give a DOI with zero
  conversion, so they go first; arXiv (LaTeX + endorsement) is step-2, not the
  gate.

**Dead-ends / caveats:** arXiv q-fin needs first-timer endorsement or an
affiliated email — flagged as the one step that can block. The submission is
gated on human-only decisions (author identity, disclosure wording, license);
nothing posts until the user supplies those.

**Next:** user supplies author/affiliation + disclosure wording + license; then
OSF pre-reg + Zenodo DOI, then SSRN.

## 2026-06-04 23:13 UTC — Web UI made publicly deployable (build-in-public surface)   [commit pending]

**Context:** User pivoted priority: get the website/web UI up and running now,
papers stay on file (multiple papers planned — be tactical about content split).
Keep the existing monitors running + logging, don't disrupt them. "Web UI up
before we publish."

**Did:**
- Treated the existing Streamlit `dashboard.py` as the site (per advisor: plain
  reading; "public Streamlit UI" was already the deferred vision, no new narrative
  site). Made it dual-mode via `LAKE_AVAILABLE = Path(LAKE_ROOT).is_dir()`:
  - **public view** (no lake) = Research Progress (hero) + Traffic Light only;
  - **local** = full 5-tab strategy lab.
  Hid the three lake-backed tabs (Equity Curves / Walk-forward / Trade Log) in
  public mode — Equity Curves called `load_bars_cached` *outside* its try and
  would hard-crash a lakeless host. Added a public-view sidebar note + a landing
  intro on the Research Progress tab.
- `requirements.txt` (core deps only, no torch/research) for Streamlit Community
  Cloud, which installs from it not pyproject. `.streamlit/config.toml` (dark
  theme). `docs/DEPLOY.md` — Community Cloud steps + human-only actions.

**Tested:**
- **Import viability (make-or-break):** `local_system.strategies.registry`
  imports with NO `LAKE_ROOT` and does NOT transitively pull `lake_adapter`
  (which raises on missing `LAKE_ROOT`). So the landing app loads on a lakeless
  host; the adapter only raises lazily inside the lake tabs. Public deploy
  reachable without a registry refactor.
- **Headless boot (streamlit AppTest, both modes):** public mode →
  `exception: NONE`, radio = ['Research Progress','Traffic Light'], intro present;
  local mode → `exception: NONE`, radio = all 5 tabs. (A trailing traceback in the
  run was the test's own print() choking on the '→' glyph in the cp1252 console,
  not an app error — at.exception was NONE.)
- Verified stack: streamlit 1.57.0, plotly 6.7.0, pandas 3.0.3, statsmodels 0.14.6.

**Decided (advisor-guided):**
- Default host = **Streamlit Community Cloud** (free, public, GitHub-linked — fits
  build-in-public, no VPS needed). The deploy clicks (account, repo authorise,
  app name) are human-only; handed off in DEPLOY.md, same pattern as the paper.
- **Pin render-critical deps** (streamlit==1.57.0 etc.): `use_container_width` is
  deprecated and slated for removal post-2025-12-31, so an unpinned newer
  streamlit could break the live app. Pin to the AppTest-passing versions; bump
  deliberately. (Did NOT migrate the 11 `use_container_width` call sites to
  `width=` — pinning locks verified behavior with far less edit risk; migration
  is a known follow-up if/when unpinning.)
- **Monitors untouched:** paper_trader tick loop / trump_alert / cli.status left
  exactly as-is; the dashboard only reads their committed output. Read the
  instruction as "don't disrupt logging," not a new build.

**Dead-ends / caveats:** lake-backed tabs can't be public without a host that has
the lake synced (VPS path) — out of scope for the free deploy. `state/comparison.json`
is gitignored, so Traffic Light shows its degraded note on the cloud (expected).

**Next:** user does the Community Cloud deploy clicks → public URL. Then: be
tactical about how the planned multiple papers split content (parked in memory).

## 2026-06-11 22:46 UTC — VPS migration plan: cost-aware architecture   [commit 13cb9cf]
**Context:** Publishing parked ("stop trying to publish; we have other work").
Pivot to launch: stand the system up on a VPS and put the dashboard on the website
at `stratbot.solvx.uk`. No box exists yet — this session is the architecture +
decisions, gated on the human creating the box.

**Did:** Wrote `docs/VPS_MIGRATION_PLAN.md` (companion to VPS_SETUP.md). Measured
the constraints first: ran the dashboard locally to confirm it serves
(localhost:8501), then sized the data — the price lake is **11.45 GB across
~2,039,958 parquet files**. Settled the placement: a lean always-on CPU box
(dashboard public-view + Hermes collector + Claude Code analyst, NO torch/lake),
RunPod hired per-hour for GPU-class signal regen, desktop stays the lake's home.

**Tested:** `streamlit run dashboard.py` → served on :8501 (full lab locally since
the lake is present); stopped after verifying. Lake footprint measured via
recursive size scan (2.04M files / 11.45 GB).

**Decided (with rationale):**
- **Hosting:** Krystal (free credit) now → **Hetzner 8 GB @ $10.99** after free
  period (4 GB @ $5.99 austerity fallback). Krystal's RAM is expensive; Hetzner is
  the sustainable home.
- **Collector = Hermes Agent** (Nous Research, MIT, github.com/NousResearch/hermes-agent).
  Verified the installer (fetched install.ps1): user-scoped, no admin, no telemetry,
  pulls from standard sources; bundles uv+Python+Git+Node22+Playwright Chromium.
  On Linux use **install.sh** not the advertised `.ps1` (Windows-only). Chromium's
  300 MB–1 GB RAM appetite is what fixes the tier at 6–8 GB.
- **Lake bridges, sized to consumer:** (1) results → VPS **via git** (desktop
  computes lake-dependent jobs, commits artifacts, dashboard renders — the only
  bridge the public dashboard needs); (2) lake **slice** → RunPod on demand via
  tar / a Tailscale slice-server. No dedicated lake VPS.
- **Subdomain:** `stratbot.solvx.uk` via nginx reverse-proxy + Let's Encrypt.

**Dead-ends / caveats:**
- **Binance klines fallback is invalid** (VPS_SETUP §5 notwithstanding): the lake
  is **second-resolution** data and klines are 1-min bars — they cannot substitute
  for the sec/sec analysis. So the VPS never runs the event study/`reflect`; those
  stay where the lake (or a bridged slice) is. Corrected throughout the plan.
- First assumed "no Hermes exists, just cron the repo's `trump_archive.py` puller."
  Wrong — Hermes is a real Nous Research agent with a one-step installer. Reverted.
  (The CNN-mirror puller still matters: a missed Truth Social pull is backfillable
  from the archive, so Hermes' higher-value arm is the *headline* scrape, which has
  no upstream archive.)
- Considered syncing the lake to the VPS / a dedicated lake VPS — rejected on cost
  (duplicating 11.45 GB + 2M files) in favour of the git+Tailscale bridge.

**Next:** human gate — create the box (Krystal 6 GB) + add `stratbot.solvx.uk`
DNS A record once it has an IP; send the Hermes LLM-backend key for `hermes setup`.
Then execute: lean install → systemd dashboard + nginx/TLS → Hermes collector →
nightly /signoff cron.

## 2026-06-12 01:39 UTC — VPS live: both dashboards public, collector running   [commit 697d1a9]
**Context:** Execute the migration. Krystal 6 GB Ubuntu 24.04 box provisioned
(185.44.253.199, user `kc-user`, passwordless sudo). Mid-way the user widened the
goal: don't just bridge results — **move the whole crypto lake to the VPS, run the
full crypto-lake-rs collector there, expose the lake to a few users, retire local.**

**Did (in order):**
- **SSH:** dedicated `id_ed25519_stratbot` key (passphrase, in agent). Krystal's
  template injects org keys but ours wasn't among them; installed it via the
  root-password path. Hardened: drop-in `00-stratbot-hardening.conf` (sorts ahead
  of Krystal's `10-template-spec.conf` which set `PasswordAuthentication yes`),
  password auth off, `PermitRootLogin prohibit-password`. Verified key-only works,
  password refused.
- **Base + dashboard:** apt git/python/nginx/certbot (no torch); cloned
  lewis-strat-trader via read-only deploy key; lean venv from requirements.txt (65
  pkgs, no torch); `stratbot-dashboard` systemd unit (streamlit 127.0.0.1:8501);
  nginx reverse-proxy + Let's Encrypt → **https://stratbot.solvx.uk** (public view).
- **crypto-lake-rs:** installed Rust; cloned via a second deploy key + `github-lake`
  host alias; `cargo build --release` (needed `pkg-config`+`libssl-dev` for
  openssl-sys; added a 4 GB swapfile as a build cushion). VPS `config.yml` with
  **betty disabled**; systemd `cryptolake` unit running
  `--no-tray --retention-days 0`. All 3 exchanges streaming; dashboard/API on :8000.
- **Full strategy UI:** discovered a fresh lake makes the collector's startup
  backfill skip (no anchor); used `--deep-backfill` to rebuild **1m history from
  Binance** directly — no file transfer. Pointed the dashboard's `LAKE_ROOT` at
  `~/crypto-lake-rs/data/parquet`; smoke-tested `load_bars` (5,760 1m rows → 96 1h
  bars, real BTC prices) → Equity/Walk-forward/Trade-log tabs now render.
- **Lake access:** **https://lake.solvx.uk** — nginx vhost → :8000, HTTP basic auth
  (user `lake`), Let's Encrypt TLS. Verified 401 without creds, 200 with, HTTP→HTTPS.
- **Security:** crypto-lake-rs binds `0.0.0.0:8000` and was **publicly reachable
  unauthenticated** — closed it with ufw (allow only 22/80/443; verified :8000 now
  times out externally, SSH intact).
- **Hermes:** user ran the Nous installer + `hermes setup` themselves (key off-chat);
  agent running. Collector job spec not yet wired.

**Tested:** SSH key-only login + password-refused; `nginx -t` clean; both
`/_stcore/health`=200 and certbot issuance for both subdomains; lake auth gate
(401/200); `load_bars` end-to-end on the box; `--deep-backfill` (4-day sample =
5,760 bars in ~3 s); ufw external :8000 = timeout.

**Decided (with rationale):**
- **Rebuild 1m history from Binance, don't transfer the lake.** Tarring the
  11.45 GB / **2,039,958-file** lake crawled at ~12 MB/min (~16 h projected) —
  per-file overhead on 2 M ~5.7 KB files. Killed it. `--deep-backfill` gets the 1m
  data the dashboards actually use (they resample to 1h) with zero transfer.
- **Second-resolution archive = Phase 2.** The unique sec/sec data still lives only
  on local; migrating it means the project's `consolidate` tool (lossless, ~1440×
  fewer files) which **rewrites the canonical local lake** — deferred, will confirm
  before running. So **local is NOT yet retired** (no backup taken yet).
- **6 GB tier confirmed** (Hermes bundles Chromium); added swap for the Rust build.

**Dead-ends / caveats:**
- **PowerShell→ssh quoting** repeatedly mangled commands (`\"`, `\$`, `>>` → EOF /
  spaces→`n`). Switched to: write file locally → `scp` → run; this is the reliable
  pattern for anything with quotes/redirects.
- First clone failed — repo is **private** (deploy keys, not public clone).
- `--retention-days` defaults to 3 (purges old raw) → set **0** to preserve history.
- Lake dashboard exposed unauthenticated on :8000 until ufw — caught and closed.

**Next:** wire Hermes' collector job (hourly Truth Social pull + daily headline
scan) once the invocation is known; let `--deep-backfill` finish (history deepens);
Phase 2 — rclone→gdrive backup, optional sec/sec migration, then retire local;
schedule `archive.py consolidate` via cron to keep file count down.

## 2026-06-12 14:23 UTC — System map + Phase 1: live traffic-light comparison on the VPS   [commit 11395d5]
**Context:** With the deployment live, the user asked for a full audit of "what we
actually built" — their mental model needed verifying before trusting a live
system. Then: get the simplest live strategy comparison running today, with the
ambition of an eventual public strategy-test platform (users submit strategies).

**Did:**
- **Code-grounded system map** → `docs/PLATFORM_PLAN.md`. Key corrections to the
  mental model: (1) the project is **two separate tracks** — strategy lab (11
  registered strategies, all pure price TA) and research signal suite
  (futures hourly / macro daily / 5 RSS feeds / Trump) — verified the strategies
  import **no** signals; only seams are the `trump_alert` notification in
  paper_trader and a commented vol-overlay hook in backtester. (2) Macro is
  **daily** (not hourly); futures are the hourly feed. (3) 13 Binance symbols
  (not 12) + Coinbase/Kraken at 1m. (4) The paper is **volatility** × Trump posts
  (1–4h vol effect), not volume/direction. (5) The live comparison was **not**
  running on the VPS until today — the box had only collector + dashboards.
- **Backfill hardening:** the all-symbol deep-backfill had been launched attached
  to the SSH session and died twice on connection resets (only BTC+ETH finished
  overnight — 2,355 days each). Relaunched as transient systemd unit
  `deep-backfill.service` (resumable: re-run skipped 2,354 done days). Still
  running through the remaining symbols.
- **Phase 1 — live comparison:** ran `cli.reflect --symbol BTCUSDT --years 3` on
  the box as a detached unit (~4.5 min): loads 1m → 1h, walk-forward (fit first
  80%, trade last 20% ≈ 7 months OOS), scores active + 10 challengers, writes
  `state/comparison.json`. Installed `reflect-daily.timer` — **once daily 00:20
  UTC, Persistent=true**.
- **End-to-end browser verification** (Playwright on the live public URL): Traffic
  Light tab renders the real comparison — daily_swing 0.332, ensemble/
  mtf_confluence 0.300, bollinger 0.296, regime_bb 0.270 vs ⭐ active breakout
  0.251; ema_crossover 0.072, mtf_ls 0.080, rsi_meanrev 0.114, mtf_bb_vol 0.217.
  Five challengers' `days_beating=1` — promotion clocks ticking.

**Tested:** reflect unit ran to completion (journal + valid comparison.json);
dashboard `load_comparison` has ttl=30s so no restart needed (verified rendering
in-browser); timer listed with next fire 2026-06-13 00:20 UTC.

**Decided (with rationale):**
- **Cadence = exactly once/day, enforced by timer:** `update_traffic_light`
  increments `days_beating` per RUN with no same-day guard — manual on-box reflect
  runs would double-count the promotion clock. Documented in the unit + script.
- **00:20 UTC** so the cycle sees a complete "yesterday" (reflect's end date is
  today−1).
- Phase order locked in PLATFORM_PLAN.md: simple live comparison TODAY → Hermes →
  advanced/signal-driven strategies → public platform (user-submitted strategies =
  untrusted code → must sandbox; flagged as the central design problem).

**Dead-ends / caveats:**
- **Do-nothing quirk:** `ensemble` traded 0 times in the OOS window yet scores
  0.300 (full drawdown component) and "beats" the active — a cash-sitter can climb
  to GREEN in flat/bear regimes. Left as-is for v1 (capital preservation is
  defensible); queued for the Phase-3 scoring review.
- The attached-SSH backfill failure cost the overnight window — lesson recorded
  (always `systemd-run`/`nohup` long remote jobs from the start).
- PowerShell→ssh quoting struck twice more (`$(seq …)` executed locally; `\"`
  parse errors) — script-file-then-scp is now the standing pattern.
- GREEN alert's desktop toast is Windows-only (win10toast, try/except-guarded) —
  on Linux the `alerts.jsonl` write is the alert channel.

**Next:** Hermes collector job spec; backfill completes on its own; Phase 2
(rclone backup → optional sec/sec migration → retire local); Phase 3 scoring
review + advanced strategies; sandbox design for the public platform.
