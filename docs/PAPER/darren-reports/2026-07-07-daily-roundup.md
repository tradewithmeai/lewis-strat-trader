# Darren report — daily round-up + carry hardening check (2026-07-07)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (oneshot exited 0/SUCCESS).
- `lake-snapshot.service`: **ok**, last run **04:20 UTC** (oneshot exited 0/SUCCESS).
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **33% used** (`/` 32G / 96G, 65G free).
- Memory: **4.0 GiB available**; swap **2.7 GiB free**.
- Outage: **none**.
- Live paper board: `xsec_momentum` remains active on the live board, still down **-5.37%** and mostly orange. Watch, don’t promote.

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Portfolio engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- Deep funding history: Binance USDT perps for **12 symbols** (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: **2019-09-10 → 2026-07-07**
- Signal: **7d rolling mean funding sign**, shifted one step
- Costs: **10 bp / leg**
- Haircut stress: **5 settings** (`1.00, 0.75, 0.50, 0.35, 0.25`)
- Sanity checks: `event_db.load_event_table()` and `tradfi_data.load_yf()` on `GC=F` / `^GSPC`

## 3) Result
**Raw funding-carry ceiling (perfect hedge / gross view):**
- Sharpe **8.63** (95% CI **7.71, 9.78**)
- Ann. return **+12.27%**
- Ann. vol **1.42%**
- Max DD **-1.63%**
- Per-year Sharpe: **2019 +10.77**, **2020 +14.80**, **2021 +14.37**, **2022 +6.85**, **2023 +15.17**, **2024 +15.52**, **2025 +3.26**, **2026 -7.05**

**Conservative realization stress (25% funding haircut):**
- Sharpe **3.31** (95% CI **1.69, 4.76**)
- Ann. return **+1.42%**
- Ann. vol **0.43%**
- Max DD **-4.61%**
- Per-year Sharpe: **2019 +8.03**, **2020 +10.64**, **2021 +11.93**, **2022 -4.84**, **2023 +1.63**, **2024 +7.61**, **2025 -8.12**, **2026 -14.81**

## 4) Gate verdict
**Not a challenger.**

The raw Sharpe is still a perfect-hedge ceiling, and even the conservative haircut stress fails sign-consistency badly from 2022 onward. The carry model remains a documented ceiling until basis / borrow / slippage are modeled explicitly and forward-checked.

## 5) Next step
Keep cash-and-carry as a ceiling only. If revisited, add explicit basis / borrow / slippage and forward-check it. The live watch item remains the market-neutral crypto `xsec_momentum` sleeve already on the paper board; next challenger thread should be the two-sleeve `xsec_momentum` + diversified-beta combo, not a carry promotion.
