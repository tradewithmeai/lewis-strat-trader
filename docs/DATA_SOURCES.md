# Signal data-source catalogue

Concrete sources for the signal capture suite (`local_system/signals/`), with
endpoints, auth, and caveats. Legend for **Status**:

- ✅ **verified-tonight** — built and run live in this project (2026-06-02), works.
- 🔬 **researched** — sourced from research, not yet wired here.
- 🔑 **needs-key** — free but requires registration.

> Assembled from first-hand implementation (futures, news, Trump RSS, macro panel)
> plus source research (macro series, Trump-source fallback chain). See `SIGNALS.md`
> for how the suite runs.

---

## 1. Futures / derivatives

Binance USDⓈ-M futures public REST — **no key**. Host `https://fapi.binance.com`.

| Source | Endpoint | Auth | Status | Caveat |
|---|---|---|---|---|
| Funding rate history | `/fapi/v1/fundingRate?symbol=&limit=1000` | none | ✅ | 8-hourly; deep history |
| Open-interest history | `/futures/data/openInterestHist?symbol=&period=1h&limit=500` | none | ✅ | **capped ~20–30d** (500 pts) |
| Retail long/short ratio | `/futures/data/globalLongShortAccountRatio?symbol=&period=1h&limit=500` | none | ✅ | capped ~30d |
| Top-trader L/S ratio | `/futures/data/topLongShortPositionRatio?symbol=&period=1h&limit=500` | none | ✅ | capped ~30d; smart-money proxy |
| Live snapshot (mark/funding/OI) | `/fapi/v1/premiumIndex`, `/fapi/v1/openInterest` | none | ✅ | point-in-time; accrue for >30d history |

**Access:** `requests.get(...)` (see `signals/futures.py`). All timestamps epoch-ms UTC.

**Extra venues (🔬 not yet wired):** Bybit v5 (`/v5/market/...` funding/OI), OKX
(`/api/v5/public/funding-rate`, open-interest), Hyperliquid (info endpoint, funding
+ OI for perps), Deribit (options-implied). **Liquidations:** Binance has no clean
historical liquidations API; **Coinglass** (🔑 needs-key) is the practical source.
**Basis / term structure:** derive from perp mark vs quarterly futures price.

---

## 2. Macro + cross-asset

Three-tier stack (from research). **Correlate on returns, ffill macro across
crypto weekends, never bfill.**

### Tier 1 — FRED REST (🔑 free key, no scraping; the robust VPS source)
`https://api.stlouisfed.org/fred/series/observations?series_id=&api_key=&file_type=json`
| Series | ID | Why |
|---|---|---|
| US 10y nominal | `DGS10` | risk-free anchor |
| **US 10y real (TIPS)** | `DFII10` | **highest-value; only free source.** Falling real yields → BTC/gold bid |
| 10y breakeven inflation | `T10YIE` | = DGS10 − DFII10 |
| VIX | `VIXCLS` | equity fear |
| S&P 500 | `SP500` | risk-on (FRED covers ~10y only) |

`fredapi`: `Fred(api_key=...).get_series('DFII10')`. 120 req/min. Business-day lag ~1–3d.

### Tier 2 — yfinance (no key, but flaky on datacenter IPs; ✅ panel built tonight)
Exact tickers (verified): `DX-Y.NYB` (DXY — **not** "DXY"), `^IXIC` (Nasdaq),
`GC=F` (Gold), `^VIX`, `^TNX` (10y, already in %), `^GSPC` (S&P), `^MOVE` (bond vol —
intermittently empty, best-effort, no free fallback). **Wrap every call in
try/except + cache last-good; pull daily not intraday** (429s on VPS IPs).

### Tier 3 — crypto-native (🔬 not yet wired)
- **Total stablecoin supply** (dry powder): DefiLlama, **no key** —
  `GET https://stablecoins.llama.fi/stablecoincharts/all?stablecoin=1` →
  `[-1].totalCirculatingUSD.peggedUSD`. (Note host is `stablecoins.llama.fi`.)
- **BTC dominance**: CoinGecko (🔑 free Demo key, `x-cg-demo-api-key` header) —
  `GET /api/v3/global` → `data.market_cap_percentage.btc`. Keyless is throttled/403s on VPS.

Currently built (`signals/macro.py`): DXY, SPX, NDX, Gold, VIX, US10Y + BTC/ETH/SOL via yfinance.

---

## 3. News (crypto + financial)

| Source | Endpoint | Auth | Status |
|---|---|---|---|
| Cointelegraph | `https://cointelegraph.com/rss` | none | ✅ verified |
| CoinDesk | `https://www.coindesk.com/arc/outboundfeeds/rss/` | none | ✅ (redirects) |
| Decrypt | `https://decrypt.co/feed` | none | ✅ wired |
| Bitcoin Magazine | `https://bitcoinmagazine.com/feed` | none | ✅ wired |
| CryptoSlate | `https://cryptoslate.com/feed/` | none | ✅ wired |
| **CryptoPanic** | `https://cryptopanic.com/api/v1/posts/?auth_token=` | 🔑 free key | 🔬 — adds votes/sentiment fields |
| **GDELT DOC 2.0** | `https://api.gdeltproject.org/api/v2/doc/doc?query=bitcoin&format=json` | none | 🔬 — broad global news, no key |

**Access:** `feedparser.parse(url)` (see `signals/news/rss.py`). Extract publish
time as event timestamp.

---

## 4. Trump social posts

**Truth Social is primary** (he posts there almost exclusively; X free tier was
discontinued Feb 2026 — skip). No official API, but reachable. Build a **fallback
chain**, not one source:

| Rank | Source | Endpoint | Auth | Status |
|---|---|---|---|---|
| 1 | **trumpstruth.org RSS** | `https://trumpstruth.org/feed` | none | ✅ **verified tonight** (30 posts) — ToS-clean, VPS-safe |
| 2 | Truth Social public JSON | account statuses read endpoints | none (reads) | 🔬 lower-latency upgrade |
| 3 | truthbrush (Python) | `pull_statuses` | none for reads; creds for search | 🔬 breaks often, Cloudflare; don't use personal account |
| 4 | CNN-hosted archive (stiles/trump-truth) | static dataset | none | 🔬 backfill/history |
| ✗ | X/Twitter API | — | paid | skip (free tier gone) |

**Wired:** `signals/news/trump.py` uses #1 (override via `TRUMP_FEED_URL`). If it
breaks, the env var lets you point at #2/#3 without code change.

---

## Auth summary (what runs key-free on a VPS today)

**No key, working now:** Binance futures, yfinance macro, all crypto RSS, Trump
RSS. → the whole current suite runs unattended with zero credentials.

**Free key recommended for robustness/extras:** FRED (real yields — high value),
CoinGecko Demo (BTC dominance), CryptoPanic (sentiment).

## ⚠️ Reliability notes for unattended VPS runs
- **yfinance** is the biggest operational risk (scrapes Yahoo's unofficial
  endpoints, 429s datacenter IPs). Pull daily, retry+backoff, cache last-good;
  route load-bearing series to FRED.
- **CoinGecko/DefiLlama** keyless limits are low and 403 datacenter IPs — get the
  free CoinGecko Demo key.
- **Correlation correctness:** returns not levels; ffill macro, never bfill (bfill
  = lookahead bias).
