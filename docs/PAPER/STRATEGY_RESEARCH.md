# Systematic Strategy Research — Progress & Findings

A research log of the **systematic trading-strategy** strand of the project,
distinct from the Trump event-study papers (see `THESIS_STRUCTURE.md`). This
strand asks a narrower, harder question: **can a simple, explainable systematic
rule produce a real, out-of-sample edge net of costs — and if not, why not?**

The honest answer so far is a **negative result**, and the negative result is
itself the contribution: it reproduces, on our own data and infrastructure, the
well-documented failure of single-asset price-timing — and motivates a reframing
toward the strategy classes the literature actually supports.

_Last updated: 2026-07-15._

## 1. What we built (method)

- **Walk-forward backtester** (`local_system/backtester.py`): 80/20 train/test,
  no look-ahead, realistic costs (0.1% taker × 2 + ~2 bp slippage × 2 ≈ 0.24%
  round trip), block-bootstrap Sharpe 95% CI.
- **Mark-to-market drawdown + holding-time metrics** (added 2026-06): exposes
  the risk that a realised-only drawdown hides for hold-to-target designs.
- **Live forward paper board** (`local_system/paper_trader.py` +
  `live_board.py`): every registered strategy trades a persistent $1,000 account
  on the live feed — genuinely out-of-sample, no split. This is the arbiter;
  backtests only propose.
- **Self-hosted data**: a 19-symbol, 3-exchange crypto lake (1s→1h/1d) and an
  on-demand public-data loader for TradFi (`tradfi_data.py`, yfinance).
- **Rigor gate** (enforced on every candidate): full-history headline first;
  sign-consistency across windows *and* assets; sample sanity (distrust <30
  trades / >75% win / Sharpe >3); realised **and** mark-to-market drawdown;
  beat buy-and-hold after costs; declare the search size; fixed methodology;
  forward-board cross-check.

## 2. What we tested, and the results (all null)

Eleven registered strategies (RSI mean-reversion, EMA crossover, breakout,
Bollinger, multi-timeframe confluence, regime models, an ensemble, etc.) plus a
purpose-built `bb_rsi_dip` (Bollinger+RSI dip-buy, fixed %-target).

- **Crypto, single-asset (BTC/ETH/SOL), 3-year walk-forward, 1h:** every
  strategy negative or sub-benchmark. Leaderboard returns −4% to −68%; the
  "best" (breakout) was the active incumbent at ≈ −12%, not a winner.
- **The `bb_rsi_dip` mirage:** showed 100% win, +57% (BTC) / +137% (SOL) with a
  *no-stop* exit — fully a backtest artefact. With realised losses forced (a
  stop), it collapsed to +13%, **Sharpe 0.32 with a CI spanning zero**; the
  no-stop version hid a **45–64% mark-to-market drawdown** and **235-day holds**.
  A bull-market "never sell at a loss" illusion, caught by the mark-to-market
  metric.
- **Event-driven (Trump archive, 34k posts, in-office split):** reproduces the
  event-study papers — China posts precede a *negative* BTC drift (t ≈ −2.3) and
  tariff/China posts elevate 1–4h volatility (×1.1–1.2 baseline) — but the
  **directional effect (~0.2%/4h) is smaller than the 0.24% round-trip cost**.
  A volatility risk-overlay on `rsi_meanrev` was **indistinguishable from random
  entry suppression** (one-sided p ≈ 0.07 vs a random-suppression null). No edge.
- **TradFi transfer (8 commodities + indices/DXY, 2017–2026 daily):** crypto
  strategies do **not** transfer. Across 32 asset×strategy combinations only 2
  nominally beat buy-and-hold (≈ chance), by rounding-error margins on weak
  underliers with 70%+ drawdowns. Strong-trend assets (equities, gold) left most
  of the gains on the table.

## 3. Why (reconciliation with the literature)

A wide literature search (2026-06-30) confirms our nulls are **expected**, not
bad luck — we were testing the one approach the evidence says does not work, and
ignoring the ones that do:

1. **Single-asset directional timing vs buy-and-hold is the empty pond.** The
   overfitting literature treats "backtest Sharpe 1.2 → live −0.2" as the
   canonical outcome of retail single-asset rule-mining (López de Prado;
   *Portfolio Optimization* Ch. 8). Our results match this exactly.
2. **The documented edges are cross-sectional / market-neutral, not single-asset
   directional.** Persistent premia — momentum, value, carry, defensive — are
   harvested by *ranking a universe* (long winners / short losers), e.g. AQR's
   "Value and Momentum Everywhere" and "A Century of Factor Premia". In crypto
   specifically, the reported working combination is **cross-sectional momentum
   + funding-rate carry, market-neutral, BTC-regime-gated** (Sharpe ≈ 1.3).
3. **Trend-following is a diversified-basket phenomenon.** A single market's
   trend Sharpe is low; a basket of 50–100 futures across asset classes reaches
   portfolio Sharpe > 1 because the trends are uncorrelated (Moskowitz, Ooi &
   Pedersen 2012; AQR "Demystifying Managed Futures"). We tested one market at a
   time — structurally unable to see the effect.
4. **The benchmark was wrong.** Trend/managed-futures does not aim to beat equity
   buy-and-hold in a bull market; its value is low correlation and crisis alpha
   (adding trend to equities historically cut max drawdown ~51%→22%). "Never beat
   buy-and-hold of BTC" was never the right test for that class.

## 4. The reframing (current hypothesis)

The essential missing ingredient is **portfolio / cross-sectional structure**,
which our single-asset backtester cannot express. Next phase:

- **Cross-sectional / portfolio backtester** (`portfolio_backtester.py`): rank a
  universe by a signal, long-top / short-bottom, periodic rebalance,
  market-neutral P&L, annualised Sharpe — the framework the documented edges
  require.
- **Three pre-registered tests** on it: (a) crypto cross-sectional momentum
  across the 19-symbol universe; (b) funding-rate carry from the futures data we
  already collect; (c) a diversified time-series trend basket across the TradFi
  universe.
- **Re-anchor evaluation on risk-adjusted return** (Sharpe, correlation,
  drawdown), keeping buy-and-hold only as an honesty check, not the target.

Expectation, stated up front to avoid hindsight bias: these edges are **real but
decayed and drawdown-prone** (Sharpe ≈ 1, multi-year drawdowns; crypto carry
compressed to ~5–15% annualised by 2026; cross-sectional crypto momentum muted
in calm 2024–25). We expect modest, honest positives — not a magic bullet — and
will hold them to the same rigor gate and live-forward confirmation.

## 6. Phase-2 results: portfolio / cross-sectional engines (2026-06-30)

Built `portfolio_backtester.py` (cross-sectional rank-and-trade + diversified
time-series trend, with risk-parity weighting, a no-look-ahead vol-target
overlay, per-calendar-year Sharpe, and block-bootstrap Sharpe CIs) and ran the
three pre-registered tests. **Headline: the reframing is validated in *kind* but
not in *degree*** — these are genuinely the structures the literature describes,
behaving as documented, but none clears the rigor gate (every bootstrap Sharpe CI
spans zero on our sample).

| test | best config | Sharpe (95% CI) | vol / maxDD | per-year pattern |
|---|---|---|---|---|
| Crypto X-sectional momentum | 60d, risk-parity, vol-targeted 15% | **0.91** (−0.15, 1.89) | 17% / −19% | 2.6 → 1.2 → 0.4 → **−0.7** (decaying) |
| Funding carry (price P&L only) | −funding rank, neutral | 0.32 (−0.71, 1.28) | 39% / −50% | inconsistent |
| Funding carry **+ income** | + modeled funding accrual | **0.69** (−0.34, 1.66) | 39% / −47% | −1.0, 1.8, 0.3, 0.2 |
| TradFi diversified trend | 120d, risk-parity, vol-targeted 10% | 0.26 (−0.21, 0.76) | 11% / −31% | crisis-alpha (+2008, +2022) |
| _benchmarks_ | crypto EW buy&hold / TradFi EW long | 0.47 / 0.41 | — | — |

Findings, honestly:
1. **Crypto cross-sectional momentum is the strongest result we have.** Vol-
   targeting tamed the raw 62% vol to a clean **17% vol / −19% DD at Sharpe ~0.9**,
   and being **market-neutral it cushioned crypto drawdowns** — it beat the
   long-only benchmark in 2025 (0.4 vs −0.3) and 2026 (−0.7 vs −1.5). But the
   per-year Sharpe **decays monotonically and goes negative in 2026**, and the
   CI spans zero. A *real but decaying* effect (matching reports of muted
   cross-sectional crypto momentum in 2024–25), not a deployable edge.
2. **Funding carry's income is real money** (~**+14.6%/yr** of funding accrual),
   lifting the combined Sharpe to 0.69 and turning recent years positive. The
   proper form is delta-hedged cash-and-carry, not the long/short price book
   tested here; worth a dedicated build. CI still spans zero.
3. **TradFi trend shows textbook crisis alpha** (positive in 2008 and 2022 when
   long-only was hit) at low 11% vol — but standalone Sharpe (0.26) trails its
   own benchmark (0.41). Consistent with the literature: at 16 markets it can't
   reach the documented Sharpe>1 that needs 50–100 markets across asset classes.

### Cash-and-carry (delta-hedged funding harvest, 2026-06-30)

Followed up the carry result with the *correct* structure: a per-asset
delta-neutral position (long spot / short perp on the funding-receiving side) so
price P&L cancels and the return is funding income net of flip cost
(`cash_and_carry_backtest`), over 3y of funding for 12 symbols.

| config | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year |
|---|---|---|---|---|---|
| smoothed (lb7, 5bp/leg) | **8.19** (6.25, 10.54) | +5.2% | 0.6% | −1.6% | 12.7 / 15.5 / 3.3 / **−7.6** |
| high-cost stress (10bp/leg) | 3.81 (1.14, 6.2) | +2.6% | 0.7% | −3.0% | 6.2 / 9.7 / −6.0 / −6.8 |

**The first result with a bootstrap CI clearing zero** — funding income is a
*genuine, persistent* edge (strongly positive 2023–25). **But the Sharpe of 8 is
an artefact, not a prize:** (1) the absolute return is only ~+5%/yr and that is
the idealised *ceiling* — real net is low-single-digits once basis risk, spot
borrow, and hedge slippage (unmodelled) are paid; (2) the 0.6% vol assumes a
*perfect* hedge and so omits the one risk that matters — the basis/funding
blowout during liquidation cascades that actually ruins carry traders; (3) it
still went **negative in 2026**. Verdict: **real but marginal** — a low-single-
digit uncorrelated income stream, operationally heavy (perp+spot+continuous
hedge), and not faithfully representable on the spot paper board, so it is
documented rather than deployed.

**Conclusion:** single-asset directional timing produced artefacts; the
portfolio/cross-sectional reframing produced *weak-but-structurally-genuine*
phenomena (market-neutrality, carry income, crisis alpha) whose limitation is
decay / breadth / significance — not overfitting. The honest next step is forward
validation (add crypto X-sectional momentum to the live board as a market-neutral
challenger) and breadth (a proper cash-and-carry build; many more trend markets),
not declaring a winner.

## 5. Methodological value (for the AI-augmentation tier)

This strand is also evidence for the master's "AI-boost" thesis: the negative
results were produced fast and *honestly* because the harness was built to make
self-deception hard (mark-to-market DD, random-suppression nulls, forward board,
declared search size). The reframing came from a literature search that
correctly diagnosed the framing error. The record of *how the nulls were caught*
is as valuable as the nulls themselves.

## 7. Phase-3 result: trend breadth (2026-06-30)

Following the reframing, we tested the main open thread — **diversified trend
breadth** — using `local_system/portfolio_backtester.py` on a widened public-data
universe built from `load_yf()`.

- **Universe:** 32 TradFi instruments spanning commodities, equity indices,
  rates, and FX (all fetched from yfinance; no collector / no lake).
- **Fixed method:** 120d lookback, 7d rebalance, inverse-vol sizing,
  10% vol-target overlay, 10 bp turnover cost, 252 trading days/year.
- **Search size:** 4 breadth ladders (8 / 16 / 24 / 32 assets).
- **Benchmark:** equal-weight long-only basket on the same tape, same rebalance
  cadence, same cost and vol-target treatment.

Headline: the basket is now genuinely broad, but the trend result still does **not**
clear the rigor gate.

| n | trend Sharpe (95% CI) | ann ret | maxDD | benchmark Sharpe (95% CI) | ann ret | maxDD |
|---|---|---:|---:|---|---:|---:|
| 8 | 0.31 (−0.35, 0.92) | +3.32% | −25.97% | 0.51 (−0.09, 1.21) | +5.54% | −24.26% |
| 16 | 0.01 (−0.63, 0.66) | +0.11% | −30.65% | 0.58 (−0.07, 1.24) | +6.23% | −22.30% |
| 24 | −0.10 (−0.70, 0.49) | −1.06% | −29.89% | 0.73 (0.09, 1.40) | +7.82% | −18.83% |
| 32 | 0.16 (−0.46, 0.76) | +1.71% | −33.87% | 1.15 (0.49, 1.88) | +12.74% | −24.63% |

Per-year Sharpe on the 32-asset trend basket is mixed (+ in 2017/18/20/21/22/26,
− in 2019/23/24/25), so the sign-consistency check fails as well. The 32-asset
benchmark remains stronger than the trend basket on this sample. No challenger.

## 8. Phase-4 result: combine the premia (2026-06-30)

The next thread was not a fourth standalone strategy; it was the portfolio test
implied by the literature: combine the weak-but-real premia with fixed weights
and see whether diversification does the work.

- **Sleeve A:** crypto cross-sectional momentum (`xsec_momentum` lead), vol-
  standardised for the combo.
- **Sleeve B:** cash-and-carry with the high-cost haircut (10 bp/leg), then
  standardised.
- **Sleeve C:** diversified beta passive basket on the broad TradFi universe,
  then standardised.
- **Search size:** 3 sleeves, no weight optimisation; equal-risk sleeves then a
  portfolio vol-target.

Correlation matrix of the equal-risk sleeve inputs was genuinely low
(xsec/carry 0.02, xsec/beta -0.01, carry/beta 0.03), so the premise was at least
plausible. The combined book improved on the beta sleeve and cleared zero, but
it still did **not** beat the best individual sleeve (carry) and the year-by-year
sign pattern failed because 2026 flipped negative.

| metric | value |
|---|---:|
| combined Sharpe (95% CI) | 1.58 (0.79, 2.75) |
| combined ann return | +22.86% |
| combined ann vol | +14.44% |
| combined max DD | -11.76% |
| best sleeve Sharpe | 2.88 (carry) |
| passive TradFi benchmark Sharpe | 1.23 (0.31, 2.27) |

Verdict: honest null — diversification helped versus the passive beta basket,
but the combined book did not clear the full gate (best-sleeve hurdle + sign
consistency).

### Cash-and-carry hardening refresh (2026-07-06)

Re-ran the same forward-checkable carry ceiling with the funding history
extended to 2026-07-06 and the same fixed 7d rolling-sign rule on 12 USDT
perps. Sanity checks still pass: `event_db.load_event_table()` returns 35,350
rows / 34,878 with 4h reaction, and `tradfi_data.load_yf()` still loads `GC=F`
and `^GSPC` cleanly.

|| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
||---|---|---:|---:|---:|---|
|| 1.00 | **3.36** (0.96, 5.75) | +2.58% | 0.77% | -6.53% | 2023:+7.73, 2024:+12.59, 2025:-3.72, 2026:-12.38 |
|| 0.75 | 0.86 (-1.57, 3.34) | +0.58% | 0.67% | -7.76% | 2023:+4.61, 2024:+10.76, 2025:-5.85, 2026:-13.67 |
|| 0.50 | **-2.40** (-4.62, 0.03) | **-1.42%** | 0.59% | -9.01% | 2023:+0.59, 2024:+7.61, 2025:-8.12, 2026:-14.93 |
|| 0.35 | -4.75 (-6.76, -2.60) | -2.62% | 0.55% | -10.07% | 2023:-2.29, 2024:+4.58, 2025:-9.53, 2026:-15.66 |
|| 0.25 | -6.48 (-8.24, -4.60) | -3.42% | 0.53% | -11.35% | 2023:-4.37, 2024:+1.84, 2025:-10.48, 2026:-16.14 |

Interpretation: the raw funding stream is real, but the headline Sharpe is still
an upper-bound / perfect-hedge artefact. Once haircut toward live carry
frictions (borrow, basis, hedge slippage), the edge vanishes and the per-year
sign check fails hard. This is not a challenger; it is the ceiling we should use
to stop over-comparing carry against other sleeves.

### Cash-and-carry full-history hardening refresh (2026-07-07)

Re-ran the carry ceiling on a **full deep-history 12-asset USDT perp funding
set** (ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP) by
backfilling Binance funding history from **2019-09-10 → 2026-07-07** and
collapsing it to daily mean funding rates. Sanity checks still pass:
`event_db.load_event_table()` returns 35,350 rows / 34,878 with 4h reaction, and
`tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly.

| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|---|---|---:|---:|---:|---|
| 1.00 | **8.63** (7.71, 9.78) | +12.27% | 1.42% | -1.63% | 2019:+10.77, 2020:+14.80, 2021:+14.37, 2022:+6.85, 2023:+15.17, 2024:+15.52, 2025:+3.26, 2026:-7.05 |
| 0.75 | 8.24 (7.28, 9.43) | +8.85% | 1.07% | -2.18% | 2019:+10.50, 2020:+14.35, 2021:+14.11, 2022:+5.12, 2023:+12.92, 2024:+14.53, 2025:+0.09, 2026:-9.60 |
| 0.50 | 6.91 (5.84, 8.09) | +5.14% | 0.74% | -3.32% | 2019:+9.93, 2020:+13.44, 2021:+13.58, 2022:+1.85, 2023:+8.99, 2024:+12.59, 2025:-3.72, 2026:-12.23 |
| 0.35 | 5.27 (3.93, 6.59) | +2.91% | 0.55% | -4.08% | 2019:+9.13, 2020:+12.23, 2021:+12.88, 2022:-1.61, 2023:+5.14, 2024:+10.26, 2025:-6.30, 2026:-13.79 |
| 0.25 | **3.31** (1.69, 4.76) | +1.42% | 0.43% | -4.61% | 2019:+8.03, 2020:+10.64, 2021:+11.93, 2022:-4.84, 2023:+1.63, 2024:+7.61, 2025:-8.12, 2026:-14.81 |

Interpretation: the raw hedge is still a perfect-hedge ceiling, and even a
conservative 25% realization haircut leaves a positive CI but fails the
sign-consistency check badly from 2022 onward. The model is therefore a
documented carry ceiling, not a challenger, until basis / borrow / slippage are
modeled explicitly and forward-checked.

### Cash-and-carry hardening refresh (2026-07-09)

Refreshed the same funding-harvest thread on the updated common overlap for the
12 USDT-perp universe. The common funding history now starts **2023-05-03** and
runs through **2026-07-09**. Method stayed fixed: 7d rolling funding sign,
5 bp/leg, equal-weight cross-asset carry, with realism stress applied only to
the funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly (**2,894**
rows each).

| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|---|---|---:|---:|---:|---|
| 1.00 | **8.21** (6.24, 10.14) | +5.10% | 0.62% | -1.63% | 2023:+12.45, 2024:+15.52, 2025:+3.26, 2026:-7.02 |
| 0.75 | 6.19 (3.87, 8.31) | +3.12% | 0.50% | -2.18% | 2023:+10.18, 2024:+14.53, 2025:+0.09, 2026:-9.55 |
| 0.50 | **2.88** (0.24, 5.34) | +1.14% | 0.40% | -3.32% | 2023:+6.39, 2024:+12.59, 2025:-3.72, 2026:-12.14 |
| 0.35 | -0.13 (-2.80, 2.44) | -0.05% | 0.34% | -4.08% | 2023:+2.88, 2024:+10.26, 2025:-6.30, 2026:-13.68 |
| 0.25 | -2.74 (-5.21, -0.27) | -0.84% | 0.31% | -4.61% | 2023:-0.17, 2024:+7.61, 2025:-8.12, 2026:-14.68 |

Verdict stays the same: the funding stream is real, but once we haircut only
the income side to approximate live carry frictions, the edge decays fast and
the per-year sign pattern still fails in 2026. That makes it a documented carry
ceiling, not a challenger. The next honest step is an explicit basis / borrow /
slippage model if we want a truly forward-checkable carry sleeve.

### Cash-and-carry daily refresh (2026-07-10)

Refreshed the same funding-harvest thread at the next daily cutoff. The common
overlap on the 12 USDT-perp universe now runs **2023-05-03 → 2026-07-10** and
the fixed methodology stayed unchanged: 7d rolling funding sign, 5 bp/leg,
equal-weight cross-asset carry, with the realism stress applied only to the
funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly (**2,895**
rows each).

| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|---|---|---:|---:|---:|---|
| 1.00 | **8.20** (6.24, 10.24) | +5.10% | 0.62% | -1.63% | 2023:+12.34, 2024:+15.52, 2025:+3.26, 2026:-6.90 |
| 0.75 | 6.17 (3.90, 8.43) | +3.12% | 0.50% | -2.18% | 2023:+10.06, 2024:+14.53, 2025:+0.09, 2026:-9.43 |
| 0.50 | **2.87** (0.28, 5.42) | +1.14% | 0.40% | -3.32% | 2023:+6.26, 2024:+12.59, 2025:-3.72, 2026:-12.03 |
| 0.35 | -0.14 (-2.82, 2.52) | -0.05% | 0.34% | -4.08% | 2023:+2.76, 2024:+10.26, 2025:-6.30, 2026:-13.58 |
| 0.25 | -2.75 (-5.29, -0.18) | -0.84% | 0.31% | -4.61% | 2023:-0.26, 2024:+7.61, 2025:-8.12, 2026:-14.59 |

Verdict stays the same: the raw hedge is still a perfect-hedge ceiling, and
even the conservative stress views fail the sign-consistency check from 2025–26.
This remains a documented carry ceiling, not a challenger, until basis / borrow
/ slippage are modeled explicitly and forward-checked.

### Cash-and-carry daily refresh (2026-07-11)

Refreshed the same funding-harvest thread again at the next daily cutoff. The
common overlap on the 12 USDT-perp universe now runs **2023-05-03 16:00 UTC →
2026-07-11 00:00 UTC** and the fixed methodology stayed unchanged: 7d rolling
funding sign, 5 bp/leg, equal-weight cross-asset carry, with the realism stress
applied only to the funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly.

|| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
||---|---|---:|---:|---:|---|
|| 1.00 | **8.19** (6.23, 10.33) | +5.10% | 0.62% | -1.63% | 2023:+12.17, 2024:+15.52, 2025:+3.26, 2026:-6.73 |
|| 0.75 | 6.17 (3.89, 8.42) | +3.12% | 0.51% | -2.18% | 2023:+9.93, 2024:+14.53, 2025:+0.09, 2026:-9.27 |
|| 0.50 | **2.88** (0.29, 5.45) | +1.14% | 0.40% | -3.32% | 2023:+6.23, 2024:+12.59, 2025:-3.72, 2026:-11.89 |
|| 0.35 | -0.12 (-2.73, 2.51) | -0.04% | 0.34% | -4.08% | 2023:+2.82, 2024:+10.26, 2025:-6.30, 2026:-13.46 |
|| 0.25 | -2.72 (-5.10, -0.23) | -0.83% | 0.31% | -4.61% | 2023:-0.14, 2024:+7.61, 2025:-8.12, 2026:-14.47 |

Verdict stays the same: the raw hedge is still a perfect-hedge ceiling, and
the conservative stress views still fail the sign-consistency check from 2025–26.
This remains a documented carry ceiling, not a challenger, until basis / borrow
/ slippage are modeled explicitly and forward-checked.

### Cash-and-carry daily refresh (2026-07-12)

Refreshed the same funding-harvest thread at the next daily cutoff with a full
deep Binance backfill on the 12 USDT-perp universe. The common overlap now runs
**2023-05-03 16:00 UTC → 2026-07-12 00:00 UTC**. Method stayed fixed: 7d
rolling funding sign, 5 bp/leg, equal-weight cross-asset carry, with the
realism stress applied only to the funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly (**2,895**
and **2,896** rows).

| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|---|---|---:|---:|---:|---|
| 1.00 | **8.22** (6.27, 10.41) | +5.10% | 0.62% | -1.63% | 2023:+12.45, 2024:+15.52, 2025:+3.26, 2026:-6.67 |
| 0.75 | 6.20 (3.96, 8.45) | +3.12% | 0.50% | -2.18% | 2023:+10.18, 2024:+14.53, 2025:+0.09, 2026:-9.21 |
| 0.50 | **2.90** (0.28, 5.41) | +1.15% | 0.40% | -3.32% | 2023:+6.39, 2024:+12.59, 2025:-3.72, 2026:-11.83 |
| 0.35 | -0.12 (-2.73, 2.52) | -0.04% | 0.34% | -4.08% | 2023:+2.88, 2024:+10.26, 2025:-6.30, 2026:-13.39 |
| 0.25 | -2.73 (-5.11, -0.18) | -0.83% | 0.30% | -4.61% | 2023:-0.17, 2024:+7.61, 2025:-8.12, 2026:-14.40 |

Verdict stays the same: the raw hedge is still a perfect-hedge ceiling, and
the conservative stress views still fail the sign-consistency check from 2025–26.
This remains a documented carry ceiling, not a challenger, until basis / borrow
/ slippage are modeled explicitly and forward-checked.

### Cash-and-carry daily refresh (2026-07-13)

Refreshed the same funding-harvest thread at the next daily cutoff with the full
deep Binance backfill on the 12 USDT-perp universe. The common overlap now runs
**2023-05-03 16:00 UTC → 2026-07-13 00:00 UTC**. Method stayed fixed: 7d
rolling funding sign, 5 bp/leg, equal-weight cross-asset carry, with the
realism stress applied only to the funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly (**2,896**
rows each).

|| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
||---|---|---:|---:|---:|---|
|| 1.00 | **8.20** (6.25, 10.42) | +5.09% | 0.62% | -1.63% | 2023:+12.45, 2024:+15.52, 2025:+3.26, 2026:-6.77 |
|| 0.75 | 6.18 (3.93, 8.52) | +3.12% | 0.50% | -2.18% | 2023:+10.18, 2024:+14.53, 2025:+0.09, 2026:-9.30 |
|| 0.50 | **2.88** (0.30, 5.48) | +1.14% | 0.40% | -3.32% | 2023:+6.39, 2024:+12.59, 2025:-3.72, 2026:-11.91 |
|| 0.35 | -0.14 (-2.74, 2.50) | -0.05% | 0.34% | -4.08% | 2023:+2.88, 2024:+10.26, 2025:-6.30, 2026:-13.46 |
|| 0.25 | -2.74 (-5.17, -0.22) | -0.84% | 0.30% | -4.61% | 2023:-0.17, 2024:+7.61, 2025:-8.12, 2026:-14.47 |

Verdict stays the same: the raw hedge is still a perfect-hedge ceiling, and
the conservative stress views still fail the sign-consistency check from 2025–26.
This remains a documented carry ceiling, not a challenger, until basis / borrow
/ slippage are modeled explicitly and forward-checked.

### Cash-and-carry daily refresh (2026-07-14)

Refreshed the same funding-harvest thread at the next daily cutoff with the full
deep Binance backfill on the 12 USDT-perp universe. The common overlap now runs
**2023-05-03 00:00 UTC → 2026-07-14 00:00 UTC**. Method stayed fixed: 7d
rolling funding sign, 5 bp/leg, equal-weight cross-asset carry, with the
realism stress applied only to the funding income (costs unchanged).

Sanity checks still pass: `event_db.load_event_table()` returns **35,350** rows,
and `tradfi_data.load_yf()` still loads `GC=F` and `^GSPC` cleanly (**2,897**
rows each).

||| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|||---|---|---:|---:|---:|---|
||| 1.00 | **8.20** (6.28, 10.40) | +5.09% | 0.62% | -1.63% | 2023:+12.45, 2024:+15.52, 2025:+3.26, 2026:-6.75 |
||| 0.75 | 6.18 (3.97, 8.52) | +3.11% | 0.50% | -2.18% | 2023:+10.18, 2024:+14.53, 2025:+0.09, 2026:-9.27 |
||| 0.50 | **2.88** (0.32, 5.50) | +1.14% | 0.40% | -3.32% | 2023:+6.39, 2024:+12.59, 2025:-3.72, 2026:-11.87 |
||| 0.35 | -0.14 (-2.71, 2.57) | -0.05% | 0.34% | -4.08% | 2023:+2.88, 2024:+10.26, 2025:-6.30, 2026:-13.41 |
||| 0.25 | -2.74 (-5.15, -0.22) | -0.84% | 0.30% | -4.61% | 2023:-0.17, 2024:+7.61, 2025:-8.12, 2026:-14.41 |

Verdict stays the same: the raw hedge is still a perfect-hedge ceiling, and
the conservative stress views still fail the sign-consistency check from 2025–26.
This remains a documented carry ceiling, not a challenger, until basis / borrow
/ slippage are modeled explicitly and forward-checked.

### Cash-and-carry forward slice refresh (2026-07-15)

Ran a forward-checkable API-capped refresh using the same fixed carry method on
the 12 USDT-perp universe, with the current `funding_history()` window only
covering the recent 500-row slice.

- **Window:** 2026-01-29 → 2026-07-15, 12 symbols, 168 daily bars in common.
- **Method:** `cash_and_carry_backtest`, 7d rolling-sign rule, 5 bp/leg,
  no threshold, equal-weight across assets, block-bootstrap Sharpe CI.
- **Sanity:** `event_db.load_event_table()` = 35,350 rows; `tradfi_data.load_yf()`
  still loads `GC=F` and `^GSPC` cleanly (2,898 rows each).

| haircut | Sharpe (95% CI) | ann ret | ann vol | maxDD | per-year Sharpe |
|---|---|---:|---:|---:|---|
| 1.00 | **-7.80** (-12.14, -5.06) | -3.02% | 0.39% | -1.51% | 2026: **-7.80** |
| 0.50 | -12.21 (-16.50, -9.89) | -4.43% | 0.36% | -2.06% | 2026: **-12.21** |
| 0.25 | -14.35 (-18.74, -12.28) | -5.13% | 0.36% | -2.34% | 2026: **-14.35** |

Interpretation: the forward slice is already negative before any extra realism
stress, so the model is not a challenger. This is exactly why the deep-history
ceiling remains only a ceiling: the perfect-hedge Sharpe overstates live carry,
and the sign consistency collapses as soon as we force a more realistic view of
the current tape.
