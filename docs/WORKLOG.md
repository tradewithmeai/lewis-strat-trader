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
