# Placebo (content control): NON-market-relevant Trump posts

## Interpretation (hand-written; script overwrites this file on rerun — re-add after)

Content placebo: Trump's non-market-relevant, non-noise posts (7,232 bursts —
**5× the treatment's 1,422**, so HIGHER power) through the identical pipeline.

**Result — the 1–4h vol effect is content-specific.** Under the primary
inference (cluster-robust regression w/ trailing-vol control), the placebo is
NULL on all vol horizons:
- placebo vol_4h: +1.0bp p=0.232 (full), +1.6bp p=0.214 (2025+)
- treatment vol_4h: **+5.2bp p=0.007 (full), +6.3bp p=0.015 (2025+)**
- placebo vol_1h: +0.5bp p=0.390 (full), +0.2bp p=0.769 (2025+)
- treatment vol_1h: +3.1bp p=0.018 (full)

Effect sizes differ ~5×. The vol-matched i.i.d. null agrees (placebo vol_1h/4h
p=0.30–0.97). So the effect is the market CONTENT, not "Trump posted" or
time-of-day (hour-of-day is matched in the null; trailing vol is balanced:
placebo event 224bp ≈ pool 228bp).

**Methodological by-catch — the day-block null is anti-conservative at large n.**
It flagged placebo vol_1h at p=0.014 (full) / 0.049 (2025+) despite an
economically negligible +0.4bp gap. With 7,229 bursts its SE is tiny, so trivial
differences "significate". This confirms the decision (Amendment 1) to use the
**cluster-robust regression as the PRIMARY inference**, with the bootstrap nulls
as corroboration — and to DEMOTE the day-block null to a sanity check, not a
headline p. The 24h placebo "significance" (p=0.003) is a *lower*-vol artifact
(event 222bp < null 226bp), opposite sign, not a vol-elevation effect.

**Remaining limitation (stated, not engineered around):** this is a *content*
placebo (within-actor). A *different-actor* placebo (another high-salience
poster's real timestamps) would further separate "Trump-specific" from "any
salient market commentator"; no clean second feed is readily available (Musk
would be a positive, not negative, control), so it is logged as future work.

---

Identical pipeline to the main event study, but on Trump's non-market-relevant, non-noise posts (political/other content that should NOT carry crypto-market information). If the 1-4h vol effect is about market CONTENT (not just 'Trump posted' or time-of-day), it should be ABSENT here. Compare against docs/TRUMP_EVENT_STUDY.md.

Placebo (non-market) non-noise bursts: 7232 (2022-02-14 -> 2026-06-02)
Horizons: [1, 4, 24]h; null draws: 2000; split at 2025-01-20 (inauguration)

## BTCUSDT  (37681 hourly bars 2022-02-14 -> 2026-06-03)
bursts joined to bars: 7231 / 7232

### full  (n=7229 bursts across 1473 days)
_event trail_vol_24: mean=224bp p90=370bp | pool: mean=228bp p90=382bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | -0.4 bp | +0.0 bp | 0.565 | 0.461 |
| fwd_ret_4 | +0.2 bp | +0.4 bp | 0.883 | 0.839 |
| fwd_ret_24 | +9.3 bp | +3.0 bp | 0.036 | 0.331 |
| fwd_vol_1 | +35.1 bp | +34.7 bp | 0.449 | 0.014 * |
| fwd_vol_4 | +82.9 bp | +82.1 bp | 0.302 | 0.321 |
| fwd_vol_24 | +221.8 bp | +225.9 bp | 0.003 | 0.091 |

### pre-2025 (out of office)  (n=5134 bursts across 986 days)
_event trail_vol_24: mean=232bp p90=388bp | pool: mean=239bp p90=402bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | -0.0 bp | +0.2 bp | 0.739 | 0.662 |
| fwd_ret_4 | +1.2 bp | +1.2 bp | 0.996 | 0.905 |
| fwd_ret_24 | +14.5 bp | +7.9 bp | 0.080 | 0.423 |
| fwd_vol_1 | +36.2 bp | +35.8 bp | 0.495 | 0.115 |
| fwd_vol_4 | +85.5 bp | +85.1 bp | 0.655 | 0.889 |
| fwd_vol_24 | +230.7 bp | +235.7 bp | 0.003 | 0.058 |

### 2025+ (in office)  (n=2095 bursts across 487 days)
_event trail_vol_24: mean=205bp p90=331bp | pool: mean=204bp p90=337bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | -1.1 bp | -0.6 bp | 0.594 | 0.444 |
| fwd_ret_4 | -2.1 bp | -1.3 bp | 0.708 | 0.729 |
| fwd_ret_24 | -3.4 bp | -7.4 bp | 0.404 | 0.697 |
| fwd_vol_1 | +32.3 bp | +32.3 bp | 0.972 | 0.049 * |
| fwd_vol_4 | +76.5 bp | +75.4 bp | 0.369 | 0.126 |
| fwd_vol_24 | +199.9 bp | +203.7 bp | 0.078 | 0.474 |

### Vol regression with trailing-vol control (all bars, day-clustered SEs)
- full (n=37632, events=7228): vol_1h: event b=+0.48bp (p=0.390); vol_4h: event b=+1.04bp (p=0.232); vol_24h: event b=-5.39bp (p=0.004)
- 2025+ (n=11954, events=2095): vol_1h: event b=+0.24bp (p=0.769); vol_4h: event b=+1.62bp (p=0.214); vol_24h: event b=-4.65bp (p=0.109)

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.000, n=7231; no significant terms
- fwd_ret_4h: R2=0.000, n=7231; no significant terms
- fwd_ret_24h: R2=0.000, n=7229; no significant terms
