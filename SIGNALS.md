# Signal capture suite

Exogenous signals for the trading agent — data that lives *outside* the OHLCV
price lake and may carry predictive information. Built as `local_system/signals/`
with one collector per domain, all writing to `state/signals/` with **event-time
UTC timestamps** so they can later be joined to price bars without lookahead.

> Status (2026-06-02): futures, macro/correlations, news/social, and the live-data
> rollup are all **built, tested live, and committed**. See `RESEARCH_NOTE.md` for
> the separate strategy-validation work and `docs/DATA_SOURCES.md` for the source
> catalogue.

---

## Subsystems

### 1. Futures / derivatives — `signals/futures.py`
Funding rate, open interest, and long/short positioning (retail + top-trader) for
any USDT-perp, from **Binance USDⓈ-M futures public REST — no key**. Uses the
*historical* endpoints so series backfill rather than only accruing forward.

- `collect_futures(["BTCUSDT","SOLUSDT"])` → per-symbol 1h frame, persisted to
  `state/signals/futures_{symbol}.parquet`; a current snapshot is appended to
  `futures_snapshots.jsonl` for forward accrual beyond the API caps.
- Caps: funding history is deep; OI / L-S history is capped to ~500 points
  (~20 days at 1h). To build longer OI history, accrue the snapshots over time.

### 2. Macro + correlations — `signals/macro.py`, `signals/correlations.py`
Daily panel of crypto (BTC/ETH/SOL) + macro (DXY, SPX, NDX, Gold, VIX, US10Y) via
**yfinance — no key**. Correlations are computed on **returns**, not levels.
Handles the 24/7-crypto vs market-hours-macro calendar mismatch by forward-filling
macro across non-trading days.

- `build_panel()` → aligned daily-close panel → `state/signals/macro_panel.parquet`
- `correlation_report(panel)` → 30d/90d correlation of BTC vs each series

### 3. News + social — `signals/news/`
Pluggable `NewsAdapter`s normalised to a common `NewsEvent` (event-time stamped,
keyword-tagged), deduped into `state/signals/news.jsonl`.

- `rss.py` — crypto/financial RSS via feedparser (**no key**): Cointelegraph,
  CoinDesk, Decrypt, Bitcoin Magazine, CryptoSlate. Bad feeds skipped, never fatal.
- `trump.py` — Donald Trump's Truth Social posts. **Best-effort, graceful
  degradation.** Default source `https://trumpstruth.org/feed` (no key, working as
  of build); override with env `TRUMP_FEED_URL` if it breaks. If the source is
  down it logs "needs config" and returns nothing — never crashes the pass.
- `capture.py` — `run_capture()` runs all adapters, dedups by URL, appends new.

### 4. Live-data rollup — `signals/live_rollup.py`  *(data hardening)*
The lake's live 1-second partitions have **multiple parquet-corruption modes**
(truncated footers *and* corrupt thrift metadata — the latter reported by DuckDB
with no file path) and ~1140 files/day, so a single glob fails unrecoverably and
per-tick full reads are slow. This module reads each live day **once** via a
bisecting DuckDB reader (one query for the whole day; split only to isolate and
skip corrupt files), aggregates to 1h, and caches it under
`state/lake_rollup/`. `load_history_hybrid()` stitches clean backfill (bulk) with
the cached rollups (live tail).

- Result: the monitor now tracks **real time** (was pinned to the last clean
  backfill bar). First build ~5 min one-time; cached loads ~2s.
- Reader-side robustness was also added in `lake_adapter.py` (footer-aware
  validation + quarantine-on-read) for the backfill path.

> The *proper* upstream fix is for the collector to write valid parquet and/or
> backfill recent days into clean form; the rollup is the reader-side workaround.

---

## Running it

```bash
# one capture pass + publishable digest (state/signals/report.md)
LAKE_ROOT=… uv run python -m local_system.cli.signals

# just rebuild the digest from already-captured data
LAKE_ROOT=… uv run python -m local_system.cli.signals --report-only

# individual collectors
LAKE_ROOT=… uv run python -m local_system.signals.futures BTCUSDT SOLUSDT
LAKE_ROOT=… uv run python -m local_system.signals.news.capture
LAKE_ROOT=… uv run python -m local_system.signals.correlations
```

`report.md` is the artifact to publish: latest futures positioning, cross-asset
correlations, recent Trump posts, and tagged market-moving headlines.

---

## Auth summary

| Source | Auth | Notes |
|---|---|---|
| Binance futures | **none** | public market-data endpoints |
| yfinance macro | **none** | |
| Crypto RSS | **none** | feedparser |
| Trump (trumpstruth.org/feed) | **none** | best-effort; override via `TRUMP_FEED_URL` |
| CryptoPanic / GDELT / FRED | free key (optional) | not yet wired — see `docs/DATA_SOURCES.md` |

---

## VPS deployment notes

- Cron `python -m local_system.cli.signals` (e.g. every 15–30 min) to refresh
  `state/signals/report.md`; publish that file to the website.
- The paper-trade monitor (`python -m local_system.paper_trader`) should run as a
  **detached, supervised process** (not a child of any interactive session) so it
  survives restarts. (We deferred building the supervisor — durability is handled
  by committing code; the running process is relaunchable.)
- First run builds the live-rollup cache (~5 min); subsequent runs are fast.

## ⚠️ Security flag — user-submitted strategies

The plan to "publish output and let people submit strategies to run" means
**executing untrusted code** on the VPS. Do **not** wire that up without a
sandbox (separate unprivileged container/VM, no secrets in env, CPU/mem/time
limits, no outbound network, read-only data mount). Running submitted Python in
the same process/host as the trading agent or any keys is an arbitrary-code-
execution hole. Treat this as a hard prerequisite before that feature ships.

## Not yet wired / future work
- Extra futures venues (Bybit/OKX/Hyperliquid) + liquidations — see catalogue.
- CryptoPanic/GDELT sentiment, FRED macro series.
- Joining signals to bars as strategy features (the point of collecting them).
- Forward-accrual store for OI beyond the ~20-day API cap.
