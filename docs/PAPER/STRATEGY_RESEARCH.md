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

## 5. Methodological value (for the AI-augmentation tier)

This strand is also evidence for the master's "AI-boost" thesis: the negative
results were produced fast and *honestly* because the harness was built to make
self-deception hard (mark-to-market DD, random-suppression nulls, forward board,
declared search size). The reframing came from a literature search that
correctly diagnosed the framing error. The record of *how the nulls were caught*
is as valuable as the nulls themselves.
