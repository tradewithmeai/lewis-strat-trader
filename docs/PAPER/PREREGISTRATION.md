# Pre-registration — Phase 2 confirmatory analysis

**Frozen:** 2026-06-02, before any Phase-2 (reaction-modelling) results were
computed. The git commit timestamp of this file is the evidence of pre-commitment.
Phase 0 (the exploratory event study in `docs/TRUMP_EVENT_STUDY.md`) is **not**
covered by this pre-registration and is reported as exploratory /
hypothesis-generating (its taxonomy was refined after observing specific 2025
episodes — see `docs/WORKLOG.md`). This document governs the **confirmatory**
analysis only.

> Any deviation from this plan, once results are seen, must be logged in
> `docs/WORKLOG.md` with its reason and reported in the paper as a post-hoc
> deviation. Additions are allowed; they are labelled exploratory.

---

## 1. Research questions (confirmatory)

- **RQ1 (volatility).** Do market-relevant Trump Truth Social posts predict
  elevated short-horizon (1–4h) realized volatility in BTC/ETH/SOL **beyond**
  what trailing volatility already implies?
- **RQ2 (direction).** Does the text-derived directional signal predict the
  sign of forward returns at 1/4/24h?
- **RQ3 (tradeable edge).** Is there a post-event trading rule whose net-of-cost
  out-of-sample performance is distinguishable from zero?

## 2. Frozen signal definition (no forward data — text only)

The independent variables are computed in `local_system/signals/trump_signal.py`
from post text + timestamp ONLY. No realized return ever enters a label
(prevents look-ahead circularity). Frozen components:

- `signal` ∈ [−1, 1]: blended directional signal. LLM-labelled posts →
  `llm_stance/2 × conviction`; others → `finbert_score` (= P(pos) − P(neg),
  ProsusAI/finbert).
- `finbert_score`, `finbert_pos/neg/neu` — FinBERT class probabilities.
- `novelty_7d` — 1 − max cosine similarity to MiniLM embeddings of posts in the
  trailing 7 days (causal).
- Topic dummies (frozen taxonomy, `trump_classify.py`): tariffs_trade, china,
  fed_rates, crypto, dollar, energy_oil, markets, taxes_fiscal, geopolitics,
  market_directive, reassurance.
- `is_policy_signal`, `is_market_directive`, `conviction` (LLM, hard cases).
- `market_relevant` (any economic topic), `is_noise`, `burst_id`, `engagement`.

**Unit of observation:** the burst (posts <30 min apart), anchored to the first
market-relevant post's hour. Engagement counts are NOT known at post time and
are excluded from any predictive specification (used only descriptively).

## 3. Assets & targets (frozen lists)

- **Crypto (hourly):** BTCUSDT, ETHUSDT, SOLUSDT (Binance; lake + klines).
- **Macro (daily):** DXY, GOLD, SPX, NDX, US10Y, VIX.
- **Horizons:** 1h, 4h, 24h (crypto); 1 trading day (macro).
- **Targets:** forward log return `fwd_ret_k`; forward realized volatility
  `fwd_vol_k = sqrt(Σ hourly logret² over k)`. Both measured from the event
  hour's close (conservative; misses first-minutes reaction).

## 4. Estimation

1. **Panel / OLS (interpretable):** `fwd_target ~ signal + novelty_7d +
   topic dummies + trailing_vol_24` with **standard errors clustered by day**
   (bursts cluster within days). Trailing-vol control is mandatory for all
   volatility regressions (the endogenous-timing confound).
2. **Non-linear (LightGBM):** same features → forward target, evaluated by
   purged + embargoed walk-forward CV. Report permutation feature importance.

**Cross-validation:** purged + embargoed walk-forward (López de Prado). Embargo =
the target horizon (24h max) so overlapping forward windows cannot leak across
the train/test boundary. 5 expanding folds by time.

**Null:** the era-matched + trailing-vol-quintile-matched bootstrap already in
`_event_study_trump.py` (2000 draws), for the event-vs-null mean tests.

## 5. Multiple-testing correction (decided in advance)

The test grid is assets × horizons × targets × signal terms ≈ dozens of tests.
Primary correction: **Benjamini–Hochberg FDR at q = 0.10** across the full
pre-registered grid. Robustness: **Romano–Wolf stepdown** family-wise control.
A result is "confirmed" only if it survives BH-FDR. The BTC/ETH/SOL co-movement
(~0.92) is disclosed: the three crypto assets are treated as ~one effect, not
three independent confirmations.

## 6. Decision rule for RQ3 (tradeable edge) — fixed before results

- **Holdout:** the final 20% of the sample by calendar time is a true OOS
  holdout, not used for any model selection or feature tuning.
- A post-event rule (e.g. trade direction = sign(signal), hold k hours) counts
  as a **tradeable edge only if** its net-of-cost Sharpe (costs = 0.24% round
  trip, the repo standard) has a **block-bootstrap 95% CI lower bound > 0 on the
  OOS holdout.** Otherwise the reported conclusion is "no tradeable edge after
  costs" — a valid result.

## 7. What would falsify each hypothesis

- RQ1 false if the event dummy / signal is insignificant once `trailing_vol_24`
  is controlled (i.e. the Phase-0 vol effect was endogenous timing after all).
- RQ2 false if `signal` does not predict return sign out-of-sample.
- RQ3 false (the expected outcome, per the repo's prior track record) if no rule
  clears the OOS Sharpe-CI bar.

## 8. Reproducibility

Pinned data snapshot (`state/signals/trump_archive.meta.json`); fixed RNG seed
(42); frozen model versions (ProsusAI/finbert, all-MiniLM-L6-v2,
gpt-4.1-mini); all code committed. The full method trail is in `docs/WORKLOG.md`.

---

# AMENDMENT 1 — 2026-06-03 (post methodology-review, pre signal-dependent results)

Sections 1–8 above remain frozen as the original pre-commitment (its git
timestamp is the evidence). This amendment records changes made AFTER a 14-agent
adversarial methodology review (`METHODOLOGY_REVIEW.md`, 14 high-severity issues)
and the advisor's triage, but BEFORE the signal-dependent confirmatory results
(RQ2/RQ3) were computed. The vol-only RQ1 keystone (which needs no LLM signal)
was run as part of this amendment and is reported below.

## A1.1 Reframing: exploratory/observational, not strong-confirmatory
The study is relabelled **exploratory / observational with adversarial
robustness**, not strong-confirmatory. Rationale (data ceilings no method can
fix): a single dominant regime (2025–26 tariff war), n=2 in the directive class,
and BTC/ETH/SOL co-movement ≈0.92. The originally-implied temporal firewall
(refine pre-2025 → confirm post-2025) is **dropped**: the signal is concentrated
in 2025–26, so the split starves both sides and would manufacture rigor the data
cannot bear. The final-20%-by-time OOS holdout is retained for **RQ3 only**.

## A1.2 Inference (primary vs corroborating)
- **Primary inference = cluster-robust (day-clustered) OLS** with the
  trailing-vol control. It correctly handles within-day correlation and the
  endogenous-timing confound parametrically.
- **Corroborating = two bootstrap nulls:** the vol-quintile-matched i.i.d. null
  AND the new day-clustered null (`null_distribution_dayblock`). Report a
  **balance table** (event vs pool trailing-vol mean + p90) with every vol claim.
- Honesty note: the day-block null came back *more* significant than the i.i.d.
  one because it relaxes vol-matching (era+clustering only) — so it is reported
  as corroboration, NOT cited as "the conservative number". Effects must hold
  across all three to count.

## A1.3 RQ1 keystone result (run under this amendment)
The 1–4h forward-vol effect SURVIVES all three specs (BTC): vol_4h full-sample
+5.2bp, regression p=0.007, i.i.d.-null p=0.010, day-block-null p=0.005; 2025+
p=0.015/0.005/0.000. The 24h effect is volatility clustering (dies under all).
Trailing vol is balanced (event 223bp ≈ pool 225bp). RQ1 is treated as a real,
robust effect; RQ2/RQ3 expected null.

## A1.4 Adopted fixes (from the review)
1. **FinBERT-only robustness signal** for RQ2/RQ3 — defends against the
   gpt-4.1-mini training-corpus leak (its weights may encode how famous posts
   played out). FinBERT predates the events; any RQ2/RQ3 result must also be
   shown under a FinBERT-only signal.
2. **Freeze + hash the label set** at the declared coverage (target 100% of
   market-relevant non-noise) BEFORE any signal-dependent result; pin the dated
   LLM snapshot and persist a run manifest (model version, params). The signal
   seam (which posts are LLM- vs FinBERT-labelled) must not be build-date-dependent.
3. **Do not blend constructs:** report the LLM market-impact stance and the
   FinBERT tone as SEPARATE covariates, not one `signal` column, for RQ2.
4. **Placebo-actor control** (top addition): run the identical burst pipeline on
   a non-Trump high-salience feed and/or scrambled event timestamps, to separate
   "Trump's text carries vol-relevant info" from "any salient poster correlates
   with crypto vol".
5. **Co-movement:** BTC is the primary asset; ETH/SOL are r≈0.92 robustness, NOT
   independent confirmations. Avoid "3/3 assets" replication language.
6. **RQ3:** keep the pre-registered sign(signal) every-burst rule for
   completeness, but the **primary RQ3 cell is directive/high-conviction-gated,
   single asset (BTC)**; report any multi-cell family with FWER control.

## A1.5 Acknowledged ceilings (reported as limitations, not engineered around)
Single-regime dominance; n=2 directive class (case study, not inference);
BTC/ETH/SOL ≈ one factor; engagement not known at post time (excluded from
predictors). These bound external validity and are stated plainly in the paper.
