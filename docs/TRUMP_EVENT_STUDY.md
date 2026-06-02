# Trump Truth Social event study

## Findings (hand-written summary — tables below are script-generated; rerunning
## `_event_study_trump.py` overwrites this file, so re-add this section after)

Run 2026-06-02 against the pinned archive snapshot (33,712 posts, Feb 2022 ->
Jun 2026; `state/signals/trump_archive.meta.json`). Method: burst-level event
study vs a bootstrap null matched on hour-of-day bucket AND trailing-24h-vol
quintile, same era (2,000 draws); plus an all-bars regression of forward vol
on an event dummy controlling for trailing vol (day-clustered SEs). The
trailing-vol matching is the critical adversarial control: vol clusters and
posting timing is endogenous ("he posts when markets are already moving"), so
an unmatched null would manufacture the effect.

1. **Short-horizon vol effect: SURVIVES the endogenous-timing control.**
   After market-relevant post bursts, 1-4h forward vol is higher than
   vol-matched null hours, and the event dummy stays significant with
   trailing vol controlled: BTC +3.0bp/1h (p=0.019), +5.1bp/4h (p=0.008)
   full sample; +6.3bp/4h (p=0.015) in-office. ETH similar (full sample
   p=0.019-0.047); SOL only in-office (+8.5bp/4h, p=0.033). The **24h effect
   is gone everywhere** — that part was vol clustering. Note BTC/ETH/SOL
   co-move at ~0.92, so the three assets are one effect measured three
   times, not independent confirmations. Magnitude: ~+4-8% relative vol for
   1-4 hours. Real but small; a vol/timing input, not an alpha source.

2. **Era contrast (weaker than first claimed):** under the vol-matched null
   the in-office era shows the effect most consistently (all three assets at
   4h), but BTC also shows it pre-2025 (p=0.011 at 4h). "Only when in
   office" was partly an artifact of the cruder null. Also "in office"
   coincides with the 2025 tariff-war regime, so the split is not a clean
   power-effect isolator.

3. **Topic direction: china/tariff posts -> negative next hour, same sign on
   all three (co-moving) assets.** topic_china 1h: BTC -8.7bp (p=0.021), ETH
   -12.1bp (p=0.017), SOL -17.9bp (p=0.011); SOL tariffs -12.9bp (p=0.033).

4. **market_directive ("THIS IS A GREAT TIME TO BUY!!! DJT") — huge but n=2.**
   Both explicit buy-directives (2025-04-03, 2025-04-09) preceded large
   rallies (Apr 9: +564bp/4h, +401bp/24h BTC; the tariff pause was announced
   ~4h after the post). Regression p-values on a 2-observation dummy are
   artifacts — treat as a case study. Read: the post is a *leading indicator
   of the poster's own upcoming policy action*. Use as a real-time
   rule-based alert tier, not statistics.

5. **Generic sentiment (VADER): DEAD.** Sign-flips across horizons/assets
   (Trump's superlative style scores angry tariff rants +0.97). Direction
   lives in topics; v2 = market-aware classification of the relevant subset.

6. **Macro daily panel: nothing significant** (only Dec 2024+ daily; low
   power, not evidence of absence).

Caveats: correlation/reaction, not causation; heavy April-2025 clustering;
engagement counts are NOT knowable at post time (exclude from live
predictors); p-values unadjusted for the test grid — the surviving claims are
the ones that passed the pre-registered controls, not the grid's best cells.

---

Pinned archive events: see state/signals/trump_archive.meta.json
Market-relevant non-noise bursts: 1411 (2022-04-30 -> 2026-06-02)
Horizons: [1, 4, 24]h; null draws: 2000; split at 2025-01-20 (inauguration)

## BTCUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -0.7 bp | +0.2 bp | 0.569 |
| fwd_ret_4 | +0.9 bp | +0.9 bp | 0.959 |
| fwd_ret_24 | +6.9 bp | +4.7 bp | 0.740 |
| fwd_vol_1 | +37.7 bp | +35.0 bp | 0.021 ** |
| fwd_vol_4 | +87.5 bp | +82.8 bp | 0.008 ** |
| fwd_vol_24 | +223.4 bp | +224.0 bp | 0.866 |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +1.9 bp | +0.4 bp | 0.473 |
| fwd_ret_4 | +5.4 bp | +2.1 bp | 0.408 |
| fwd_ret_24 | +25.4 bp | +10.6 bp | 0.126 |
| fwd_vol_1 | +38.6 bp | +35.4 bp | 0.055 |
| fwd_vol_4 | +90.0 bp | +84.1 bp | 0.011 ** |
| fwd_vol_24 | +234.9 bp | +231.8 bp | 0.473 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -3.6 bp | -0.5 bp | 0.145 |
| fwd_ret_4 | -4.3 bp | -1.1 bp | 0.410 |
| fwd_ret_24 | -14.2 bp | -7.2 bp | 0.446 |
| fwd_vol_1 | +36.7 bp | +33.6 bp | 0.038 ** |
| fwd_vol_4 | +84.7 bp | +78.3 bp | 0.007 ** |
| fwd_vol_24 | +210.2 bp | +206.0 bp | 0.287 |

### Vol regression with trailing-vol control (all bars, day-clustered SEs)
- full (n=35824, events=1409): vol_1h: event b=+3.01bp (p=0.019); vol_4h: event b=+5.10bp (p=0.008); vol_24h: event b=-0.57bp (p=0.866)
- 2025+ (n=11946, events=658): vol_1h: event b=+3.36bp (p=0.042); vol_4h: event b=+6.30bp (p=0.015); vol_24h: event b=+3.10bp (p=0.458)

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.016, n=1411; significant terms: topic_china (b=-8.7bp, p=0.021), topic_market_directive (b=+79.4bp, p=0.002)
- fwd_ret_4h: R2=0.012, n=1411; significant terms: topic_market_directive (b=+162.0bp, p=0.000)
- fwd_ret_24h: R2=0.012, n=1410; significant terms: topic_market_directive (b=+436.0bp, p=0.002)

## ETHUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +0.6 bp | -0.2 bp | 0.673 |
| fwd_ret_4 | -2.0 bp | -0.1 bp | 0.646 |
| fwd_ret_24 | -10.3 bp | -2.6 bp | 0.398 |
| fwd_vol_1 | +50.8 bp | +47.4 bp | 0.022 ** |
| fwd_vol_4 | +119.7 bp | +113.1 bp | 0.007 ** |
| fwd_vol_24 | +306.8 bp | +305.0 bp | 0.656 |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +3.4 bp | +0.1 bp | 0.180 |
| fwd_ret_4 | +3.4 bp | +1.0 bp | 0.615 |
| fwd_ret_24 | +0.8 bp | +2.0 bp | 0.877 |
| fwd_vol_1 | +46.3 bp | +42.9 bp | 0.094 |
| fwd_vol_4 | +107.9 bp | +102.8 bp | 0.103 |
| fwd_vol_24 | +283.3 bp | +283.8 bp | 0.952 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -2.7 bp | -0.9 bp | 0.554 |
| fwd_ret_4 | -8.1 bp | -2.0 bp | 0.340 |
| fwd_ret_24 | -22.9 bp | -12.0 bp | 0.439 |
| fwd_vol_1 | +56.0 bp | +52.4 bp | 0.126 |
| fwd_vol_4 | +133.1 bp | +124.6 bp | 0.028 ** |
| fwd_vol_24 | +333.8 bp | +327.8 bp | 0.338 |

### Vol regression with trailing-vol control (all bars, day-clustered SEs)
- full (n=35824, events=1409): vol_1h: event b=+3.34bp (p=0.047); vol_4h: event b=+6.11bp (p=0.019); vol_24h: event b=+0.33bp (p=0.940)
- 2025+ (n=11946, events=658): vol_1h: event b=+3.34bp (p=0.203); vol_4h: event b=+8.21bp (p=0.051); vol_24h: event b=+4.15bp (p=0.512)

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.017, n=1411; significant terms: topic_china (b=-12.1bp, p=0.017), topic_market_directive (b=+113.1bp, p=0.001)
- fwd_ret_4h: R2=0.014, n=1411; significant terms: sentiment (b=-13.9bp, p=0.030), topic_market_directive (b=+217.1bp, p=0.000)
- fwd_ret_24h: R2=0.011, n=1410; no significant terms

## SOLUSDT  (35873 hourly bars 2022-04-30 -> 2026-06-02)
bursts joined to bars: 1411 / 1411

### full  (n=1410 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -1.5 bp | -0.4 bp | 0.680 |
| fwd_ret_4 | -4.4 bp | -0.2 bp | 0.430 |
| fwd_ret_24 | -13.1 bp | -1.4 bp | 0.384 |
| fwd_vol_1 | +69.0 bp | +68.1 bp | 0.650 |
| fwd_vol_4 | +165.4 bp | +161.3 bp | 0.198 |
| fwd_vol_24 | +425.0 bp | +430.7 bp | 0.324 |

### pre-2025 (out of office)  (n=752 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | +3.4 bp | +0.1 bp | 0.423 |
| fwd_ret_4 | -1.8 bp | +1.4 bp | 0.681 |
| fwd_ret_24 | +7.1 bp | +7.5 bp | 0.978 |
| fwd_vol_1 | +72.0 bp | +72.1 bp | 0.978 |
| fwd_vol_4 | +175.8 bp | +171.4 bp | 0.319 |
| fwd_vol_24 | +460.6 bp | +461.5 bp | 0.917 |

### 2025+ (in office)  (n=658 bursts)
| stat | event mean | null mean | p (2-sided) |
|---|---|---|---|
| fwd_ret_1 | -7.2 bp | -1.3 bp | 0.099 |
| fwd_ret_4 | -7.3 bp | -3.2 bp | 0.572 |
| fwd_ret_24 | -36.1 bp | -23.3 bp | 0.400 |
| fwd_vol_1 | +65.6 bp | +61.7 bp | 0.115 |
| fwd_vol_4 | +153.5 bp | +144.6 bp | 0.023 ** |
| fwd_vol_24 | +384.2 bp | +376.0 bp | 0.189 |

### Vol regression with trailing-vol control (all bars, day-clustered SEs)
- full (n=35824, events=1409): vol_1h: event b=+0.65bp (p=0.771); vol_4h: event b=+3.25bp (p=0.297); vol_24h: event b=-7.95bp (p=0.150)
- 2025+ (n=11946, events=658): vol_1h: event b=+3.82bp (p=0.175); vol_4h: event b=+8.53bp (p=0.033); vol_24h: event b=+5.77bp (p=0.395)

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
