# Community Strategies — "suggest a strategy, watch it race"

The north-star for the public site (set by the owner, 2026-06-30): visitors
**suggest a strategy** through the site; **Darren reviews the queue weekly**,
tests the candidates, **picks one**, and **adds it to the live race**. Turns the
tournament from a fixed field into a living, community-driven competition.

## The one critical decision: submissions are IDEAS, not code

**Never run user-submitted code.** Accepting executable code from the public is
an arbitrary-code-execution hole — not acceptable on a live box. Instead a
submission is a **described idea** plus, optionally, **parameters chosen from the
existing building blocks** (indicators/rules we already have: RSI, Bollinger,
breakout channels, MA crossovers, cross-sectional rank, funding, vol-target…).
Darren + Claude **translate the idea into a strategy** using the existing
`registry` / `portfolio_backtester`, then backtest it. The human stays in the
loop on what goes live. This keeps the whole feature safe.

## How it works (proposed flow)

1. **Suggest** — a public "Suggest a strategy" panel on the site: handle/name, a
   plain-language description ("buy when X is oversold and funding is negative,
   take profit at Y%"), and optional template params. Appended to
   `state/submissions.jsonl`. Light anti-spam: rate-limit + an LLM moderation
   pass (drop abuse/nonsense), no code field.
2. **Weekly review (Darren)** — a weekly cron (sibling of the daily dream):
   read the new submissions, use the day's Claude run to turn the most promising
   into concrete strategies via the existing harness, backtest each through the
   **rigor gate** (full-history, sign-consistency, mark-to-market DD, beat
   buy-and-hold, bootstrap CI, declare search size). Pick **at most one** that's
   plausible, safe, and distinct from the current field — or **none**, honestly.
3. **Add to the race** — the pick is added as a **live paper account** (it's only
   paper; the existing **cull** removes it if it loses). Show **"suggested by
   @handle"** on its lane, and a **"This week's pick"** highlight. Human veto
   before it goes live.
4. **Engagement** — submitters can watch *their* strategy race; a small
   "community wall" of pending/added/rejected ideas with one-line verdicts.

## Why this fits what's already built

- The **live race board** is the natural home + the reward (watch your idea run).
- The **rigor gate + live cull** mean a weak community pick fails safely and
  honestly — low stakes, self-correcting.
- **Darren's weekly cadence** already exists in spirit (daily dream); this is a
  second, weekly routine pointed at the submission queue.
- Attribution + "this week's pick" are the **build-in-public engagement** the
  project wants.

## Phasing

- **P1 — Submission capture:** the public form + `submissions.jsonl` + moderation.
- **P2 — Weekly Darren review:** cron that translates → backtests → picks (or
  passes), reports to Telegram + writes a verdict per submission.
- **P3 — Into the race:** add the pick as a live account with attribution +
  "This week's pick" on the board; human veto step.
- **P4 — Community wall:** pending/added/rejected ideas with verdicts; submitter
  can follow their entry.

## Voice & philosophy (decided 2026-06-30)

- **Free-text only, by design.** People describe their idea however weird and
  wonderful — no code, no jargon, no template required. Low friction is the
  point. (A guided indicator-picker for technical users is a *later, optional*
  add, not the default.)
- **Fun and informative.** The humour does the teaching: every bot needs just two
  things — **data** (something it can watch) and a **trigger** (when to act). The
  playful reply to a daft idea quietly explains exactly that.
- **Anti-hype, explicitly.** No "I built a 3000% bot" claims. The stance is
  *"bring it down and we'll see if you're right"* — an honest race, costs in,
  forward-tested, with the cull for losers.
- **The Terry test (the house example).** "My tortoise Terry predicts BTC volume
  — when he sits top-right of his tank, volume rises the next day." The right
  response: *brilliant — first, insure Terry. If that's really the signal, the
  recipe is the same as any bot: the **data** is a camera on the tank, the
  **trigger** is 'Terry top-right → expect higher volume'. Wire a bridge to that
  feed and Terry races the field.* It's silly on purpose, and it teaches the
  whole method in one breath. We are **not** chasing pet strategies — it's the
  illustration, not the goal.
- **The system can already take more.** Owner has built the data + harness;
  adding other assets or news feeds as data sources is easy, so "what can it
  watch" is genuinely open.

## Later (beyond the first tournament)

- Display other people's more complex / technical strategies.
- Let entrants **register a wallet** to prove live trading success — real money,
  real verification — as the high tier above the paper race.

_Agreed direction toward the "final stage". P1 (text capture) is being built;
P2–P4 follow._
