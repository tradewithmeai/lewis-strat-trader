# Darren report — daily round-up + carry hardening check (2026-07-10)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.timer`: **ok**, last fire **04:15 UTC**; service exited **0/SUCCESS** and is waiting for the next run.
- `lake-snapshot.timer`: **ok**, last fire **04:00:02 UTC**; service exited **0/SUCCESS** and is waiting for the next run.
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **34% used** (`/` 33G / 96G, 64G free).
- Memory: **1.6 GiB available**; swap **2.3 GiB free**.
- Outage: **none**.
- Live paper board: `xsec_momentum` remains active, **-3.64%**, **13 assets / 14 trades**, still orange. Watch, don’t promote.

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- Universe: **12 USDT perps** (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: deep Binance funding backfill; common overlap now **2023-05-03 → 2026-07-10**
- Signal: **7d rolling mean funding sign**, shifted one step
- Costs: **5 bp / leg**
- Realism stress: haircut funding income only, costs unchanged
- Sanity checks: `event_db.load_event_table()` and `tradfi_data.load_yf()` on `GC=F` / `^GSPC`
- Search size: **5 haircut settings** (`1.00, 0.75, 0.50, 0.35, 0.25`)

## 3) Result
**Raw perfect-hedge ceiling:**
- Sharpe **8.20** (95% CI **6.24, 10.24**)
- Ann. return **+5.10%**
- Ann. vol **0.62%**
- Max DD **-1.63%**
- Per-year Sharpe: **2023 +12.34**, **2024 +15.52**, **2025 +3.26**, **2026 -6.90**

**Realism stress (50% income haircut):**
- Sharpe **2.87** (95% CI **0.28, 5.42**)
- Ann. return **+1.14%**
- Ann. vol **0.40%**
- Max DD **-3.32%**
- Per-year Sharpe: **2023 +6.26**, **2024 +12.59**, **2025 -3.72**, **2026 -12.03**

**Hard stress (25% income haircut):**
- Sharpe **-2.75** (95% CI **-5.29, -0.18**)
- Ann. return **-0.84%**
- Ann. vol **0.31%**
- Max DD **-4.61%**
- Per-year Sharpe: **2023 -0.26**, **2024 +7.61**, **2025 -8.12**, **2026 -14.59**

## 4) Gate verdict
**Not a challenger.**

The funding stream is real, but the headline Sharpe is still a perfect-hedge ceiling. Once haircut toward live carry frictions, the edge decays fast and the per-year sign pattern still fails in 2026. The model is a documented carry ceiling, not a forward-checkable sleeve.

## 5) Next step
Build an explicit basis / borrow / slippage model if we want a truly forward-checkable cash-and-carry sleeve. Otherwise keep watching the live `xsec_momentum` board and move on to the two-sleeve `xsec_momentum` + diversified-beta combo.
