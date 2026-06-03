# Phase 2 — reaction modelling (EXPLORATORY — per Amendment 1)

## Interpretation (hand-written; the script overwrites this file on rerun — re-add after)

Run 2026-06-03 at 100% LLM coverage (frozen label set, `SIGNAL_MANIFEST.json`).

- **RQ2 (does the directional signal predict return sign?): NULL.** The continuous
  `signal` term is insignificant on every asset/horizon (all p > 0.4). The
  FinBERT-only directional signal (LLM-leak-immune robustness) is likewise null.
- **RQ3 (tradeable edge): NULL on every cell** — all 12 (3 assets × {all,policy} ×
  {LLM,FinBERT}) lose money net of 0.24% cost, strongly negative Sharpe. Robust to
  the signal source, so it is not an artifact of the LLM training-corpus leak.
- **The 8 BH-FDR "survivors" are ALL `topic_market_directive` and must NOT be read
  as 8 predictive findings.** That dummy is the **n=2 directive class** (the two
  "GREAT TIME TO BUY"-type posts, both of which preceded large rallies). The huge
  betas (+166 to +724bp) and p=0.000 are the mechanical artifact of a
  two-observation dummy landing on two large-move events — exactly the
  small-n/over-fitting trap flagged in `METHODOLOGY_REVIEW.md`. Report as the
  qualitative **case study** (n=2), not as confirmed alpha.
- **`topic_china` → negative 1h return** (BTC −8.0bp p=0.027, ETH −10.3bp p=0.033,
  SOL −17.1bp p=0.016) appears but does NOT survive FDR. Per Amendment 1 this is a
  **consistency check** (tariffs/China escalation is known to be risk-off), not a
  novel finding — and not reported as one (circularity guard).

**Combined paper finding:** market-relevant posts move short-horizon (1–4h)
**volatility** (RQ1, robust), not **direction** (RQ2/RQ3 null after costs). The
accused-manipulation "buy" directives are a compelling but statistically thin
(n=2) case study. An honest, publishable result.

---

LLM coverage of market-relevant posts: 100.0%
Bursts: 1408  (2022-04-30 -> 2026-06-02)
Pre-registration: docs/PAPER/PREREGISTRATION.md | costs 0.24% RT

## Confirmatory OLS (day-clustered SEs, trailing-vol controlled)

### BTCUSDT  (bursts joined: 1408)

### ETHUSDT  (bursts joined: 1408)

### SOLUSDT  (bursts joined: 1408)

Grid: 72 tests; BH-FDR q=0.1: 8 survive correction.

| asset | target | term | beta | p | FDR-sig |
|---|---|---|---|---|---|
| BTCUSDT | fwd_ret_4 | topic_market_directive | +166.8bp | 0.000 | YES |
| ETHUSDT | fwd_ret_4 | topic_market_directive | +234.3bp | 0.000 | YES |
| SOLUSDT | fwd_ret_24 | topic_market_directive | +724.1bp | 0.000 | YES |
| SOLUSDT | fwd_ret_4 | topic_market_directive | +269.1bp | 0.000 | YES |
| SOLUSDT | fwd_ret_1 | topic_market_directive | +88.2bp | 0.000 | YES |
| ETHUSDT | fwd_ret_1 | topic_market_directive | +108.3bp | 0.000 | YES |
| BTCUSDT | fwd_ret_1 | topic_market_directive | +76.1bp | 0.002 | YES |
| BTCUSDT | fwd_ret_24 | topic_market_directive | +412.5bp | 0.004 | YES |
| SOLUSDT | fwd_ret_1 | topic_china | -17.1bp | 0.016 |  |
| ETHUSDT | fwd_vol_24 | topic_tariffs_trade | +29.7bp | 0.020 |  |
| BTCUSDT | fwd_ret_1 | topic_china | -8.0bp | 0.027 |  |
| ETHUSDT | fwd_ret_1 | topic_china | -10.3bp | 0.033 |  |
| BTCUSDT | fwd_vol_24 | topic_market_directive | +153.3bp | 0.035 |  |
| SOLUSDT | fwd_vol_24 | topic_china | +29.6bp | 0.041 |  |
| SOLUSDT | fwd_ret_1 | topic_tariffs_trade | -12.0bp | 0.062 |  |
| ETHUSDT | fwd_ret_1 | topic_tariffs_trade | -9.3bp | 0.073 |  |
| ETHUSDT | fwd_ret_24 | topic_market_directive | +465.0bp | 0.073 |  |
| ETHUSDT | fwd_ret_24 | topic_china | -39.4bp | 0.126 |  |
| BTCUSDT | fwd_vol_1 | topic_tariffs_trade | -3.5bp | 0.157 |  |
| SOLUSDT | fwd_vol_24 | topic_tariffs_trade | +20.7bp | 0.193 |  |
| SOLUSDT | fwd_vol_24 | topic_market_directive | +229.4bp | 0.194 |  |
| ETHUSDT | fwd_vol_4 | topic_tariffs_trade | +9.1bp | 0.206 |  |
| ETHUSDT | fwd_vol_1 | signal | +11.5bp | 0.209 |  |
| SOLUSDT | fwd_vol_4 | topic_market_directive | -73.8bp | 0.238 |  |
| BTCUSDT | fwd_ret_4 | topic_tariffs_trade | +9.4bp | 0.248 |  |
| ETHUSDT | fwd_vol_24 | topic_market_directive | +189.2bp | 0.252 |  |
| SOLUSDT | fwd_ret_24 | topic_china | -37.9bp | 0.288 |  |
| BTCUSDT | fwd_vol_24 | topic_tariffs_trade | +8.4bp | 0.294 |  |
| SOLUSDT | fwd_vol_1 | topic_china | -5.1bp | 0.325 |  |
| BTCUSDT | fwd_vol_1 | topic_china | -2.5bp | 0.353 |  |
| ETHUSDT | fwd_ret_24 | signal | +38.2bp | 0.369 |  |
| SOLUSDT | fwd_vol_4 | topic_china | +7.3bp | 0.379 |  |
| ETHUSDT | fwd_vol_1 | topic_market_directive | +30.0bp | 0.402 |  |
| BTCUSDT | fwd_ret_1 | topic_tariffs_trade | -3.0bp | 0.403 |  |
| SOLUSDT | fwd_vol_1 | topic_tariffs_trade | -3.8bp | 0.405 |  |
| ETHUSDT | fwd_ret_4 | topic_china | -9.9bp | 0.428 |  |
| ETHUSDT | fwd_vol_1 | topic_china | -2.8bp | 0.430 |  |
| BTCUSDT | fwd_vol_1 | topic_market_directive | +20.0bp | 0.443 |  |
| SOLUSDT | fwd_ret_24 | topic_tariffs_trade | -23.9bp | 0.472 |  |
| SOLUSDT | fwd_ret_4 | topic_china | -10.9bp | 0.478 |  |
| SOLUSDT | fwd_vol_4 | signal | -9.3bp | 0.483 |  |
| ETHUSDT | fwd_vol_24 | signal | +11.5bp | 0.485 |  |
| SOLUSDT | fwd_ret_4 | signal | -14.2bp | 0.543 |  |
| SOLUSDT | fwd_vol_1 | signal | +6.9bp | 0.547 |  |
| SOLUSDT | fwd_ret_1 | signal | -8.1bp | 0.552 |  |
| BTCUSDT | fwd_vol_4 | signal | -4.5bp | 0.574 |  |
| SOLUSDT | fwd_vol_24 | signal | -12.1bp | 0.584 |  |
| SOLUSDT | fwd_vol_4 | topic_tariffs_trade | +4.0bp | 0.592 |  |
| ETHUSDT | fwd_vol_4 | topic_china | +3.7bp | 0.619 |  |
| BTCUSDT | fwd_vol_24 | signal | -6.8bp | 0.626 |  |
| BTCUSDT | fwd_vol_4 | topic_market_directive | +23.2bp | 0.637 |  |
| BTCUSDT | fwd_ret_24 | signal | +12.1bp | 0.647 |  |
| ETHUSDT | fwd_vol_4 | signal | -4.5bp | 0.673 |  |
| ETHUSDT | fwd_ret_4 | topic_tariffs_trade | +5.2bp | 0.677 |  |
| BTCUSDT | fwd_vol_1 | signal | +2.3bp | 0.683 |  |
| BTCUSDT | fwd_vol_4 | topic_china | +1.8bp | 0.683 |  |
| BTCUSDT | fwd_ret_24 | topic_tariffs_trade | +7.0bp | 0.690 |  |
| SOLUSDT | fwd_ret_24 | signal | -19.3bp | 0.699 |  |
| BTCUSDT | fwd_ret_4 | signal | +5.0bp | 0.702 |  |
| BTCUSDT | fwd_vol_24 | topic_china | +2.6bp | 0.726 |  |
| ETHUSDT | fwd_vol_1 | topic_tariffs_trade | -1.3bp | 0.753 |  |
| ETHUSDT | fwd_vol_24 | topic_china | +3.6bp | 0.784 |  |
| ETHUSDT | fwd_ret_1 | signal | -3.1bp | 0.785 |  |
| SOLUSDT | fwd_ret_4 | topic_tariffs_trade | +1.9bp | 0.886 |  |
| ETHUSDT | fwd_ret_24 | topic_tariffs_trade | +3.5bp | 0.894 |  |
| BTCUSDT | fwd_vol_4 | topic_tariffs_trade | -0.5bp | 0.911 |  |
| BTCUSDT | fwd_ret_4 | topic_china | -0.8bp | 0.917 |  |
| ETHUSDT | fwd_vol_4 | topic_market_directive | -5.5bp | 0.922 |  |
| SOLUSDT | fwd_vol_1 | topic_market_directive | +2.9bp | 0.935 |  |
| ETHUSDT | fwd_ret_4 | signal | +1.1bp | 0.958 |  |
| BTCUSDT | fwd_ret_1 | signal | -0.3bp | 0.967 |  |
| BTCUSDT | fwd_ret_24 | topic_china | -0.3bp | 0.986 |  |

## OOS tradeable-edge (final 20% by time, net of costs, 4h hold)
| asset | subset | n | mean net | Sharpe | 95% CI | verdict |
|---|---|---|---|---|---|---|
| BTCUSDT | all/LLMsig | 200 | -26.1bp | -12.54 | [-43.10, -6.82] | no edge |
| BTCUSDT | policy/LLMsig | 144 | -26.7bp | -15.15 | [-49.76, -4.50] | no edge |
| BTCUSDT | all/FinBERTsig | 282 | -26.0bp | -13.47 | [-35.36, -17.06] | no edge |
| BTCUSDT | policy/FinBERTsig | 153 | -23.0bp | -12.87 | [-32.33, -14.41] | no edge |
| ETHUSDT | all/LLMsig | 200 | -31.1bp | -10.26 | [-33.97, -4.14] | no edge |
| ETHUSDT | policy/LLMsig | 144 | -35.0bp | -13.52 | [-39.69, -5.35] | no edge |
| ETHUSDT | all/FinBERTsig | 282 | -28.4bp | -10.35 | [-31.79, -9.79] | no edge |
| ETHUSDT | policy/FinBERTsig | 153 | -27.1bp | -10.48 | [-30.54, -9.45] | no edge |
| SOLUSDT | all/LLMsig | 200 | -21.0bp | -6.51 | [-23.56, +3.24] | no edge |
| SOLUSDT | policy/LLMsig | 144 | -24.0bp | -8.50 | [-29.12, +6.39] | no edge |
| SOLUSDT | all/FinBERTsig | 282 | -26.0bp | -8.71 | [-27.25, -8.78] | no edge |
| SOLUSDT | policy/FinBERTsig | 153 | -17.2bp | -6.17 | [-21.39, -0.90] | no edge |

**RQ3 verdict:** NO tradeable edge after costs
