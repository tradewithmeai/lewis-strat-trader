---
name: signoff
description: End-of-day routine for this trading-research repo — run when the user signs off ("signing off", "end of day", "wrap up for today", "/signoff"). Updates today's WORKLOG narrative, refreshes the undergrad/master's/PhD progress tracker (docs/PAPER/progress.json), commits everything, and prints a short end-of-day summary. Built to be run nightly so progress is recorded and publishable on the dashboard.
---

# Sign-off — nightly progress routine

The user runs this at the end of a working session. It captures the day's
progress durably and updates the public-facing progress tracker, so the
undergrad → master's → PhD timeline on the dashboard stays current and the
build-in-public record never drifts. Composes with the `/worklog` skill.

## Steps

1. **Worklog.** Run the `/worklog` procedure (see `.claude/skills/worklog/`):
   read `state/commit_log.tsv` for commits since the last WORKLOG entry, plus any
   uncommitted work this session, and append a structured narrative entry
   (Context / Did / Tested / Decided / Dead-ends / Next) to `docs/WORKLOG.md`.
   Real numbers, real decisions, record rejections. Never invent.

2. **Progress tracker.** Update `docs/PAPER/progress.json`:
   - Set `updated` to today's date (UTC).
   - For each milestone touched today, advance its `status`
     (`todo` → `active` → `done`) and set `date` (YYYY-MM-DD) when it becomes
     `done`. Only mark `done` what is genuinely complete and committed — be
     conservative; this is a public record.
   - If today's work created a new milestone not yet listed, add it under the
     right tier (undergrad / masters / phd) with a stable `id`.
   - Tier definitions live in `docs/PAPER/THESIS_STRUCTURE.md` and
     `ROADMAP.md` — keep the tracker consistent with them.

3. **Commit.** Stage the worklog, the progress tracker, and any other work from
   the session, and commit with a factual message (NO mention of Claude /
   Anthropic / AI — per the global guardrail). The `post-commit` hook records the
   spine automatically.

4. **End-of-day summary.** Print a short readout to the user:
   - What moved today (1–3 bullets).
   - Current tier completion: undergrad / master's / phd percentages
     (done = 1.0, active = 0.5, of each tier's milestones).
   - The single most important thing queued for next session.

## Rules

- **Honest status only.** A milestone is `done` only when its artifact is
  committed and verified. Half-finished work is `active`, not `done`. The tracker
  is published — overstating progress is worse than understating it.
- **Durability.** Verify the writes (the worklog entry and the progress update
  persisted) before committing; commit promptly so a session end never loses the
  day's record.
- **One entry per session.** If `/worklog` already ran this session, extend/There
  is no need to duplicate — just refresh the progress tracker and commit.
- Keep the summary short — this fires at sign-off, not a status meeting.
