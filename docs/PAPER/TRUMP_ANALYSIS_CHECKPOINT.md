# Trump Analysis Checkpoint

_Written 2026-06-16. Summary of all Trump-post volatility and directional-edge work to date._

---

## Artifacts on Disk

| File | Description |
|---|---|
| `state/signals/trump_archive.parquet` | Pinned CNN mirror snapshot — 33,960 posts, Feb 2022 – Jun 2026 |
| `state/signals/trump_archive.meta.json` | Snapshot provenance (URL, etag, pulled_at, byte count) |
| `state/signals/trump_events.parquet` | Keyword-classified event table (33,960 rows, 24 cols) |
| `local_system/signals/trump_classify.py` | Rule-based classifier → topic dummies + VADER sentiment + burst IDs |
| `local_system/signals/trump_archive.py` | Archive loader (pinned snapshot, no live fetch) |
| `local_system/signals/trump_alert.py` | Live post poller → tier A/B alerts wired into paper_trader tick loop |
| `local_system/signals/trump_signal.py` | Merge layer: FinBERT local + LLM JSONL → `trump_signal.parquet` (requires `--extra research`) |
| `local_system/signals/trump_signal_llm.py` | GPT-4.1-mini LLM classifier (requires OpenAI key + torch stack) |
| `local_system/signals/trump_signal_local.py` | FinBERT local pass (requires torch, sentence-transformers) |
| `_event_study_trump.py` | Main event study: bootstrap null, vol regression, return regression |
| `_val_trump_overlay.py` | Disjoint-window validation of the Trump vol overlay entry filter |
| `_phase2_reaction.py` | Phase 2 confirmatory: BH-FDR OLS grid + OOS tradeable-edge test (needs `trump_signal.parquet`) |
| `_event_study_trump.py --placebo` | Content placebo run (non-market-relevant posts through same pipeline) |
| `docs/TRUMP_EVENT_STUDY.md` | Results of the main event study (auto-written by `_event_study_trump.py`) |
| `docs/TRUMP_DIRECTIONAL_OOS.md` | Simple keyword-only OOS directional feature test (written 2026-06-16) |
| `docs/PAPER/UNDERGRAD_PAPER.md` | Full IMRaD draft: "Posts as Events: Intraday Cryptocurrency Volatility…" |
| `docs/PAPER/PHASE2_RESULTS.md` | Phase 2 results (written by `_phase2_reaction.py --confirm`; requires 95%+ LLM coverage) |

**Not present** (require `--extra research` install + API key): `trump_signal.parquet`, `trump_signal_local.parquet`, `trump_signal_llm.jsonl`.

---

## Archive & Classification Counts

| Metric | Value |
|---|---|
| Total posts in archive | 33,960 |
| Date range | 2022-02-14 → 2026-06-15 |
| Market-relevant (any econ topic hit) | 2,754 (8.1%) |
| Noise posts (endorsements, congratulations, boilerplate) | 8,358 |
| Market-relevant **and** non-noise | 1,865 |
| Unique burst-hours (30-min burst collapse + hourly dedup) | **1,421** |
| Burst range | 2022-04-30 → 2026-06-15 |

**Keyword topic counts (post level, full archive):**

| Topic | Posts | % |
|---|---|---|
| tariffs_trade | 467 | 1.4% |
| china | 471 | 1.4% |
| fed_rates | 606 | 1.8% |
| crypto | 37 | 0.1% |
| markets | 93 | 0.3% |
| market_directive | 2 | 0.006% |
| reassurance | 13 | 0.04% |

---

## BTCUSDT Holdout Setup

- **Bars**: 36,193 hourly bars from the local crypto-lake-rs parquet store (2022-04-30 → 2026-06-16)
- **Join**: burst-hours left-joined to bar features (`fwd_ret_1h`, `fwd_ret_4h`, `trail_vol_24`)
- **Split**: final 20% by burst-time order (no shuffling)

| Split | n | Date range |
|---|---|---|
| Train | 1,136 | 2022-04-30 → 2025-10-27 |
| **OOS** | **285** | **2025-10-29 → 2026-06-15** |

The OOS window is entirely post-inauguration (in-office, 2025–26 tariff regime).

**OOS topic counts:**

| Topic | OOS n |
|---|---|
| tariffs_trade | 104 |
| china | 70 |
| fed_rates | 55 |
| markets_mention | 32 |
| crypto_mention | 3 |
| reassurance | 1 |
| market_directive | **0** |

---

## Simple Feature Tests (Keyword-Only, No LLM)

Cost assumption: **0.24% round-trip** (0.1% taker × 2 + 2 bp slippage × 2).
Permutation test: 2,000 random-sign draws (one-sided, expected direction).

### 4h forward return (primary horizon)

| Feature | Expected dir | OOS n | Raw mean | Gross | Net | %win | p (1-sided) | Verdict |
|---|---|---|---|---|---|---|---|---|
| market_directive | long | 0 | — | — | — | — | — | not testable |
| **china** | **short** | **70** | **−21.5 bp** | **+21.5 bp** | **−2.5 bp** | **58.6%** | **0.025** | **no edge** |
| tariffs_trade | short | 104 | −1.2 bp | +1.2 bp | −22.8 bp | 44.2% | 0.429 | no edge |
| crypto_mention | long | 3 | −8.3 bp | −8.3 bp | −32.3 bp | 0.0% | 1.000 | no edge |
| reassurance | long | 1 | — | — | — | — | — | not testable |
| markets_mention | long | 32 | +13.3 bp | +13.3 bp | −10.7 bp | 50.0% | 0.275 | no edge |
| sentiment sign | long | 285 | −0.0 bp | −0.0 bp | −0.0 bp | 42.8% | 0.288 | no edge |

### 1h forward return

| Feature | OOS n | Gross | Net | p (1-sided) | Verdict |
|---|---|---|---|---|---|
| china (short) | 70 | +0.3 bp | −23.7 bp | 0.497 | no edge |
| tariffs_trade (short) | 104 | −2.9 bp | −26.9 bp | 0.796 | no edge |
| fed_rates (long) | 55 | +9.8 bp | −14.2 bp | 0.097 | no edge |
| sentiment sign | 285 | +0.0 bp | −0.0 bp | 0.021 | no edge |

### market_directive — qualitative case study only

| Date | Split | 1h return | 4h return | Text (truncated) |
|---|---|---|---|---|
| 2025-04-03 | TRAIN | +43 bp | +146 bp | *"THE MARKETS are going to BOOM…"* |
| 2025-04-09 | TRAIN | +121 bp | +194 bp | *"IMPERATIVE that Republicans pass the Tax Cut Bill…"* |

n=2 globally, both in training. Not a repeatable signal by any statistical standard.

### In-sample vs OOS consistency

| Feature | Train 1h | Train 4h | OOS 1h | OOS 4h |
|---|---|---|---|---|
| china (raw) | −8.6 bp | −0.6 bp | −0.3 bp | −21.5 bp |
| tariffs_trade (raw) | −4.3 bp | +8.3 bp | +2.9 bp | −1.2 bp |
| crypto_mention (raw) | +11.9 bp | +20.4 bp | −4.6 bp | −8.3 bp |
| markets_mention (raw) | +27.9 bp | +26.2 bp | −1.7 bp | +13.3 bp |

China/4h is the only direction consistent across both splits.

---

## Full-Corpus Regression (Replication Check)

Day-clustered OLS, all 1,421 joined burst-hours. Matches `docs/TRUMP_EVENT_STUDY.md`:

- **fwd_ret_1h** (n=1421, R²=0.013): `topic_market_directive` b=+80.6 bp p=0.002; `topic_china` b=−8.0 bp p=0.016
- **fwd_ret_4h** (n=1421, R²=0.011): `topic_market_directive` b=+163.2 bp p=0.000

---

## Conclusion

**No feature has a stable directional edge net of realistic costs in the OOS window.**

- **Volatility effect is real**: market-relevant posts are followed by +3–5 bp elevated 1–4h realised vol (day-clustered regression p<0.01), surviving a vol-matched null and a content placebo. This is the paper's positive finding (RQ1).
- **Direction is not predictable** (RQ2): no topic dummy or VADER sentiment produces a consistent signed return in OOS.
- **No tradeable edge** (RQ3): the closest result is china/short at 4h (gross +21.5 bp, p=0.025, win rate 58.6%), but net = **−2.5 bp** after 24 bp round-trip costs. The signal is real but smaller than the cost of acting on it at market-taker rates. Limit-order execution (~5 bp RT) would reduce the hurdle to ~6 bp — still marginal and untested.
- **market_directive** posts are spectacular individually but n=2 globally; not a strategy.

The paper's conclusion stands at the keyword-only classification level: _posts move how much BTC moves over the next few hours, not which way, and not by enough to trade after costs._

**Next step if revisiting**: run `_phase2_reaction.py --confirm` once LLM coverage of market-relevant posts reaches ≥95% — the LLM stance/conviction/policy-signal columns may separate the directional signal from the noise in a way keyword dummies cannot.
