# Posts as Events: Intraday Cryptocurrency Volatility Around a Head of State's Social-Media Communications

**Draft — undergraduate-level empirical paper (tier 1 of the project roadmap).**
Status: complete first draft from the frozen evidence base; not yet copy-edited
or converted to LaTeX. Author(s): _[human author / affiliation TBD]_. AI tooling
disclosed in the Reproducibility & Disclosure statement.

---

## Abstract

We study whether the social-media communications of a sitting head of state carry
short-horizon, market-relevant information for cryptocurrency markets. Using the
full corpus of 33,712 Truth Social posts by Donald J. Trump (February 2022 – June
2026) and hourly prices for Bitcoin, Ethereum and Solana, we construct a
text-only event signal — combining a financial-domain sentiment model, a
large-language-model market-impact stance read, a keyword topic taxonomy and a
causal novelty score — and conduct a burst-level event study. We find that
market-relevant posts are followed by a modest but robust increase in 1–4 hour
**realised volatility** (Bitcoin: +5.2 bp over four hours, day-clustered
regression *p* = 0.007), which survives a null matched on the prevailing
volatility regime and, critically, is **absent for the same author's
non-market-relevant posts** (a content placebo run on five times as many events).
The effect does **not** extend to 24 hours (that horizon is consistent with
ordinary volatility clustering) and does **not** translate into predictable
return *direction*: neither the directional signal nor any post-event trading rule
produces a tradeable edge net of transaction costs, a null that is robust to using
a sentiment model whose training predates the events. A small class of explicit
"market-directive" posts — including the widely reported "THIS IS A GREAT TIME TO
BUY" message of 9 April 2025 — preceded large rallies, but with only two such
events these are reported as a qualitative case study, not as evidence of
predictability. The contribution is methodological as much as empirical: an
intraday, full-corpus, text-only, pre-registered design with an endogenous-timing
control and a content placebo, applied to a setting (Truth Social → crypto, the
2025–26 trade-policy regime) that prior daily, hand-curated event studies do not
resolve.

**Keywords:** event study; realised volatility; social media; cryptocurrency;
political communication; volatility clustering.

---

## 1. Introduction

A distinctive feature of the 2025–26 market environment is that a single,
high-authority actor — the President of the United States — routinely posts
unscheduled statements on a social-media platform (Truth Social), some of which
concern, or directly precede, market-moving policy. Three episodes drew particular
public attention. On 3 March 2025 a post announcing a "Strategic National Crypto
Reserve" was followed by a sharp Bitcoin rally. On 9 April 2025, roughly four hours
before the announcement of a 90-day pause in reciprocal tariffs, the President
posted "THIS IS A GREAT TIME TO BUY!!! DJT"; equity and crypto markets rallied
sharply that afternoon, and several legislators publicly called for
insider-trading and market-manipulation investigations. On 10 October 2025 a post
announcing 100% tariffs on China was followed by a ~12% intraday fall in Bitcoin
and the largest single-day liquidation event in the asset's history to that point.

These episodes raise a measurement question that this paper addresses
quantitatively and neutrally: **do this actor's posts carry short-horizon,
market-relevant information for cryptocurrency, and if so, in what form — direction,
volatility, or neither?** We make no claim about intent; we report the public
allegations around specific posts as dated facts and study the *abnormal returns
and volatility* around posts, not the question of manipulation.

We answer the measurement question with a burst-level event study on the full
post corpus, joined to hourly crypto prices and a daily macro panel. Three
pre-registered research questions structure the analysis:

- **RQ1 (volatility).** Do market-relevant post bursts predict elevated 1–4 hour
  forward realised volatility *beyond* what the prevailing (trailing) volatility
  already implies?
- **RQ2 (direction).** Does a text-derived directional signal predict the *sign*
  of forward returns?
- **RQ3 (tradeable edge).** Does a post-event trading rule beat zero net of
  realistic transaction costs out of sample?

Our answers are: **yes** (modest, robust, content-specific) to RQ1; **no** to RQ2
and RQ3. The most defensible single sentence is that *market-relevant posts move
how much crypto moves over the next few hours, not which way, and not by enough to
trade after costs.*

**Contributions.** Relative to the closest prior work (Section 2), which conducts
*daily* event studies on *hand-curated* policy-event lists, we contribute: (i) an
**intraday** (1/4/24-hour) design that resolves an effect invisible at daily
resolution; (ii) a **systematic, text-only classification of the entire 33k-post
corpus** rather than a curated event list, removing event-selection discretion;
(iii) an explicit **endogenous-timing control** — matching the comparison set on
prevailing volatility, because a high-profile actor may post precisely when
markets are already moving; and (iv) a **content placebo** that isolates whether
the effect is about market *content* or merely about the act of posting. We frame
the study as exploratory/observational; the data — a single dominant policy
regime, two directive-class events, and crypto assets that co-move at ~0.92 —
cannot bear strong-confirmatory claims, and we say so throughout.

---

## 2. Related work

**Trump communications and market volatility.** A mature literature studies the
president's *Twitter* output and *equity/bond* markets. Nishimura, Dong & Sun
(2021, *Journal of Financial Research*) study the second-moment response of US
equities to Trump tweets using daily realised volatility decomposed into
continuous and jump components, finding that tweeting raises volatility and jump
tail-risk in the later sample. The practitioner "Volfefe Index" (JPMorgan, 2019)
linked tweets to intraday Treasury-rate volatility; its citable academic anchor,
Klaus & Koser (2021, *Finance Research Letters*), finds the index adds predictive
power for European equity returns, heterogeneously and non-linearly. Born, Myers
& Clark (2017, *Algorithmic Finance*) run a daily firm-level event study on 15
tweets, finding transitory, noise-trader-driven abnormal returns. On the
trade-war channel specifically, Burggraf, Fendel & Huynh (2020, *Applied Economics
Letters*) find US–China tweets negatively predict the S&P 500 and positively
predict the VIX. Two studies move toward our intraday, topic-classified design:
Gjerstad et al. (2021, *Decision Support Systems*) use precise tweet timestamps
with high-frequency equity data and LDA topics, finding the market falls and
uncertainty rises after tweets, strongest for the "trade war" topic; and Perico
Ortiz (2023, *Journal of Economics and Finance*) runs an intraday VIX event study
(5-minute bars, to five hours post-tweet) with unsupervised topic clustering,
finding foreign-policy/trade tweets raise uncertainty most. This literature is
*Twitter + equities/bonds, first term*; we are *Truth Social + crypto, 2022–26*.

**Trump and crypto.** The closest direct work is a cluster of SSRN working papers
by Krause (2025) — e.g., *Trump-Era Cryptocurrency Policy Events and Bitcoin
Returns*, *Trump, Tokens, and Tailwinds*, *Tariffs, Tokens, and Turmoil* — which
conduct **daily** event studies on **hand-curated** policy/advocacy events, with
multi-day cumulative-abnormal-return windows. We differ on four axes
(intraday resolution; full-corpus systematic classification rather than curated
events; a focus on the second moment with an explicit treatment of volatility
*clustering*; and an endogenous-timing-matched null). We therefore do not claim
to be the first study of Trump and crypto; our novelty is the *joint* combination
of these design choices in this regime.

**Social-media sentiment and crypto.** A broad literature relates aggregate
Twitter sentiment to crypto returns, volatility and liquidity, and documents that
single high-profile actors (e.g., Elon Musk) generate abnormal returns in named
coins. This work typically uses aggregate retail sentiment rather than a single
high-authority actor whose posts can *precede the policy they concern* — the
feature that motivates our directive case study.

---

## 3. Data

**Posts.** We use a pinned snapshot (33,712 posts, 14 Feb 2022 – 2 Jun 2026; SHA
recorded in the project manifest) of a public archive of @realDonaldTrump's Truth
Social posts. Each post carries an ISO-8601 UTC timestamp, HTML content,
engagement counts, and media flags. Because the upstream archive refreshes every
few minutes, all analysis runs against the frozen snapshot for reproducibility.

**Prices.** Hourly OHLCV for BTCUSDT, ETHUSDT and SOLUSDT (Binance), spanning the
post period. Bitcoin history is drawn from a local parquet lake; Ethereum and
Solana, which lack deep history in the lake, are fetched from the Binance public
REST API (same venue, so the series are consistent by construction). A daily macro
panel (DXY, gold, S&P 500, Nasdaq-100, US 10-year yield, VIX, and the three crypto
assets) covers December 2024 onward.

**Event-time joins and no look-ahead.** Posts are joined to prices strictly by
their post timestamp floored to the hour; all forward returns and volatilities are
measured from that hour's *close* onward (a conservative choice that misses the
first within-hour minutes of any reaction). We validate the join against a
ground-truth event — the "Liberation Day" tariff sell-off of 2–3 April 2025, in
which Bitcoin fell ~2.4% in a single evening hour — confirming that timestamps
align and that no timezone error contaminates the windows.

---

## 4. Signal construction (text only)

All independent variables are computed from post text and timestamp **only**; no
realised return ever enters a label. This is essential: a label informed by the
outcome it is meant to predict would make the analysis circular.

- **Topic taxonomy.** A frozen keyword taxonomy assigns each post to economic
  topics (tariffs/trade, China, Fed/rates, crypto, dollar, energy, markets,
  fiscal), geopolitics, and two content classes motivated by the 2025 episodes:
  *market-directive* (explicit buy/sell or market predictions, e.g. "great time
  to buy") and *reassurance* ("be cool", "don't panic"). A post is
  *market-relevant* if it hits any economic topic (≈8% of posts).
- **Financial sentiment.** FinBERT (ProsusAI/finbert) yields class probabilities;
  `finbert_score = P(pos) − P(neg)`. On market-relevant posts this averages −0.01,
  versus +0.37 for a generic lexical sentiment model (VADER) — i.e. the
  domain model removes a strong positive bias driven by the author's
  superlative style.
- **LLM market-impact stance.** For the ~1,851 market-relevant, non-boilerplate
  posts (the cases where idiom matters), an instruction-tuned LLM labels the
  *direction a trader would lean for risk assets* on reading the post (−2…+2),
  a conviction (0–1), and flags for policy-signal and market-directive content.
  We emphasise this is a market-impact read from the text, not hindsight.
- **Novelty.** A causal 7-day novelty score (1 − maximum cosine similarity to the
  embeddings of posts in the trailing week) distinguishes first-of-kind statements
  from repetitive ones.
- **Bursts.** Because posts arrive in clusters (ten posts in seven minutes is
  common), the unit of observation is the *burst* — posts less than 30 minutes
  apart — anchored to the first post's hour. Within-burst moves cannot be
  attributed to one post.

We note two disclosed limitations of the signal. First, the directional `signal`
blends an LLM market-impact read (where available) with FinBERT tone (otherwise);
we therefore also report results using a **FinBERT-only** signal, whose training
predates these events and is thus immune to any leakage through an LLM's
parametric memory of how famous posts played out. Second, engagement counts are
*not* known at post time and are excluded from all predictive specifications.

---

## 5. Method

The analysis was **pre-registered** before the signal-dependent results were
computed (with one dated amendment that reframed the study as
exploratory/observational and adopted the robustness checks below); the
pre-registration timestamp is the evidence of pre-commitment.

**Targets.** For horizons *k* ∈ {1, 4, 24} hours we compute forward log return and
forward realised volatility (the root of summed squared hourly log returns over
*k*), plus a trailing-24-hour realised volatility *known at event time*.

**Primary inference (RQ1).** A cluster-robust OLS regression on all hourly bars of
forward volatility on an event dummy, controlling for trailing volatility and
hour-of-day, with standard errors clustered by calendar day. The trailing-vol
control is the key identification device: a high-profile actor may post *because*
volatility is already elevated, so the question is whether forward volatility rises
*beyond* what trailing volatility predicts.

**Corroborating nulls.** Two bootstrap nulls (2,000 draws): one matching the
comparison hours on hour-of-day *and* trailing-vol quintile (an i.i.d. null), and
one resampling whole calendar-day blocks to reproduce the event sample's
day-clustering. We report a balance table (event vs. pool trailing volatility) with
every volatility claim.

**RQ2/RQ3.** For direction, cluster-robust regressions of forward returns on the
signal, novelty and topic dummies, with Benjamini–Hochberg false-discovery
correction across the test grid. For tradeable edge, a sign-of-signal rule on a
final-20%-by-time out-of-sample holdout, held four hours, net of a 0.24%
round-trip cost (0.1% taker × 2 + 2 bp slippage × 2), judged by a block-bootstrap
95% Sharpe confidence interval whose lower bound must exceed zero. RQ3 is reported
for both the LLM-blended and FinBERT-only signals, and split by policy-signal
status.

---

## 6. Results

Reported *p*-values are **nominal** (uncorrected for multiple comparisons)
except in RQ2/RQ3, where a Benjamini–Hochberg false-discovery correction is
applied. For the RQ1 volatility result the multiplicity safeguard is not a
corrected threshold but the *consistency* of the effect across two horizons
(1 h, 4 h) × three assets × two independent nulls, together with the
content-placebo contrast (§6.2); we read the nominal values in this exploratory/
observational spirit rather than as confirmatory significance tests.

### 6.1 RQ1 — a robust 1–4 hour volatility effect

Market-relevant post bursts are followed by elevated short-horizon realised
volatility. In the cluster-robust regression (the primary inference), the Bitcoin
event dummy is **+3.06 bp at 1 hour (*p* = 0.018)** and **+5.18 bp at 4 hours
(*p* = 0.007)** over the full sample, and +3.37 bp (*p* = 0.041) / +6.33 bp
(*p* = 0.015) in the in-office (2025+) sub-sample. The **24-hour** dummy is
insignificant and near zero (−0.89 bp, *p* = 0.795), consistent with the 24-hour
window capturing ordinary volatility clustering rather than a post effect. The two
bootstrap nulls corroborate the 1–4 hour result (event vs. matched null: 4-hour
+87.6 bp vs. +82.8 bp). The balance table shows the comparison is fair: event-hour
trailing volatility (223 bp) is essentially identical to the pool (225 bp) — the
effect is *not* an artefact of posts arriving in already-high-volatility hours.

The economic magnitude is modest — roughly a 5–8% relative increase in realised
volatility for one to four hours — and we treat it as a volatility/timing signal,
not an alpha source.

### 6.2 The content placebo — the effect is specific to market content

To separate "market content moves volatility" from "any post, or any time-of-day,
coincides with volatility," we run the identical pipeline on the *same author's
non-market-relevant* posts — 7,232 bursts, five times the treatment count, so
higher statistical power. Under the primary inference these show **no** volatility
effect: the 4-hour event dummy is +1.04 bp (*p* = 0.232) full-sample and +1.62 bp
(*p* = 0.214) in 2025+, versus the treatment's +5.18 bp (*p* = 0.007) and +6.33 bp
(*p* = 0.015) — a roughly five-fold difference in effect size, with the placebo
indistinguishable from zero. At 24 hours neither group shows a positive effect;
the placebo's 24-hour coefficient is in fact significantly *negative* (−5.39 bp,
*p* = 0.004) — an unexplained large-sample artefact of the opposite sign that we
do not interpret as a post effect, and which mirrors the treatment's own null
24-hour coefficient (−0.89 bp). The volatility effect is therefore a property of
the market *content* of the posts at the 1–4 hour horizon, not of the act of
posting or of intraday seasonality (which the null already matches).

### 6.3 RQ2/RQ3 — no directional predictability, no tradeable edge

The directional signal does **not** predict the sign of forward returns: the
continuous `signal` term is insignificant at every asset and horizon (all *p* >
0.4). No post-event trading rule clears costs: across all twelve cells (three
assets × {all, policy-gated} × {LLM, FinBERT signals}), the sign-of-signal rule
loses money net of the 0.24% round trip, with out-of-sample annualised Sharpe
ratios between roughly −6 and −15. Critically, the null holds under the
**FinBERT-only** signal as well as the LLM signal, so it is not an artefact of any
LLM training-corpus leakage. Trading every market-relevant burst is, mechanically,
cost-prohibitive; the absence of a directional edge is robust.

The Benjamini–Hochberg procedure flags eight "surviving" coefficients, but **all
eight are the market-directive dummy** — i.e. the *n* = 2 directive class (below) —
and their large magnitudes (+166 to +724 bp) and *p* = 0.000 are the mechanical
artefact of a two-observation dummy landing on two large-move events, not evidence
of a generalisable effect. A negative one-hour coefficient on the China/tariff
topic (−8 to −17 bp, *p* ≈ 0.02–0.03, not surviving correction) is reported only as
a consistency check: that trade-war escalation is risk-off for crypto is already
known, so we do not report it as a finding.

### 6.4 The market-directive case study (*n* = 2)

Two posts in the corpus are explicit market directives: "I think it's going very
well…The MARKETS are going to BOOM" (3 April 2025) and "THIS IS A GREAT TIME TO
BUY!!! DJT" (9 April 2025). Both preceded large rallies; the 9 April post preceded
the 90-day tariff-pause announcement by roughly four hours, and Bitcoin rose ~5.6%
over the following four hours and ~4.0% over 24 hours. We report these as a
qualitative illustration of the directive class and, as a documented matter of
public record, note that the 9 April post prompted public calls for
insider-trading and market-manipulation investigations. With *n* = 2 we draw no
statistical inference; the episode motivates the directive taxonomy and the future
collection of more such events, not a tradeable claim.

### 6.5 Macro panel

On the daily macro panel (December 2024 onward) we find no statistically
significant next-day effects of post activity or sentiment on any series. The panel
is short and daily, so this is low-power evidence rather than evidence of absence.

---

## 7. Discussion and limitations

**What the evidence supports.** Posts with market content are followed by a small,
robust increase in 1–4 hour crypto volatility that survives an endogenous-timing
control and is absent for the same author's non-market posts. They do not predict
direction, and the volatility effect is too small and too short-lived to trade
after costs. This is a coherent and, we think, credible picture: high-authority
communications inject short-lived uncertainty without providing a directional edge
to an outside reader.

**Methodological by-catch.** The content placebo also audited our inference
machinery: the day-block bootstrap null flagged a *negligible* +0.4 bp placebo
"effect" as significant, revealing that this null is anti-conservative at large *n*
(its standard error shrinks faster than the dependence structure warrants). We
therefore treat the **cluster-robust regression as the primary inference** and the
bootstrap nulls as corroboration — a choice the placebo justifies empirically.

**Limitations (data ceilings, not fixable by method).** (i) The three crypto
assets co-move at ~0.92, so they constitute approximately one effect observed three
times, not three independent confirmations; we report Bitcoin as primary and the
others as robustness. (ii) Market-relevant bursts cluster heavily in the 2025–26
trade-policy regime, so external validity beyond that regime is unestablished, and
this bites the directional results hardest. (iii) The market-directive class has
*n* = 2; it is a case study. (iv) Our placebo is a *content* (within-actor) control;
a *different-actor* placebo — another high-salience poster's timestamps — would
further separate "this actor's text" from "any salient market commentator," but no
clean negative-control feed was readily available (a poster who also moves crypto
would be a positive, not negative, control). We log this as the priority extension.
(v) The LLM-derived labels are not bit-reproducible under the model alias used; a
local, pinned model would fix this and is planned.

**Future work.** The natural extensions are: a different-actor placebo; a test of
whether the volatility signal is monetisable through an instrument matched to it
(e.g. options/variance products, absent from our spot data); and — once a 24/7
collector has grown the directive/escalation event set well beyond *n* = 2 — a
proper test of whether such posts are predictable in advance from prevailing
conditions.

---

## 8. Conclusion

A sitting head of state's social-media posts, when they concern markets, are
followed by a modest, robust, content-specific increase in short-horizon (1–4
hour) cryptocurrency volatility, but not by predictable return direction, and not
by a tradeable edge after costs. The widely reported "buy" directives are a
compelling but statistically thin case study, not an edge. The result is a careful
*measurement* rather than a strategy — which is, given the data, the honest place
to stop.

---

## Reproducibility & disclosure

All code, the pre-registration and its amendment, the verified citation set, and a
dated work-log of every decision are version-controlled in the project repository;
the frozen signal label set and pinned post-archive snapshot are recorded with
SHA-256 hashes in a signal manifest. Analyses use a fixed random seed. The research
was conducted with substantial AI coding and analysis assistance; per standard
journal policy, AI systems are not listed as authors, and their role is disclosed
here and documented in full in the repository's work-log. _[Author names,
affiliations, funding, and competing-interest statements to be completed.]_

## References (working list — see RELATED_WORK_VERIFIED.md for the full annotated set)

- Born, J. A., Myers, D. H. & Clark, W. J. (2017). Trump tweets and the efficient
  market hypothesis. *Algorithmic Finance*, 6(3–4), 103–109.
- Burggraf, T., Fendel, R. & Huynh, T. L. D. (2020). Political news and stock
  prices: evidence from Trump's trade war. *Applied Economics Letters*, 27(18).
- Gjerstad, P., Meyn, P. F., Molnár, P. & Næss, T. D. (2021). Do President Trump's
  tweets affect financial markets? *Decision Support Systems*, 147, 113577.
- Klaus, J. & Koser, C. (2021). Measuring Trump: the Volfefe Index and its impact
  on European financial markets. *Finance Research Letters*, 38, 101447.
- Krause, D. (2025). *Trump-Era Cryptocurrency Policy Events and Bitcoin Returns*;
  *Trump, Tokens, and Tailwinds*; *Tariffs, Tokens, and Turmoil* (SSRN working papers).
- Nishimura, Y., Dong, X. & Sun, B. (2021). Trump's tweets: sentiment, stock market
  volatility, and jumps. *Journal of Financial Research*, 44(3), 497–512.
- Perico Ortiz, D. (2023). Economic policy statements, social media, and stock
  market uncertainty. *Journal of Economics and Finance*, 47, 333–367.
