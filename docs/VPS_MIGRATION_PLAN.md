# VPS migration plan — Krystal (CPU) + RunPod (GPU, on-demand)

Companion to `VPS_SETUP.md`. That file is the generic stand-up kit; this is the
**cost-aware plan for the actual target**: a CPU VPS (no GPU, RAM is the expensive
constraint) with RunPod hired per-hour for short GPU bursts.

## Hosting / cost
- **Free period:** Krystal Cloud (free credit). CPU-only, 1/3/6 GB tiers — pricey.
- **After free period:** migrate to **Hetzner** — **8 GB @ $10.99/mo** is the
  target (headroom for Hermes' Chromium + Streamlit + Claude Code); **4 GB @
  $5.99/mo** is the austerity fallback (only if Hermes stays lean / no constant
  browser automation). The git-bridge-for-results design below is what keeps even
  the 4 GB box from ever needing the lake.

## Guiding principle
The box is **weak but patient** — CPU-only, RAM-bound, but it runs all day.
Optimise for **throughput, not latency**: serialise heavy jobs on a schedule,
and keep anything GPU-class off the box entirely. Split work by *weight*, not by
feature.

## Measured facts (2026-06-11)
- Price lake: **11.45 GB across ~2,039,958 parquet files** → too big/too many
  files to sync onto an expensive small VPS. Stays local.
- `dashboard.py` imports only pandas/plotly/streamlit (no torch) and falls into
  read-only **public view** when `LAKE_ROOT` is absent — so it runs torch-free
  and lake-free on the VPS, rendering only committed result artifacts.
- Heavy signal stack (FinBERT + embeddings + LLM stance) needs multi-GB RAM /
  GPU → does **not** run on the VPS.
- **The lake holds second-resolution data; Binance klines (1-min bars) cannot
  substitute.** So the VPS_SETUP §5 "klines fallback" is NOT scientifically valid
  for the sec/sec analysis — the event study / `reflect` must run where the lake
  (or a bridged slice of it) is available. The VPS never runs them.

## Placement

### The always-on VPS — lean (NO torch/transformers)
Krystal **6 GB** during the free period → Hetzner **8 GB** after. Ubuntu 24.04 LTS.
The box runs only the lean trio below (dashboard + Hermes + Claude Code); it never
touches torch or the lake.

| Component | Mechanism | Notes |
|---|---|---|
| Public dashboard | `streamlit run dashboard.py`, systemd unit, nginx reverse-proxy → `stratbot.solvx.uk` + Let's Encrypt | public-view mode; needs only repo files |
| **Hermes** collector | installed via its official one-step installer (handles repo); runs as supervised process | hourly Truth Social pull + flag, daily headline scan. Keep heavy model inference off-box → RunPod batch. |
| Claude Code analyst | nightly `/signoff` cron + interactive over SSH | worklog/signoff/reflect skills travel with repo |
| Git repo | clone, no lake | `LAKE_ROOT` → empty dir so imports don't raise (VPS_SETUP §3) |

Install the **lean** dependency set (omit the `research` extra) so torch never
lands on the box.

**Collector decision (2026-06-11):** use **Hermes Agent** (Nous Research,
MIT-licensed, `github.com/NousResearch/hermes-agent`). Site:
https://hermes-agent.nousresearch.com/

- **Linux install (the VPS):** `curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash` → `hermes setup`.
  (The advertised `irm …/install.ps1 | iex` is the **Windows** variant — do not
  run it on the box.) Installer verified: user-scoped, no admin, no telemetry;
  installs uv + Python 3.11 + portable Git + Node 22 + Playwright Chromium + repo.
- **RAM reality:** bundles headless Chromium (300 MB–1 GB+ when active) → confirms
  the **6 GB tier**; infeasible on 1/3 GB alongside Streamlit. Scope Hermes to the
  collector role; don't let browser automation run constantly.
- **LLM backend:** it's a full autonomous agent and needs a model. CPU-only box
  can't self-host usefully → point it at a **hosted API** (key + cost) at
  `hermes setup`.

Job spec to wire: hourly — pull new Truth Social posts, flag market-relevant ones;
daily — scan policy/business headlines; append everything event-time-stamped to
the signal store.

Note the repo already has a deterministic Truth Social puller (`trump_archive.py`
→ CNN's public mirror, archived back to Feb 2022, refreshed ~5 min upstream).
Decide during install whether Hermes supersedes it or runs alongside it as the
pinned-snapshot source; because CNN maintains the upstream archive, a missed
Truth Social pull is backfillable, so the higher-value Hermes contribution is the
**headline** arm (no upstream archive → genuinely unrecoverable if not captured).

### RunPod GPU — per-hour, on-demand "heavy forge"
- FinBERT + embeddings + local LLM relabel over the accumulated corpus, in one
  pass, then commit the frozen+hashed artifacts and tear the pod down.
- The signal is deterministic and hashed (`SIGNAL_MANIFEST.json`), so the VPS
  consumes what RunPod produces — no live model on the VPS.
- Cadence: weekly, or when enough new posts accumulate. A couple of GPU-hours.

### Desktop (lake's home) + the two bridges
The 11.45 GB / 2M-file lake stays on the desktop — never synced to the VPS
(duplicating + syncing it would cost more than it's worth; a dedicated "lake VPS"
is **not** warranted). Lake-dependent jobs (`_event_study_trump.py`, `reflect`,
walk-forward backtests) run on the desktop on a schedule. Two bridges carry the
data outward, each sized to its consumer:

1. **Results → VPS, via git.** The dashboard needs only small result artifacts
   (traffic-light state, `progress.json`, backtest outputs), which are committed
   to the repo. Desktop computes → commits → VPS `git pull` → dashboard renders.
   No live link, nothing to keep up. This is the only bridge the dashboard needs.
2. **Lake *slice* → RunPod, on demand.** When a heavy GPU run genuinely needs
   sec/sec data, bridge only the required asset+window — tar the slice, or expose
   a tiny read-only slice-server on the desktop over a **Tailscale** link (NAT
   traversal, encrypted; never expose the lake to the public internet). Not the
   full 2M files.

## Scheduling (use the all-day budget)
- **Hourly (VPS cron):** Hermes pull + cheap flag. The irreplaceable job —
  real-time capture can't be backfilled.
- **Nightly (VPS cron):** `/signoff` → worklog + progress.json + commit.
- **On-demand (manual):** spin RunPod → full signal regen → commit → tear down.

## Drop-order if even 6 GB is too tight
1. Full strategy-lab view → public view only (already the off-lake default).
2. On-box mini-LLM flagging → keyword-only flag; full classify → RunPod batch.
3. Nightly Claude Code cron → manual SSH sessions only.

**Never drop:** the collector *pull* (lost posts are unrecoverable) and the
public dashboard.

## Security (carried from VPS_SETUP §8)
Paper/research only. Never set `HERMES_TRADING_MODE=live` or `*_I_ACCEPT_RISK=true`.
Run residents as supervised processes (systemd), not children of a shell.

## Human gate (blocks execution)
1. Create the Krystal box (6 GB, Ubuntu 24.04 LTS recommended).
2. Provide SSH access, or run the setup commands via `! ssh user@ip "..."`.
3. Add DNS **A record**: `stratbot.solvx.uk` → VPS IP (needs the box's IP first).

Collector and subdomain are now decided (above); the only remaining human gate is
the box + DNS.
