# Hermes self-setup session — 2026-06-15

Record of the Nous **Hermes Agent** (v0.16.0, model gpt-5.4-mini) bootstrapping
itself as the VPS resident agent. Captured for the project record and as evidence
for the master's-tier **AI-augmentation** study (an autonomous agent inspecting the
repo, standing up monitoring, and installing Claude Code to do strategy R&D).

Hermes runs on the VPS (`stratbot`, 185.44.253.199) as user `kc-user`.

## Session transcript (faithful summary)

**User:** "you are read only. confirm read only"
**Hermes:** Confirmed read-only; no changes.

**User:** "you are running on a vps. the vps has a papertrading system... familiarise yourself with the code. i can give you the repo"
**Hermes:** Asked for repo path/URL.

**User:** `https://github.com/tradewithmeai/lewis-strat-trader.git`
**Hermes:** Shallow-cloned to `/tmp/lewis-strat-trader`, read README/pyproject/registry/base/
paper_trader/backtester/reflect/status/optimize/walkforward/scoring/lake_adapter/
strategies/HANDOFF/dashboard/DATA_SOURCES/SIGNALS, ran pygount (~5.8k LOC Python, 50 files).
Produced an accurate architecture map: lake_adapter (DuckDB parquet reader),
backtester (walk-forward 80/20, fees/slippage, Sharpe CI), scoring (traffic-light),
paper_trader (async 5-min loop), strategies registry (11 strategies), signals suite.
Correctly flagged that README/HANDOFF are stale (active strategy is `breakout` per
state/strategy.yaml, not the README's `markov_regime`) — "trust the code and state files."

**User:** "save that to a local file for your reference"
**Hermes:** Wrote `/home/kc-user/lewis-strat-trader_reference.md`.

**User:** "there is a data lake collecting market and macro data... do not change or interfere
with the running service but inspect how it runs... part of your job will be to manage this
service and report outages"
**Hermes:** Inspected read-only. Found:
- `cryptolake.service` active (running) since 2026-06-12 01:27 UTC, `Restart=on-failure`,
  `NRestarts=0`, listens on :8000, exec `crypto-lake-rs --config config.yml --no-tray --retention-days 0`.
- `lake-snapshot.timer` daily 04:00 UTC → `lake_snapshot.sh` (tar → gdrive:crypto-lake-snapshots
  → prune); last two runs OK (06-14 3.5G, 06-15 3.7G).
- Live `/api/v1/health`: 4.4M bars, 138.5M messages, 31.8M trades, 2 ws disconnects/reconnects.
- `health.json`: PRODUCTION, 3 exchanges (binance/coinbase/kraken), 19 symbols, 165,593 parquet files.
- Noted `/api/v1/analysis/summary` is slow (scans parquet) — query timed out.
- Created a self-improvement skill `vps-service-observability`.

**User:** "we also have a paper trading system to compare strategies... your main job will be to
try to come up with more winning strategies. you can search the web... request ml and data
analysis... request further data... short and long strategies... one new strategy per week...
you can install claude code on the vps"
**Hermes:** Acknowledged the R&D mandate; offered to audit the strategy set / set up a weekly
workflow.

**User:** "install claude code in a safe location on the vps"
**Hermes:** `npm install -g @anthropic-ai/claude-code` (prefix `/home/kc-user/.hermes/node`),
symlinked to `/home/kc-user/.local/bin/claude`. Version 2.1.178.

**User:** "you have to use the interactive claude session... if you use the -p method it reverts
to API usage and it is very expensive... create a skill to run a request to claude code"
**Hermes:** Created skill `claude-code-interactive-request` (open `claude` REPL, paste prompt,
avoid `-p`; manual paste-fallback if no PTY).

**User:** "lets login with this claude session. can we have a browser inside the vps? is this secure?"
**Hermes:** No browser installed; advised against a general-purpose browser on the VPS; recommended
console/key login.

**User:** "forget the browser... we will use claude auth login/logout" → "run it now" →
(login is interactive; user ran it themselves via SSH) → "done"
**Hermes:** Verified `claude auth status`: logged in, **Claude Team account, org Solvx,
solutions@solvx.uk**.

## State after this session
- Claude Code installed on the VPS (`~/.local/bin/claude`, v2.1.178), logged in (Team/subscription
  — NOT API, to control cost; must be driven via the interactive REPL, not `claude -p`).
- Hermes has a read-only repo reference note + a VPS service-observability skill + an
  interactive-claude-request skill.
- Mandate given to Hermes: manage/monitor the lake service + report outages; develop ~1 new
  trading strategy/week (web research + ML/analysis + new data requests allowed).

## Next (planned)
- Have Hermes stand up the **news + Trump-Truth-Social monitor** using the *existing* signal
  code (`local_system/cli/signals.py` → `state/signals/report.md`; light deps only; the heavy
  FinBERT/LLM classification stays off the VPS). See the brief handed to Hermes.
- Guardrail reminder: Hermes must not touch `cryptolake.service` or the lake data.
