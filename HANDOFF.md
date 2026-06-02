# Project handoff — lewis-strat-trader

*Written 2026-06-02 to hand off to a fresh Claude Code instance started in this
repo. Earlier work was done from a Claude instance rooted in
`D:\Documents\11Projects\hermes\trading-agent`, but **all of it was committed
here, to `lewis-strat-trader`** — the hermes folder was just where the instance
happened to start and was never actually used. This repo is canonical.*

---

## 0. Resume checklist (run these first)

```powershell
# 1. You are in the right place:
#    D:\Documents\11Projects\lewis-strat-trader   (remote: tradewithmeai/lewis-strat-trader)

# 2. The lake path must be set for any backtest / signal command:
$env:LAKE_ROOT = "D:/Documents/11Projects/crypto-lake-rs/data/parquet"

# 3. See the story so far:
git log --oneline -20

# 4. Read these, in order:
#    HANDOFF.md (this file) -> RESEARCH_NOTE.md -> SIGNALS.md -> docs/DATA_SOURCES.md

# 5. Check live state:
uv run python -m local_system.cli.status      # paper-trade status (/status skill)
```

A background **paper-trade monitor** may still be running from the old instance
(it's a child of that session and will die when it closes). Restart it here:
```
$env:LAKE_ROOT="D:/Documents/11Projects/crypto-lake-rs/data/parquet"
uv run python -m local_system.paper_trader
```

---

## 1. Repo geography (important)

- **`lewis-strat-trader`** (this repo, `github.com/tradewithmeai/lewis-strat-trader`)
  — canonical. All strategy research + the signal suite live here.
- **`hermes/trading-agent`** (`github.com/tradewithmeai/hermes-trading-agent`) — a
  **separate** repo with a `hermes_trading/` package + Dockerfile, likely the
  intended Railway/production deploy target. **None of this work is there.** Before
  any VPS/production deploy, decide: deploy lewis-strat-trader directly, or port the
  signal suite into hermes-trading-agent. (Open question — see §9.)

---

## 2. What this project is

A self-improving paper-trading research agent for crypto (BTC focus), inspired by
a "self-improving AI trading agent" YouTube build. Pipeline:

- **reflect** (`local_system.cli.reflect`) — walk-forward backtest of the active
  strategy + all challengers; updates `state/comparison.json` traffic light. **This
  is the promotion decision engine.**
- **paper_trader** (`local_system.paper_trader`) — live monitor; runs the active
  strategy (by name from `state/strategy.yaml`) + challengers (`state/challengers.yaml`)
  via the registry, writes `state/status.json`. Observational.
- **Traffic-light promotion** — challenger must beat active for 7 reflect cycles →
  ORANGE, then **14 real calendar days** at ORANGE → GREEN (un-fakeable; a "switch"
  is always ≥2 weeks out). Claude only alerts; the human edits `state/strategy.yaml`.
- **Costs baked into every backtest:** 0.1% taker ×2 + 2bps slippage ×2 ≈ 0.24%
  round trip. This kills most gross-profitable strategies.

Data lives in the `crypto-lake-rs` parquet store (DuckDB, hive-partitioned),
read via `local_system/lake_adapter.py`.

---

## 3. Current state

- **Active strategy:** `breakout` (entry 40 / exit 20 / stop 8%) per `state/strategy.yaml`.
- **Challengers:** all 9 others, incl. `regime_bb`, in `state/challengers.yaml`.
- **Monitor:** real-time (the live-data fix below got it off the stale Apr-29 pin).
- **No challenger is promotable** — see §5. Do **not** switch the active strategy.

---

## 4. Two completed work streams

### A. Strategy research → rigorous NEGATIVE result  (see `RESEARCH_NOTE.md`)
Tested 11 strategies + a regime-aware **directional bias** idea (bull→long-only,
bear→short-only). The promising candidates (`regime_bb` directional OOS +0.66
Sharpe; `bollinger` reflect +2.55) **both failed adversarial validation**:
- `bollinger` 2.55 = pooling artifact of ~13 sparse trades; 0/10 disjoint windows significant.
- `regime_bb` directional = knife-edge: rests on one ~6-trade 2024 bull fold; breaks
  one grid-step away (ADX 20→25, bb_std 2.0→2.5); collapses to ~0 with more held-out
  data; re-optimising for the directional metric overfits (in-sample champion is worst OOS).

**Conclusion: no strategy in this family is worth live capital.** The durable
contribution is the **adversarial validation harness** (`_val_*.py`): disjoint-window
stability + parameter perturbation + split/threshold sensitivity + re-opt-then-OOS.
Run it on ANY future candidate before trusting it.

### B. Exogenous signal capture suite  (see `SIGNALS.md`, `docs/DATA_SOURCES.md`)
New `local_system/signals/` package — data outside the price lake, all event-time
UTC stamped for no-lookahead joins. All four subsystems built, **live-tested**, committed:
- **`futures.py`** — Binance USDM funding / OI / long-short positioning (BTC, SOL). No key.
- **`macro.py` + `correlations.py`** — DXY/SPX/NDX/Gold/VIX/US10Y + BTC/ETH/SOL daily
  panel; correlations on returns; macro ffilled across crypto weekends. (BTC–ETH 0.92,
  BTC–SPX +0.42, BTC–DXY −0.24 verified.)
- **`news/`** — pluggable adapters: RSS (Cointelegraph/CoinDesk/Decrypt/etc.) +
  **Trump Truth Social** (`trumpstruth.org/feed`, no key — works). 135 events captured.
- **`live_rollup.py`** — the live-data fix (see §7).
- **`cli/signals.py`** — one command: capture + emit publishable `state/signals/report.md`.

---

## 5. Key findings (don't re-learn these the hard way)

1. **No promotable strategy exists.** The traffic-light composite score
   (`Sharpe·0.4 + win·0.3 + dd·0.3`) is **gameable** by sparse, high-win-rate
   strategies — it ranked the bollinger artifact top. A non-gameable metric (min
   trade count, or require CI-low > 0) is listed in §9.
2. **Significance = lower CI bound > 0 that survives perturbation + more held-out
   data.** A high point Sharpe/win-rate is not evidence. Nothing here cleared that bar.
3. **Failure is market-wide, not BTC-specific** (ETH/SOL same params worse).
4. **Directional bias helps on average but can't manufacture an edge** — shifts a
   −0.6 to a fragile, ~0%-return +0.6.

---

## 6. How to run things

```powershell
$env:LAKE_ROOT="D:/Documents/11Projects/crypto-lake-rs/data/parquet"

# Backtest cycle (updates traffic light)
uv run python -m local_system.cli.reflect --years 5

# Directional walk-forward A/B
uv run python -m local_system.cli.walkforward --regime-folds --from 2021-05-25 --to 2026-05-24 [--directional]

# Signal capture + publishable digest -> state/signals/report.md
uv run python -m local_system.cli.signals

# Individual collectors
uv run python -m local_system.signals.futures BTCUSDT SOLUSDT
uv run python -m local_system.signals.news.capture
uv run python -m local_system.signals.correlations

# Dashboard (Streamlit)
uv run streamlit run dashboard.py

# Live monitor
uv run python -m local_system.paper_trader
```

---

## 7. Gotchas / hard-won lessons

- **Lake live-data corruption (fixed).** Live 1s partitions have ~1140 files/day and
  TWO parquet-corruption modes: truncated footers ("No magic bytes...") AND corrupt
  thrift metadata ("TProtocolException", reported with no file path). The fix:
  `signals/live_rollup.py` reads each live day once via a **bisecting DuckDB reader**
  (one query for the whole day; split only to isolate+skip corrupt files), aggregates
  to 1h, caches under `state/lake_rollup/`. `load_history_hybrid()` stitches clean
  backfill + cached rollups. First build ~5min one-time; cached loads ~2s. The proper
  upstream fix is for the collector to write valid parquet / backfill recent days clean.
- **Usage limits kill long workflows.** This account hits usage limits often; a long
  background `Workflow` (multi-agent fan-out) gets cut off mid-flight every time and
  `resumeFromRunId` re-runs from scratch rather than caching → zero progress across
  many attempts. **Do research inline / in short single-shot agent calls, and commit
  each piece immediately.** If a workflow stalls, kill it (TaskStop) and harvest
  completed agents' results from their transcript `.jsonl` / journal on disk.
- **Durability = commit promptly.** The user's chosen protection against work loss
  is regular commits (not a supervisor). Two file-writes were swallowed by internal
  errors this session and recovered only because of disciplined commits. **Verify
  each write persisted (read-back / `wc -l`), then commit.**
- **Windows console is cp1252** — avoid Unicode (→, ·, emoji) in `print()` / strings
  that hit stdout; it raises `UnicodeEncodeError` or mangles. Files are UTF-8 fine.

---

## 8. Guardrails (from `CLAUDE.local.md` — non-negotiable)

- **Never** suggest setting `HERMES_TRADING_MODE=live` or
  `HERMES_TRADING_I_ACCEPT_RISK=true` without the user explicitly asking.
- Before touching any `.env` value related to live trading or real money, **stop and ask.**
- Plan-first for anything beyond a single-file edit; explain async/ccxt non-obvious bits.
- Commit messages must **not** mention Claude / Anthropic / AI.
- All work so far is **paper/research only** — nothing touches live money.

---

## 9. Open threads / next steps

1. **User's "novel ideas"** — the user said they have novel strategy ideas to try
   *after* the signal suite. **This is the next thing to ask about / pick up.**
2. **VPS deployment** — user plans to run the suite on a free VPS and publish
   `state/signals/report.md` to their website, and eventually "let people submit
   strategies to run." ⚠️ That last part = **executing untrusted code** → must be
   sandboxed (see the security flag in `SIGNALS.md`). Also resolve the repo question (§1).
   The monitor should run as a **detached, supervised process** on the VPS, not a
   child of an interactive session.
3. **Reconcile with `hermes-trading-agent`** — it has a `hermes_trading/` package
   already fetching some macro (`^VIX`, `DX-Y.NYB`). Decide whether the signal suite
   ports there or lewis-strat-trader becomes the deploy repo.
4. **Use the signals as strategy features** — they're collected but not yet joined to
   bars / fed into any strategy. That's the point of collecting them.
5. **Non-gameable promotion metric** — penalise sparse-trade Sharpe so the traffic
   light can't promote artifacts (§5.1).
6. **Wire the researched-but-unbuilt sources** — FRED real yields (`DFII10`, high
   value), CryptoPanic/GDELT sentiment, extra futures venues (Bybit/OKX/Hyperliquid),
   Coinglass liquidations. See `docs/DATA_SOURCES.md`.

---

## 10. File map

| Path | What |
|---|---|
| `RESEARCH_NOTE.md` | The strategy-research write-up (negative result, methodology) |
| `SIGNALS.md` | Signal-suite overview + how to run + VPS notes + security flag |
| `docs/DATA_SOURCES.md` | Concrete endpoints/auth/caveats for every signal source |
| `dashboard.py` | Streamlit research dashboard |
| `local_system/backtester.py` | Walk-forward engine (costs, bootstrap CI, `direction=`) |
| `local_system/cli/{reflect,walkforward,optimize,status,signals}.py` | CLIs |
| `local_system/strategies/registry.py` | Strategy registry + grids |
| `local_system/signals/{futures,macro,correlations,live_rollup}.py` | Signal collectors |
| `local_system/signals/news/{base,rss,trump,capture}.py` | News/social suite |
| `_val_*.py` | Adversarial validation scripts (the reusable harness) |
| `_oos_*.py`, `_optimize_regime_bb_directional.py` | OOS + directional opt scripts |
| `state/strategy.yaml`, `state/challengers.yaml`, `state/comparison.json` | Live config + traffic-light state |
| `CLAUDE.local.md` | Personal guardrails (live-trading guards, working style) |
