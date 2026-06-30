# Combined premia book test

Thread: combine the premia, do not mine a fourth standalone strategy.

Fixed methodology: 2023-01-01 to 2026-06-27, daily calendar alignment, no optimisation of sleeve weights, equal-risk sleeves, then portfolio vol-target. Search size = 3 sleeves; no grid search over weights.

Sleeves:
- A: crypto cross-sectional momentum on 13 crypto symbols (ADAUSDT, AVAXUSDT, BNBUSDT, BTCUSDT, DOGEUSDT, DOTUSDT, ETHUSDT, EURUSDT, LINKUSDT, LTCUSDT, SOLUSDT, SUIUSDT, XRPUSDT)
- B: cash-and-carry on 12 funding series after haircut (10 bp/leg, 7d signal lookback)
- C: diversified beta passive basket on 41 TradFi symbols

## Correlation matrix (equal-risk sleeve inputs)
|       |   xsec |   carry |   beta |
|:------|-------:|--------:|-------:|
| xsec  |   1    |    0.02 |  -0.01 |
| carry |   0.02 |    1    |   0.03 |
| beta  |  -0.01 |    0.03 |   1    |

## Sleeve stats after equal-risk scaling to 10% vol
| sleeve | Sharpe (95% CI) | ann return | ann vol | max DD |
|---|---:|---:|---:|---:|
| A xsec momentum | 0.84 (0.05, 1.74) | +17.10% | +20.41% | -11.94% |
| B cash-and-carry | 2.88 (0.46, 5.44) | +6.49% | +2.25% | -17.48% |
| C diversified beta | 1.17 (0.26, 2.24) | +12.80% | +10.92% | -8.05% |

## Combined book
- Combined Sharpe: 1.58 (0.79, 2.75)
- Combined ann return: +22.86%
- Combined ann vol: +14.44%
- Combined max DD: -11.76%
- Best individual sleeve Sharpe: 2.88 (carry)

## Year-by-year Sharpe
A xsec momentum: 2023:+1.11, 2024:+1.45, 2025:+0.64, 2026:-0.26
B cash-and-carry: 2023:+5.02, 2024:+12.59, 2025:-3.72, 2026:-12.57
C diversified beta: 2023:+0.12, 2024:+2.08, 2025:+0.94, 2026:+1.92
combined: 2023:+1.09, 2024:+4.74, 2025:+0.63, 2026:-0.24

## Buy-and-hold / passive benchmarks
- Passive TradFi basket raw Sharpe: 1.23 (0.31, 2.27)
- Passive crypto basket raw Sharpe: 0.41 (-0.56, 1.49)

## Gate check
- Combined beats best sleeve: False
- Combined CI clears zero: True
- Sign-consistency: False

Verdict: honest null — the combined book did not clear the gate.