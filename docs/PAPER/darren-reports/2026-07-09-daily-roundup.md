# Darren report — daily round-up + carry hardening check (2026-07-09)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (oneshot exited 0/SUCCESS).
- `lake-snapshot.service`: **ok**, last run **04:13 UTC** (oneshot exited 0/SUCCESS).
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **34% used** (`/` 32G / 96G, 64G free).
- Memory: **4.2 GiB available**; swap **2.8 GiB free**.
- Outage: **none**.
- Live paper board: `xsec_momentum` remains active, **-4.83%** with **13 assets / 14 trades** and still mostly orange. Watch, don’t promote.

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- Universe: **12 USDT perps** (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: deep Binance funding backfill; common overlap now **2023-05-03 → 2026-07-09**
- Signal: **7d rolling mean funding sign**, shifted one step
- Costs: **5 bp / leg**
- Realism stress: haircut funding income only, costs unchanged
- Sanity checks: `event_db.load_event_table()` and `tradfi_data.load_yf()` on `GC=F` / `^GSPC`
- Search size: **5 haircut settings** (`1.00, 0.75, 0.50, 0.35, 0.25`)

## 3) Result
**Raw perfect-hedge ceiling:**
- Sharpe **8.21** (95% CI **6.24, 10.14**)
- Ann. return **+5.10%**
- Ann. vol **0.62%**
- Max DD **-1.63%**
- Per-year Sharpe: **2023 +12.45**, **2024 +15.52**, **2025 +3.26**, **2026 -7.02**

**Realism stress (50% income haircut):**
- Sharpe **2.88** (95% CI **0.24, 5.34**)
- Ann. return **+1.14%**
- Ann. vol **0.40%**
- Max DD **-3.32%**
- Per-year Sharpe: **2023 +6.39**, **2024 +12.59**, **2025 -3.72**, **2026 -12.14**

**Hard stress (25% income haircut):**
- Sharpe **-2.74** (95% CI **-5.21, -0.27**)
- Ann. return **-0.84%**
- Ann. vol **0.31%**
- Max DD **-4.61%**
- Per-year Sharpe: **2023 -0.17**, **2024 +7.61**, **2025 -8.12**, **2026 -14.68**

## 4) Gate verdict
**Not a challenger.**

The funding stream is real, but once I haircut only the income side to approximate live carry frictions, the edge decays fast and the per-year sign pattern still fails in 2026. The model is still a documented carry ceiling, not a forward-checkable sleeve.

## 5) Next step
Build an explicit basis / borrow / slippage model if we want a truly forward-checkable cash-and-carry sleeve. Otherwise keep watching the live `xsec_momentum` board and do not promote.
