# Darren report — daily round-up + carry hardening check (2026-07-03)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (oneshot exited 0/SUCCESS).
- `lake-snapshot.service`: **failed** at **04:01 UTC**.
- `stratbot-dashboard.service`: **healthy**, active/running on `127.0.0.1:8501`.
- Dashboard HTTP: **200 OK**.
- Disk: **33% used** (`/` 31G / 96G, 66G free).
- Memory: **4.1 GiB available**; swap **3.0 GiB free**.
- Outage: **lake-snapshot upload failed** because rclone could not refresh the Google Drive token (`access_not_configured` / account restricted). The tarball was kept locally for retry.
- Live paper board: still forward-testing; `xsec_momentum` remains active and the board is mostly orange (watch, don’t promote).

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Portfolio engine: `local_system/portfolio_backtester.cash_and_carry_backtest`
- TradFi loader sanity: `local_system.tradfi_data.load_yf()` on `GC=F` and `^GSPC`
- Event DB sanity: `local_system.signals.news.event_db.load_event_table()`
- Full-history carry grid already on disk: `state/carry_hardened_grid.json`
- Universe: 12 USDT perp funding series
- History: 2023-01-01 → 2026-06-30
- Signal: 7d rolling mean funding sign, shifted one step
- Costs: 10 bp / leg
- Search size: 5 haircut settings

**Sanity checks**
- Event DB loaded cleanly: **35,350 rows**, **34,878** with 4h market reaction.
- TradFi loader fetched cleanly: `GC=F` (**630 rows**) and `^GSPC` (**627 rows**) both returned daily bars.

## 3) Result
**Funding-carry ceiling (perfect hedge / gross view):**
- Sharpe **3.44** (95% CI **1.22, 5.98**)
- Ann. return **+2.63%**
- Ann. vol **0.76%**
- Max DD **-6.38%**
- Per-year Sharpe: **2023 +7.73**, **2024 +12.59**, **2025 -3.72**, **2026 -12.83**

**Haircut stress:**
- 0.75 haircut: Sharpe **0.93** (CI **-1.32, 3.56**)
- 0.50 haircut: Sharpe **-2.34** (CI **-4.43, 0.21**)

## 4) Gate verdict
**Not a challenger.**

The funding stream is real, but the headline Sharpe is still a perfect-hedge upper bound. Once haircut toward live carry frictions, the edge fades and the year-by-year sign check fails hard.

## 5) Next step
Keep cash-and-carry documented as a ceiling only. If revisited, it needs an explicit basis / borrow / slippage model and a forward-checkable implementation. The better live watch item remains the market-neutral crypto `xsec_momentum` sleeve already on the paper board.
