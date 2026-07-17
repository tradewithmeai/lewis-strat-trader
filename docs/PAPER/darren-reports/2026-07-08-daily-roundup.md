# Darren report — daily round-up + carry hardening check (2026-07-08)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (oneshot exited 0/SUCCESS).
- `lake-snapshot.timer`: **ok**, active/waiting; next fire **2026-07-09 04:00 UTC**.
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **34% used** (`/` 32G / 96G, 65G free).
- Memory: **4.0 GiB available**; swap **2.8 GiB free**.
- Outage: **none**.
- Live paper board: `xsec_momentum` remains active, now down **-5.18%** with **13 assets / 14 trades** and still mostly orange. Watch, don’t promote.

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio / cross-sectional track.

**Fixed method used**
- Engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- Universe: **12 USDT perps** (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: **2019-09-10 → 2026-07-07** full funding history backfill
- Signal: **7d rolling mean funding sign**, shifted one step
- Costs: **10 bp / leg**
- Realism stress: **25% realization haircut** on the perfect-hedge ceiling
- Sanity checks: `event_db.load_event_table()` and `tradfi_data.load_yf()` on `GC=F` / `^GSPC`
- Search size: **5 haircut settings** (`1.00, 0.75, 0.50, 0.35, 0.25`)

## 3) Result
**Raw perfect-hedge ceiling:**
- Sharpe **8.63** (95% CI **7.71, 9.78**)
- Ann. return **+12.27%**
- Ann. vol **1.42%**
- Max DD **-1.63%**
- Per-year Sharpe: **2019 +10.77**, **2020 +14.80**, **2021 +14.37**, **2022 +6.85**, **2023 +15.17**, **2024 +15.52**, **2025 +3.26**, **2026 -7.05**

**Conservative realism stress (25% haircut):**
- Sharpe **3.31** (95% CI **1.69, 4.76**)
- Ann. return **+1.42%**
- Ann. vol **0.43%**
- Max DD **-4.61%**
- Per-year Sharpe: **2019 +8.03**, **2020 +10.64**, **2021 +11.93**, **2022 -4.84**, **2023 +1.63**, **2024 +7.61**, **2025 -8.12**, **2026 -14.81**

## 4) Gate verdict
**Not a challenger.**

The raw Sharpe is still a perfect-hedge ceiling, and the realism-stressed view breaks sign-consistency hard from 2022 onward. This stays documented as a carry ceiling, not a deployable or forward-checkable edge.

## 5) Next step
Keep carry as a ceiling only. If revisited, add explicit basis / borrow / slippage and forward-check it. Otherwise move to the next honest candidate: the two-sleeve `xsec_momentum` + diversified-beta combo, while watching the live `xsec_momentum` board already on paper.
