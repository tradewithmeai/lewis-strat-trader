# Darren report — daily round-up + carry hardening check (2026-07-16)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running.
- `signals-monitor.service`: **ok**, last run **04:15 UTC** (exited 0/SUCCESS); next timer fire **08:15 UTC**.
- `lake-snapshot.service`: **ok**, last run **04:54 UTC** (exited 0/SUCCESS); next timer fire **04:00 UTC** tomorrow.
- `stratbot-dashboard.service`: **healthy**, dashboard HTTP **200 OK** on `127.0.0.1:8501`.
- `cryptolake` API HTTP: **200 OK** on `127.0.0.1:8000`.
- Disk: **35% used** (`/` 33G / 96G, 63G free).
- Memory: **3.1 GiB available**; swap **2.4 GiB free**.
- Outage: **none**.
- Live paper board: `xsec_momentum` remains active and red at **-2.68%**, **13 assets / 15 trades**. Watch, don’t promote.

## 2) Research thread worked
**Thread:** harden the cash-and-carry model so it is closer to forward-checkable, not a perfect-hedge artefact.

**Fixed method used**
- Engine: `local_system.portfolio_backtester.cash_and_carry_backtest`
- Universe: **12 USDT perps** (`ADA, AVAX, BNB, BTC, DOGE, DOT, ETH, LINK, LTC, SOL, SUI, XRP`)
- History: deep Binance funding backfill, common overlap now **2023-05-03 00:00 UTC → 2026-07-16 00:00 UTC**
- Signal: **7d rolling mean funding sign**, shifted one step
- Costs: **5 bp / leg**
- Realism stress: haircut funding income only, costs unchanged
- Sanity checks: `event_db.load_event_table()` and `tradfi_data.load_yf()` on `GC=F` / `^GSPC`
- Search size: **5 haircut settings** (`1.00, 0.75, 0.50, 0.35, 0.25`)

## 3) Result
**Raw perfect-hedge ceiling:**
- Sharpe **8.22** (95% CI **6.22, 10.28**)
- Ann. return **+5.09%**
- Ann. vol **0.62%**
- Max DD **-1.63%**
- Per-year Sharpe: **2023 +12.45**, **2024 +15.52**, **2025 +3.26**, **2026 -6.37**

**Realism stress (50% income haircut):**
- Sharpe **2.89** (95% CI **0.31, 5.41**)
- Ann. return **+1.14%**
- Ann. vol **0.40%**
- Max DD **-3.32%**
- Per-year Sharpe: **2023 +6.39**, **2024 +12.59**, **2025 -3.72**, **2026 -11.57**

**Hard stress (25% income haircut):**
- Sharpe **-2.73** (95% CI **-5.07, -0.31**)
- Ann. return **-0.83%**
- Ann. vol **0.30%**
- Max DD **-4.61%**
- Per-year Sharpe: **2023 -0.17**, **2024 +7.61**, **2025 -8.12**, **2026 -14.18**

## 4) Gate verdict
**Not a challenger.**

The funding stream is real, but the headline Sharpe is still a perfect-hedge ceiling. Once haircut toward live carry frictions, the edge decays fast and the per-year sign pattern still fails in 2026. It remains a documented carry ceiling, not a forward-checkable sleeve.

## 5) Next step
Build an explicit basis / borrow / slippage model if we want a truly forward-checkable cash-and-carry sleeve. Otherwise keep watching the live `xsec_momentum` board and move on to the two-sleeve `xsec_momentum` + diversified-beta combo.
