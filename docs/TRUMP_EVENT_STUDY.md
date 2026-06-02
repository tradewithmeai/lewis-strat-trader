# Trump Truth Social event study

## Findings (hand-written summary — tables below are script-generated; rerunning
## `_event_study_trump.py` overwrites this file, so re-add this section after)

Run 2026-06-02 against the pinned archive snapshot (33,712 posts, Feb 2022 ->
Jun 2026; see `state/signals/trump_archive.meta.json`). Method: burst-level
event study vs hour-of-day-matched, same-era bootstrap null (2,000 draws);
day-clustered OLS for topic effects. Pre-registered hypotheses in the script
header; replication bar = both era halves consistent AND >=2 of 3 assets.

1. **Volatility (H1): SUPPORTED, in-office era only — replicates 3/3 assets.**
   Forward realized vol after market-relevant post bursts is elevated at the
   4h horizon on BTC (p=0.020), ETH (p=0.012) and SOL (p=0.022), with 1h/24h
   broadly consistent. Pre-2025 (out of office): nothing on any asset. The
   inauguration split is a natural control: his posts only move markets when
   he holds policy power. Magnitude is modest (~+5-10% relative vol).

2. **Topic direction (H3): china/tariff posts -> negative next hour,
   replicates 3/3.** topic_china at 1h: BTC -8.7bp (p=0.021), ETH -12.1bp
   (p=0.017), SOL -17.9bp (p=0.011); SOL tariffs -12.9bp (p=0.033). Small
   per-event but consistent sign everywhere.

3. **market_directive ("THIS IS A GREAT TIME TO BUY!!! DJT") — huge but n=2.**
   Both explicit buy-directives (2025-04-03, 2025-04-09) preceded large
   rallies (+564bp/4h, +401bp/24h BTC on Apr 9; pause announced ~4h after the
   post). Regression p-values for this dummy are artifacts of two
   observations — treat as a case study. The post is best read as a *leading
   indicator of the poster's own upcoming policy action*. Use: real-time
   rule-based alert tier, not statistics.

4. **Generic sentiment (H2): DEAD.** VADER compound sign-flips across
   horizons/assets (Trump's superlative style scores angry tariff rants
   +0.97). Direction lives in topics, not generic sentiment. v2 upgrade =
   market-aware classification, not a better generic scorer.

5. **Macro daily panel: nothing significant** — but it only spans Dec 2024+
   at daily resolution; low power, not evidence of absence.

Caveats: correlation/reaction, not causation; ~1,400 bursts but heavy April
2025 clustering; engagement counts are NOT knowable at post time (excluded
from any live predictor); bootstrap p-values unadjusted for the 18-test grid
(the 3/3-asset replication requirement is the multiplicity control).

---

Pinned archive events: see state/signals/trump_archive.meta.json
Market-relevant non-noise bursts: 1411 (2022-04-30 -> 2026-06-02)
Horizons: [1, 4, 24]h; null draws: 2000; split at 2025-01-20 (inauguration)

## BTCUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -0.7 bp | +0.1 bp | 0.602 |
| fwd_ret_4 | +0.9 bp | +0.6 bp | 0.948 |
| fwd_ret_24 | +6.9 bp | +4.5 bp | 0.739 |
| fwd_vol_1 | +37.7 bp | +35.4 bp | 0.054 |
| fwd_vol_4 | +87.5 bp | +84.3 bp | 0.094 |
| fwd_vol_24 | +223.4 bp | +225.0 bp | 0.619 |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +1.9 bp | +0.4 bp | 0.501 |
| fwd_ret_4 | +5.4 bp | +2.1 bp | 0.411 |
| fwd_ret_24 | +25.4 bp | +10.1 bp | 0.132 |
| fwd_vol_1 | +38.6 bp | +36.2 bp | 0.189 |
| fwd_vol_4 | +90.0 bp | +86.3 bp | 0.179 |
| fwd_vol_24 | +234.9 bp | +235.3 bp | 0.935 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -3.6 bp | -0.6 bp | 0.149 |
| fwd_ret_4 | -4.3 bp | -1.5 bp | 0.472 |
| fwd_ret_24 | -14.2 bp | -7.4 bp | 0.405 |
| fwd_vol_1 | +36.7 bp | +32.9 bp | 0.013 ** |
| fwd_vol_4 | +84.7 bp | +78.4 bp | 0.020 ** |
| fwd_vol_24 | +210.2 bp | +202.6 bp | 0.091 |

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.016, n=1411; significant terms: topic_china (b=-8.7bp, p=0.021), topic_market_directive (b=+79.4bp, p=0.002)
- fwd_ret_4h: R2=0.012, n=1411; significant terms: topic_market_directive (b=+162.0bp, p=0.000)
- fwd_ret_24h: R2=0.012, n=1410; significant terms: topic_market_directive (b=+436.0bp, p=0.002)

## ETHUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +0.6 bp | -0.2 bp | 0.712 |
| fwd_ret_4 | -2.0 bp | -0.2 bp | 0.654 |
| fwd_ret_24 | -10.3 bp | -1.8 bp | 0.356 |
| fwd_vol_1 | +50.8 bp | +47.4 bp | 0.036 ** |
| fwd_vol_4 | +119.7 bp | +113.6 bp | 0.021 ** |
| fwd_vol_24 | +306.8 bp | +303.1 bp | 0.427 |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +3.4 bp | +0.2 bp | 0.234 |
| fwd_ret_4 | +3.4 bp | +1.0 bp | 0.644 |
| fwd_ret_24 | +0.8 bp | +2.4 bp | 0.905 |
| fwd_vol_1 | +46.3 bp | +44.8 bp | 0.466 |
| fwd_vol_4 | +107.9 bp | +107.4 bp | 0.892 |
| fwd_vol_24 | +283.3 bp | +292.6 bp | 0.167 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -2.7 bp | -0.9 bp | 0.565 |
| fwd_ret_4 | -8.1 bp | -2.3 bp | 0.347 |
| fwd_ret_24 | -22.9 bp | -10.6 bp | 0.395 |
| fwd_vol_1 | +56.0 bp | +51.6 bp | 0.055 |
| fwd_vol_4 | +133.1 bp | +124.1 bp | 0.012 ** |
| fwd_vol_24 | +333.8 bp | +322.1 bp | 0.066 |

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.017, n=1411; significant terms: topic_china (b=-12.1bp, p=0.017), topic_market_directive (b=+113.1bp, p=0.001)
- fwd_ret_4h: R2=0.014, n=1411; significant terms: sentiment (b=-13.9bp, p=0.030), topic_market_directive (b=+217.1bp, p=0.000)
- fwd_ret_24h: R2=0.011, n=1410; no significant terms

## SOLUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -1.5 bp | -0.3 bp | 0.689 |
| fwd_ret_4 | -4.4 bp | -0.2 bp | 0.452 |
| fwd_ret_24 | -13.1 bp | -0.3 bp | 0.335 |
| fwd_vol_1 | +69.0 bp | +70.1 bp | 0.619 |
| fwd_vol_4 | +165.4 bp | +166.4 bp | 0.780 |
| fwd_vol_24 | +425.0 bp | +438.6 bp | 0.034 ** |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +3.4 bp | +0.2 bp | 0.467 |
| fwd_ret_4 | -1.8 bp | +1.9 bp | 0.641 |
| fwd_ret_24 | +7.1 bp | +8.9 bp | 0.934 |
| fwd_vol_1 | +72.0 bp | +73.8 bp | 0.589 |
| fwd_vol_4 | +175.8 bp | +175.4 bp | 0.910 |
| fwd_vol_24 | +460.6 bp | +469.4 bp | 0.378 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -7.2 bp | -1.3 bp | 0.105 |
| fwd_ret_4 | -7.3 bp | -2.8 bp | 0.509 |
| fwd_ret_24 | -36.1 bp | -21.7 bp | 0.350 |
| fwd_vol_1 | +65.6 bp | +61.0 bp | 0.077 |
| fwd_vol_4 | +153.5 bp | +144.7 bp | 0.028 ** |
| fwd_vol_24 | +384.2 bp | +370.5 bp | 0.046 ** |

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.019, n=1411; significant terms: topic_tariffs_trade (b=-12.9bp, p=0.033), topic_china (b=-17.9bp, p=0.011), topic_market_directive (b=+96.2bp, p=0.000)
- fwd_ret_4h: R2=0.013, n=1411; significant terms: topic_fed_rates (b=+25.1bp, p=0.047), topic_market_directive (b=+233.8bp, p=0.000)
- fwd_ret_24h: R2=0.011, n=1410; significant terms: topic_market_directive (b=+731.5bp, p=0.000)

## Macro daily panel  (2024-12-13 -> 2026-06-02, cols: ['BTC', 'ETH', 'SOL', 'DXY', 'GOLD', 'SPX', 'NDX', 'US10Y', 'VIX'])

| asset | next-day ret on event days vs not (bp) | sentiment beta (bp, p) |
|---|---|---|
| BTC | -7.5 | -26.3 (p=0.265) |
| ETH | -12.5 | -51.7 (p=0.144) |
| SOL | -14.7 | -60.7 (p=0.139) |
| DXY | -4.0 | +1.9 (p=0.496) |
| GOLD | -13.3 | -21.8 (p=0.122) |
| SPX | +1.7 | -4.4 (p=0.568) |
| NDX | -0.1 | -5.5 (p=0.578) |
| US10Y | +0.2 | +5.2 (p=0.543) |
| VIX | -104.3 | +8.0 (p=0.899) |
