# Platform plan & verified system map

Authoritative "where we are / where we're going" doc, written 2026-06-12 after a
full code-grounded review. Companion to `VPS_MIGRATION_PLAN.md` (infra) and the
`docs/PAPER/` tier docs (academic).

---

## 1. What we have actually built (verified against code)

The project is **two largely separate tracks** that share data plumbing but not
logic:

### Track A — the strategy lab (pure price-based)
- **Data:** the crypto price lake (`crypto-lake-rs`) — 13 Binance symbols (1-second
  live + 1-minute backfill), plus Coinbase (3) and Kraken (3) at 1-minute.
- **Strategies:** **11 registered** in `strategies/registry.py` — markov_regime,
  rsi_meanrev, ema_crossover, mtf_confluence, breakout, daily_swing, mtf_ls,
  bollinger, mtf_bb_vol, regime_bb, and an **ensemble** (votes across the others).
  **All are simple technical-analysis strategies** (RSI/EMA/Bollinger/MACD/ADX);
  none consume macro/news/Trump signals. *Advanced/signal-driven strategies do not
  exist yet — that's future work.*
- **Engine:** `backtester.py` (fees 0.1%×2 + 2bp slippage×2 = 0.24% round-trip),
  `cli/optimize.py` (grid search), `cli/walkforward.py`, `cli/reflect.py`,
  `paper_trader.py`, `scoring.py`.
- **Promotion (traffic light):** a challenger must beat the active strategy for
  **7 days → ORANGE**, then hold **14 days at ORANGE → GREEN** (promote). State in
  `state/comparison.json`; rendered by the dashboard's Traffic Light tab.
- **Verdict so far:** no simple strategy has passed robustness validation
  (bollinger & regime_bb both failed). This is an honest, documented null result.

### Track B — the research / signal suite (the dissertation)
- **Signals (`local_system/signals/`):** futures/derivatives (Binance funding,
  open-interest, long/short ratios — **hourly**), macro (DXY/SPX/NDX/Gold/VIX/US10Y
  via yfinance — **daily**), news (5 crypto RSS feeds), Trump posts (CNN archive
  ~33k + live `trumpstruth.org` RSS).
- **Output:** the **event study** — *does a head of state's social-media posting
  move intraday crypto **volatility**?* Result: a robust **1–4h volatility effect**
  (RQ1), null on direction (RQ2/RQ3). This is the undergrad paper; master's
  (AI-augmentation) and PhD tiers build on it.
- **Connection to Track A:** thin — `paper_trader` fires a `trump_alert`
  (notification only); `backtester.py` has a commented *intention* for Trump-vol
  risk overlays that is **not** wired into strategy logic. The signals are **not**
  inputs to the trading strategies today.

---

## 2. What is actually LIVE (VPS, as of 2026-06-12)

**Running on the box (`stratbot` / 185.44.253.199):**
- `cryptolake.service` — collector (3 exchanges) + its dashboard/API on :8000
- `deep-backfill.service` — rebuilding 1m history from Binance (in progress)
- `stratbot-dashboard.service` — Streamlit, public at **https://stratbot.solvx.uk**
- crypto-lake dashboard behind auth at **https://lake.solvx.uk**
- ufw locked to 22/80/443

**NOT yet on the VPS (this is the gap to close):**
- `paper_trader` / `cli.reflect` — **not running**; no crontab; **no
  `comparison.json`** (only `challengers.yaml` + `strategy.yaml` configs). So the
  **live strategy comparison / traffic light is not executing on the box yet** —
  the dashboard shows the framework, but nothing is driving it.
- Signal capture (macro/news/futures/Trump) — not scheduled on the VPS.
- Hermes collector job spec — installed by user, not yet wired.

**Local (desktop):** full ~79-day 1-second history, prior run outputs. **Not
retired** — still the source of truth for sec/sec data until Phase-2 migration.

---

## 3. Roadmap

### Phase 1 — TODAY: live strategy comparison + traffic light on the VPS
Goal: the **simplest working version** of the live comparison running on the box
with the existing simple strategies.
- Bring the strategy state to the VPS (`challengers.yaml`/`strategy.yaml` present).
- Schedule `cli.reflect` (systemd timer or cron) to run walk-forward on the lake,
  score challengers vs active, and write `state/comparison.json`.
- (Optional for v1) run `paper_trader` for the live tick loop.
- Confirm the dashboard Traffic Light tab renders the live comparison.
- Needs BTC/ETH history (already present); other symbols fill as backfill completes.

### Phase 2 — Hermes collector
Wire the Nous Hermes agent (already installed) to: hourly Truth Social pull +
flag; daily policy/business headline scan; append event-time-stamped to the store.

### Phase 3 — improve the strategies
Move beyond simple TA: signal-driven strategies (wire the Track-B signals as
inputs / the Trump-vol risk-overlay hook), and/or ML. This is where the two tracks
could finally connect.

### Phase 4 — public strategy-testing platform (the vision)
Let users submit strategies and run them publicly on the live comparison.
- **⚠️ Security (non-negotiable):** user-submitted strategies are **untrusted code**
  and MUST be sandboxed (isolated process / container, resource + network limits,
  no lake-wide or shell access). Flagged in `SIGNALS.md` / `VPS_SETUP.md §8`. This
  is the central engineering problem of the public platform — design before build.

### Ongoing — Phase-2 lake migration
Migrate the second-resolution history to the VPS (consolidate-then-ship; rewrites
the local lake — confirm first), set up rclone→gdrive backup, then retire local.

---

## 4. Immediate next action
Wait for the deep-backfill to finish, then execute **Phase 1**. Hermes and advanced
strategies explicitly come *after* the simple live comparison is working.
