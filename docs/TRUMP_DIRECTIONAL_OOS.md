# Trump-Post Directional Feature Test — OOS Results

_Generated 2026-06-16. Read-only analysis; no strategy code modified._

Using: `state/signals/trump_events.parquet` (keyword classifier, no LLM).
Bars: BTCUSDT 1h from lake (`LAKE_ROOT`). Cost: 0.24% round-trip.

---

## Corpus

- 33,960 posts (CNN pinned snapshot, Feb 2022 – Jun 2026)
- 1,865 market-relevant non-noise posts
- **1,421 unique burst-hours** after 30-min burst collapsing + hourly dedup

---

## Holdout Setup

| | |
|---|---|
| Split index | burst #1,136 / 1,421 (80/20 by time) |
| **Split timestamp** | **2025-10-29 05:00 UTC** |
| Train | 1,136 bursts · 2022-04-30 → 2025-10-27 |
| OOS | 285 bursts · 2025-10-29 → 2026-06-15 |

OOS is entirely in-office (post-inauguration), covering the 2025–26 tariff/trade-policy regime.

---

## OOS Topic Counts

| Feature | Train n | OOS n |
|---|---|---|
| china | 345 | 70 |
| tariffs_trade | 266 | 104 |
| fed_rates | 316 | 55 |
| markets_mention | 55 | 32 |
| reassurance | 12 | 1 |
| crypto_mention | 26 | 3 |
| market_directive | 2 | **0** |

---

## OOS Directional Feature Results

Cost: 0.24% RT per trade. Permutation test: 2,000 random-sign draws.

### 1h forward return

| Feature | N | Raw mean | Gross | Net | %win | p (1-sided) | Verdict |
|---|---|---|---|---|---|---|---|
| market_directive (long) | 0 | — | — | — | — | — | not testable |
| china (short) | 70 | −0.3 bp | +0.3 bp | −23.7 bp | 44.3% | 0.497 | no edge |
| tariffs_trade (short) | 104 | +2.9 bp | −2.9 bp | −26.9 bp | 39.4% | 0.796 | no edge |
| crypto_mention (long) | 3 | −4.6 bp | −4.6 bp | −28.6 bp | 66.7% | 0.647 | no edge |
| markets_mention (long) | 32 | −1.7 bp | −1.7 bp | −25.7 bp | 53.1% | 0.577 | no edge |
| fed_rates (long) | 55 | +9.8 bp | +9.8 bp | −14.2 bp | 52.7% | 0.097 | no edge |
| sentiment sign (all) | 285 | −0.0 bp | +0.0 bp | −0.0 bp | 46.0% | 0.021 | no edge |

### 4h forward return

| Feature | N | Raw mean | Gross | Net | %win | p (1-sided) | Verdict |
|---|---|---|---|---|---|---|---|
| market_directive (long) | 0 | — | — | — | — | — | not testable |
| **china (short)** | **70** | **−21.5 bp** | **+21.5 bp** | **−2.5 bp** | **58.6%** | **0.025** | **no edge** |
| tariffs_trade (short) | 104 | −1.2 bp | +1.2 bp | −22.8 bp | 44.2% | 0.429 | no edge |
| crypto_mention (long) | 3 | −8.3 bp | −8.3 bp | −32.3 bp | 0.0% | 1.000 | no edge |
| markets_mention (long) | 32 | +13.3 bp | +13.3 bp | −10.7 bp | 50.0% | 0.275 | no edge |
| fed_rates (long) | 55 | +11.3 bp | +11.3 bp | −12.7 bp | 58.2% | 0.262 | no edge |
| sentiment sign (all) | 285 | −0.0 bp | −0.0 bp | −0.0 bp | 42.8% | 0.288 | no edge |

---

## Feature-by-Feature Notes

### market_directive
Both corpus events are in training. Cannot test OOS.

| Date | Split | 1h | 4h | Text (truncated) |
|---|---|---|---|---|
| 2025-04-03 | TRAIN | +43 bp | +146 bp | *"THE MARKETS are going to BOOM…"* |
| 2025-04-09 | TRAIN | +121 bp | +194 bp | *"IMPERATIVE that Republicans pass the Tax Cut Bill…"* |

n=2 globally. Qualitative case study only.

### china (short) — closest to a signal
In-sample direction consistent: train 1h mean −8.6 bp (aligns with regression β=−8.0 bp, p=0.016).
OOS at 4h: gross=+21.5 bp, win rate 58.6%, p=0.025 one-sided — directionally real.
**Net = −2.5 bp after 24 bp RT costs.** Signal exists, too thin to trade at taker rates.
Direction does not hold at 1h in OOS (raw −0.3 bp).

### tariffs_trade (short)
In-sample signal is inconsistent — train 4h mean is +8.3 bp (wrong direction).
OOS shows no edge at either horizon.

### crypto_mention (long)
3 OOS events — untestable. Train showed positive tendency (26 events, 1h +11.9 bp, 4h +20.4 bp).

### reassurance (long)
1 OOS event (2025-11-01: 1h=+21 bp, 4h=+10 bp — directionally consistent). n=1, inconclusive.
Train: 12 events, mean 1h +11.7 bp, 4h +22.5 bp.

### markets_mention (long)
Strong in-sample (train 1h +27.9 bp, 4h +26.2 bp). OOS 1h flips to −1.7 bp; 4h +13.3 bp
is positive but well below the 24 bp cost floor.

### VADER sentiment
1h permutation p=0.021 looks interesting but gross mean is 0.0 bp — no size, no edge.

---

## In-Sample vs OOS Consistency

| Feature | Train 1h | Train 4h | OOS 1h | OOS 4h |
|---|---|---|---|---|
| china (short, raw) | −8.6 bp | −0.6 bp | −0.3 bp | −21.5 bp |
| tariffs_trade (short, raw) | −4.3 bp | +8.3 bp | +2.9 bp | −1.2 bp |
| crypto_mention (long, raw) | +11.9 bp | +20.4 bp | −4.6 bp | −8.3 bp |
| markets_mention (long, raw) | +27.9 bp | +26.2 bp | −1.7 bp | +13.3 bp |

China/4h is the only direction that is consistent across train and OOS.

---

## Full-Corpus Regression (Day-Clustered SEs, Replication Check)

Matches `docs/TRUMP_EVENT_STUDY.md` within rounding:

- `fwd_ret_1h` (n=1421, R²=0.013): `topic_market_directive` b=+80.6 bp p=0.002; `topic_china` b=−8.0 bp p=0.016; `topic_markets` b=+17.1 bp p=0.095
- `fwd_ret_4h` (n=1421, R²=0.011): `topic_market_directive` b=+163.2 bp p=0.000

---

## Conclusion

**No feature has a stable directional edge net of costs in the OOS window. The answer is no.**

1. **market_directive** — n=2 globally, both in training, zero OOS. Not a repeatable signal.
2. **china/short at 4h** — The most interesting result. Directionally real in OOS (gross +21.5 bp, p=0.025), consistent with in-sample regression. But **net = −2.5 bp** after 24 bp RT costs. The signal is too small to trade at market-taker rates. Could be re-examined at limit-order cost (~5 bp RT).
3. **All other features** — Either too few OOS events, inconsistent direction across train/OOS, or near-zero size.

This confirms the paper's RQ2/RQ3 finding: posts affect *how much* BTC moves (the vol effect), not *which way*, and not by enough to trade after realistic costs. The china/4h result is the only crack in that conclusion, and it is one 24 bp cost assumption away from being uninvestable.
