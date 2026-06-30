# Darren report — combined-premia test (2026-06-30)

Verbatim capture of Darren's (Hermes/VPS) report on the combined-premia thread,
preserved here so it survives the TUI session. Darren's own authoritative
artifacts on the VPS: `docs/PAPER/COMBINED_PREMIA.md`, `state/combined_premia.json`,
and his edits to `docs/PAPER/STRATEGY_RESEARCH.md`.

---

Pulled first, read the updated strategy-research doc, and ran the combined-premia test.

Bottom line: honest null.
Diversification helped versus the passive beta basket, but the combined book did not beat the best sleeve, and the year-by-year sign check failed.

What I tested
- Fixed method, no weight search:
  - 2023-01-01 to 2026-06-27
  - daily calendar alignment
  - 3 sleeves only
  - equal-risk sleeve scaling, then portfolio vol-target
- Sleeve A: crypto cross-sectional momentum
  - 13 crypto symbols
- Sleeve B: cash-and-carry
  - 12 funding series
  - high-cost haircut: 10 bp/leg, 7d signal lookback
- Sleeve C: diversified beta passive basket
  - 41 TradFi symbols

Correlation matrix of the equal-risk sleeve inputs
- xsec / carry: 0.02
- xsec / beta: -0.01
- carry / beta: 0.03

So the low-correlation premise was real.

Combined-book result
- Combined Sharpe: 1.58
- 95% CI: 0.79 to 2.75
- Annual return: +22.86%
- Annual vol: +14.44%
- Max DD: -11.76%

Individual sleeves after equal-risk scaling
- A xsec momentum: Sharpe 0.84, CI 0.05 to 1.74
- B cash-and-carry: Sharpe 2.88, CI 0.46 to 5.44
- C diversified beta: Sharpe 1.17, CI 0.26 to 2.24

Benchmarks
- Passive TradFi basket raw Sharpe: 1.23, CI 0.31 to 2.27
- Passive crypto basket raw Sharpe: 0.41, CI -0.56 to 1.49

Gate check
- Combined CI clears zero: yes
- Combined beats best sleeve: no
- Sign-consistency: no
  - combined Sharpe by year: 2023 +1.09, 2024 +4.74, 2025 +0.63, 2026 -0.24

Interpretation
- Diversification did something real.
- It improved over the passive beta basket.
- But it did not beat the strongest sleeve, which was carry.
- The 2026 flip to negative kills sign-consistency.
- So this is not a deployable combined challenger yet.

Artifacts written
- /home/kc-user/lewis-strat-trader/docs/PAPER/COMBINED_PREMIA.md
- /home/kc-user/lewis-strat-trader/state/combined_premia.json
- Updated /home/kc-user/lewis-strat-trader/docs/PAPER/STRATEGY_RESEARCH.md

Next options Darren proposed:
1. harden carry with a basis-risk-aware model so it can be forward-checkable, or
2. test a two-sleeve combo excluding carry to see whether xsec + beta is the cleaner liveable challenger.
