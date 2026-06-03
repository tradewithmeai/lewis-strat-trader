# Trump Truth Social event study

Pinned archive events: see state/signals/trump_archive.meta.json
Market-relevant non-noise bursts: 1408 (2022-04-30 -> 2026-06-02)
Horizons: [1, 4, 24]h; null draws: 2000; split at 2025-01-20 (inauguration)

## BTCUSDT  (35880 hourly bars 2022-04-30 -> 2026-06-03)
bursts joined to bars: 1408 / 1408

### full  (n=1407 bursts across 841 days)
_event trail_vol_24: mean=223bp p90=364bp | pool: mean=225bp p90=378bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | -0.7 bp | +0.2 bp | 0.579 | 0.561 |
| fwd_ret_4 | +0.9 bp | +0.8 bp | 0.988 | 0.943 |
| fwd_ret_24 | +7.5 bp | +4.3 bp | 0.621 | 0.736 |
| fwd_vol_1 | +37.8 bp | +35.0 bp | 0.018 | 0.001 ** |
| fwd_vol_4 | +87.6 bp | +82.8 bp | 0.010 | 0.005 ** |
| fwd_vol_24 | +223.0 bp | +224.0 bp | 0.753 | 0.672 |

### pre-2025 (out of office)  (n=749 bursts across 488 days)
_event trail_vol_24: mean=231bp p90=378bp | pool: mean=236bp p90=400bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | +1.9 bp | +0.5 bp | 0.527 | 0.505 |
| fwd_ret_4 | +5.4 bp | +2.2 bp | 0.436 | 0.408 |
| fwd_ret_24 | +26.5 bp | +10.5 bp | 0.110 | 0.210 |
| fwd_vol_1 | +38.7 bp | +35.4 bp | 0.053 | 0.020 * |
| fwd_vol_4 | +90.2 bp | +84.2 bp | 0.016 | 0.058 |
| fwd_vol_24 | +234.3 bp | +231.8 bp | 0.597 | 0.896 |

### 2025+ (in office)  (n=658 bursts across 353 days)
_event trail_vol_24: mean=214bp p90=343bp | pool: mean=204bp p90=335bp_
| stat | event mean | null mean | p (vol-matched iid) | p (day-block) |
|---|---|---|---|---|
| fwd_ret_1 | -3.6 bp | -0.6 bp | 0.145 | 0.077 |
| fwd_ret_4 | -4.3 bp | -1.0 bp | 0.431 | 0.418 |
| fwd_ret_24 | -14.2 bp | -6.7 bp | 0.399 | 0.564 |
| fwd_vol_1 | +36.7 bp | +33.6 bp | 0.043 | 0.000 ** |
| fwd_vol_4 | +84.7 bp | +78.4 bp | 0.005 | 0.000 ** |
| fwd_vol_24 | +210.2 bp | +206.1 bp | 0.321 | 0.261 |

### Vol regression with trailing-vol control (all bars, day-clustered SEs)
- full (n=35831, events=1406): vol_1h: event b=+3.06bp (p=0.018); vol_4h: event b=+5.18bp (p=0.007); vol_24h: event b=-0.89bp (p=0.795)
- 2025+ (n=11953, events=658): vol_1h: event b=+3.37bp (p=0.041); vol_4h: event b=+6.33bp (p=0.015); vol_24h: event b=+3.24bp (p=0.438)

### Regressions (day-clustered SEs)
- fwd_ret_1h: R2=0.016, n=1408; significant terms: topic_china (b=-8.7bp, p=0.022), topic_market_directive (b=+79.4bp, p=0.002)
- fwd_ret_4h: R2=0.012, n=1408; significant terms: topic_market_directive (b=+162.0bp, p=0.000)
- fwd_ret_24h: R2=0.011, n=1407; significant terms: topic_market_directive (b=+437.0bp, p=0.002)

## Macro daily panel  (2024-12-13 -> 2026-06-02, cols: ['BTC', 'ETH', 'SOL', 'DXY', 'GOLD', 'SPX', 'NDX', 'US10Y', 'VIX'])

| asset | next-day ret on event days vs not (bp) | sentiment beta (bp, p) |
|---|---|---|
| BTC | -7.5 | -30.5 (p=0.200) |
| ETH | -12.5 | -57.4 (p=0.105) |
| SOL | -14.7 | -66.9 (p=0.099) |
| DXY | -4.0 | +2.2 (p=0.439) |
| GOLD | -13.3 | -21.4 (p=0.124) |
| SPX | +1.7 | -4.3 (p=0.566) |
| NDX | -0.1 | -5.5 (p=0.576) |
| US10Y | +0.2 | +5.0 (p=0.555) |
| VIX | -104.3 | +2.6 (p=0.966) |
