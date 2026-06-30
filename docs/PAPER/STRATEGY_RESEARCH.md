# Systematic Strategy Research — Progress & Findings

A research log of the **systematic trading-strategy** strand of the project,
distinct from the Trump event-study papers (see `THESIS_STRUCTURE.md`). This
strand asks a narrower, harder question: **can a simple, explainable systematic
rule produce a real, out-of-sample edge net of costs — and if not, why not?**

The honest answer so far is a **negative result**, and the negative result is
itself the contribution: it reproduces, on our own data and infrastructure, the
well-documented failure of single-asset price-timing — and motivates a reframing
toward the strategy classes the literature actually supports.

_Last updated: 2026-06-30._

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
