# Darren report — carry hardening + daily round-up (2026-07-01)

Read the charter + strategy log first, then checked systems and hardened the cash-and-carry thread.

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running; recent logs still writing bars, no outage.
- `signals-monitor.service`: **ok**, oneshot completed successfully at 04:15 UTC and is now inactive by design.
- `lake-snapshot.service`: **ok**, oneshot completed successfully at 04:19 UTC and is now inactive by design.
- `stratbot-dashboard.service`: **healthy**, active/running on 127.0.0.1:8501.
- Disk: **28% used** (`/dev/sda1` 27G / 96G).
- Memory: **4.3 GiB available**; swap ~3.1 GiB free.
- Note: dashboard logs still show an old `pyarrow` column-conversion error, but the service is up and serving.

## 2) Research thread worked
Cash-and-carry hardening on the validated portfolio/cross-sectional track.

### Fixed method
- Universe: 12 funding series (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP` USDT perps)
- History: full Binance funding-rate history, 2023-01-01 to 2026-06-30
- Signal: 7d rolling mean funding sign, shifted one step
- Costs: 10 bp per leg
- Search size: 5 haircut settings (`1.00, 0.75, 0.50, 0.35, 0.25`)
- Sanity checks: TradFi loader (`GC=F`, `^GSPC`) and events DB loaded cleanly; no carry edge came from them.

### Result
- **Gross perfect-hedge ceiling**: Sharpe **3.44** (95% CI **1.22, 5.98**), ann ret **+2.63%**, ann vol **0.76%**, max DD **-6.38%**
- **Moderate realism stress (0.75 haircut)**: Sharpe **0.93** (CI **-1.32, 3.56**), ann ret **+0.63%**
- **Conservative realism stress (0.50 haircut)**: Sharpe **-2.34** (CI **-4.43, 0.21**), ann ret **-1.38%**
- Per-year sign pattern on the hardened view: **2023 mildly positive, 2024 positive, 2025 negative, 2026 deeply negative**

## 3) Gate verdict
**Not a challenger.**

The raw funding stream is real, but the headline Sharpe is still a perfect-hedge upper bound. Once haircut toward live carry frictions (borrow, basis, hedge slippage), the edge vanishes and the sign-consistency check fails hard.

## 4) Next step
Keep carry documented as a ceiling only; do **not** promote it. If we want a liveable challenger, the better next thread is the market-neutral xsec momentum sleeve already on the paper board, or a properly basis-aware carry build later.

## Artifacts
- `docs/PAPER/STRATEGY_RESEARCH.md`
- `state/carry_hardened_grid.json`
