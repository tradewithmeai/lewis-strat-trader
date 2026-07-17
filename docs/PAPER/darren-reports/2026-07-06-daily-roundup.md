# Darren report — daily round-up + carry hardening check (2026-07-06)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (oneshot exited 0/SUCCESS).
- `lake-snapshot.service`: **ok**, last run **04:03 UTC** (oneshot exited 0/SUCCESS).
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **33% used** (`/` 32G / 96G, 65G free).
- Memory: **4.0 GiB available**; swap **2.8 GiB free**.
- Outage: **none**.
- Live paper board: still forward-testing; `xsec_momentum` remains active and the board is mostly orange/red. Watch, don’t promote.

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Portfolio engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- TradFi loader sanity: `local_system.tradfi_data.load_yf()` on `GC=F` and `^GSPC`
- Event DB sanity: `local_system.signals.news.event_db.load_event_table()`
- Universe: 12 USDT perp funding series (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: 2023-01-01 → 2026-07-06
- Signal: 7d rolling mean funding sign, shifted one step
- Costs: 10 bp / leg
- Search size: 5 haircut settings

## 3) Result
**Funding-carry ceiling (perfect hedge / gross view):**
- Sharpe **3.36** (95% CI **0.96, 5.75**)
- Ann. return **+2.58%**
- Ann. vol **0.77%**
- Max DD **-6.53%**
- Per-year Sharpe: **2023 +7.73**, **2024 +12.59**, **2025 -3.72**, **2026 -12.38**

**Haircut stress:**
- 0.75 haircut: Sharpe **0.86** (CI **-1.57, 3.34**)
- 0.50 haircut: Sharpe **-2.40** (CI **-4.62, 0.03**)
- 0.35 haircut: Sharpe **-4.75** (CI **-6.76, -2.60**)
- 0.25 haircut: Sharpe **-6.48** (CI **-8.24, -4.60**)

## 4) Gate verdict
**Not a challenger.**

The raw funding stream is real, but the headline Sharpe is still a perfect-hedge upper bound. Once haircut toward live carry frictions, the edge dies and the year-by-year sign check fails hard.

## 5) Next step
Keep cash-and-carry documented as a ceiling only. If revisited, it needs an explicit basis / borrow / slippage model and a forward-checkable implementation. The better live watch item remains the market-neutral crypto `xsec_momentum` sleeve already on the paper board.
