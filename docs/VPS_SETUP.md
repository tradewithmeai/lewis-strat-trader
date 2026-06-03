# VPS migration kit — lewis-strat-trader

How to stand this repo up on a fresh VPS (with optional cloud GPU) so both a
Claude Code session AND the autonomous collector ("Hermes") can run there 24/7.
Paper/research only — never set live-trading env vars (see Security below).

## 0. Continuity — read these first (the handoff IS the onboarding)
On a fresh box, a new session gets fully oriented by reading, in order:
`HANDOFF.md` → `docs/WORKLOG.md` (the full method trail) → `MEMORY.md` index +
the `memory/` files → `docs/PAPER/` (PREREGISTRATION, ROADMAP, THESIS_STRUCTURE,
progress.json). Nothing is lost in the move.

## 1. Prereqs
- git, Python ≥3.11, `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`).
- For GPU: NVIDIA driver + CUDA. Install the CUDA torch build instead of the
  default CPU wheel (the `research` extra pulls CPU torch from PyPI):
  `uv pip install torch --index-url https://download.pytorch.org/whl/cu124`
  (verify: `python -c "import torch; print(torch.cuda.is_available())"`).

## 2. Clone + install
```bash
git clone https://github.com/tradewithmeai/lewis-strat-trader.git
cd lewis-strat-trader
uv sync --extra research        # research stack: torch, transformers, sentence-transformers, sklearn, lightgbm, openai
cp scripts/post-commit .git/hooks/post-commit && chmod +x .git/hooks/post-commit   # worklog spine
```

## 3. Env vars
- `OPENAI_API_KEY` — for the LLM stance layer (or move it local on GPU; see §6).
- `LAKE_ROOT` — path to a crypto-lake-rs parquet store. **Required at import**
  even for the Trump pipeline (lake_adapter raises if unset). If you are NOT
  syncing the lake, set it to any existing empty dir; the event study then falls
  back to Binance klines automatically (see §5).

## 4. Regenerate the frozen signal (deterministic, from the pinned archive)
```bash
uv run --extra research python -m local_system.signals.trump_archive --refresh   # or keep the pinned snapshot
uv run --extra research python -m local_system.signals.trump_classify
uv run --extra research python -m local_system.signals.trump_signal_local         # FinBERT+embeddings+novelty (GPU ~2min, CPU ~40min)
uv run --extra research python -m local_system.signals.trump_signal_llm           # LLM stance (budget-gated; resumes across days)
uv run --extra research python -m local_system.signals.trump_signal --validate    # merge + gate
```
Cross-check `docs/PAPER/SIGNAL_MANIFEST.json` hashes to confirm the label set
matches (note the reproducibility caveat there re: the gpt-4.1-mini alias).

## 5. Run the analysis
```bash
LAKE_ROOT=... uv run --extra research python _event_study_trump.py              # RQ1 vol effect (+ day-block null, balance)
LAKE_ROOT=... uv run --extra research python _event_study_trump.py --placebo    # content placebo
LAKE_ROOT=... uv run --extra research python _phase2_reaction.py --confirm      # RQ2/RQ3 (needs 100% LLM coverage)
uv run streamlit run dashboard.py                                               # Research Progress + traffic-light UI
```
**Data dependency:** the Trump research needs Binance API reachability (klines,
cached) + the downloadable CNN archive — the deep BTC *lake* history is optional
(klines fallback covers it). The strategy system (`paper_trader`, `reflect`) DOES
need the lake synced.

## 6. GPU payoffs (why the move is worth it)
- FinBERT + embeddings on 27k posts: ~2 min (GPU) vs ~40 min (CPU).
- **Move LLM classification fully local** (a good open instruct model on the GPU)
  → drop the OpenAI 250k-tokens/day cap entirely; re-label the whole corpus in
  one pass (also fixes the alias-reproducibility caveat — pin a local model).
- Headroom to actually *train* a model later (the Phase-3 directive-timing idea,
  once the collector has grown n).

## 7. The two residents
- **Claude Code (analyst):** run interactively / via cron on the VPS; the
  `/worklog`, `/signoff`, `/reflect-now` skills + the post-commit hook travel with
  the repo. The nightly `/signoff` updates the published progress timeline.
- **Hermes (24/7 collector):** TODO — pending the chosen Hermes agent's install.
  Job spec (drop-in natural-language requirements): *hourly — pull new Truth
  Social posts, classify, flag market-relevant ones; daily — scan policy/business
  headlines; append everything event-time-stamped to the lake/signal store.*

## 8. Security (non-negotiable)
- Paper/research only. **Never** set `HERMES_TRADING_MODE=live` or
  `*_I_ACCEPT_RISK=true`. Don't put real money anywhere.
- Run both residents as **detached, supervised processes** (systemd/pm2), not
  children of an interactive shell.
- If the public UI ever executes visitor-submitted strategies, that is untrusted
  code → must be sandboxed (separate concern, see SIGNALS.md security flag).

## 9. Still needed from the human
- Which **Hermes** agent (repo/install docs).
- VPS **OS / GPU type** + how Claude Code is launched there (SSH session? cron?).
- Build-in-public surface (public GitHub is set; site/arXiv/SSRN for papers).
