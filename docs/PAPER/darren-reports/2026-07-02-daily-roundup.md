# Darren report — daily round-up + carry hardening check (2026-07-02)

## 1) Round-up / health
- `cryptolake.service`: **healthy**, active/running; dashboard/API still serving.
- `signals-monitor.service`: **ok**, inactive by design after the 04:15 UTC oneshot.
- `lake-snapshot.service`: **ok**, inactive by design after the 04:00 UTC oneshot.
- `stratbot-dashboard.service`: **healthy**, active/running on `127.0.0.1:8501`.
- Dashboard HTTP: **200 OK** on `:8501`; API HTTP: **200 OK** on `:8000`.
- Disk: **29% used** (`/dev/sda1` 28G / 96G, 69G free).
- Memory: **4.2 GiB available**; swap **2.9 GiB free**.
- Outage: **none observed**.
- Live paper board: still forward-testing; `xsec_momentum` is the active market-neutral challenger and the board remains mostly orange (watch, don’t promote).

## 2) Research thread worked
**Thread:** cash-and-carry hardening on the validated portfolio/cross-sectional track.

**Fixed method used**
- Portfolio engine: `local_system/portfolio_backtester.cash_and_carry_backtest`
- Event DB sanity: `local_system.signals.news.event_db.load_event_table()`
- TradFi loader sanity: `local_system.tradfi_data.load_yf()` on `GC=F` and `^GSPC`
- Full-history carry grid already on disk: `state/carry_hardened_grid.json`
- Universe: 12 USDT perp funding series
- History: 2023-01-01 → 2026-06-30
- Signal: 7d rolling mean funding sign, shifted one step
- Costs: 10 bp / leg
- Search size: 5 haircut settings

**Sanity checks**
- Event DB loaded cleanly: 35,350 rows, 34,878 with 4h reaction.
- TradFi loader fetched cleanly: `GC=F` and `^GSPC` both returned daily bars.
- Live futures parquet spot-check on available local files was too small to matter (BTC/SOL only, 22 daily periods); treat as a sanity probe, not evidence.

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

The raw funding stream is real, but the headline Sharpe is still a perfect-hedge upper bound. Once haircut toward live carry frictions, the edge vanishes and the year-by-year sign check fails hard.

## 5) Next step
Keep cash-and-carry documented as a ceiling only. If we revisit carry, it needs an explicit basis / borrow / slippage model and a forward-checkable implementation; otherwise the better live candidate remains the market-neutral crypto xsec momentum sleeve already on the paper board.
