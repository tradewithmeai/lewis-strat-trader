---
name: worklog
description: Append a narrative entry to docs/WORKLOG.md documenting the work, decisions, tests, runs, and dead-ends since the last entry — for this trading-research repo. Use as part of the commit ritual (run BEFORE git commit so the entry lands in the same commit), or whenever the user asks to "log progress", "document this", "update the worklog", or "record what we did". Pairs with the post-commit git hook that records the deterministic commit spine.
---

# Worklog — research journal maintainer

This repo (`lewis-strat-trader`) is a trading-research project where **why a
thing was done, tested, and rejected** is as valuable as the code. `/worklog`
keeps `docs/WORKLOG.md` — a chronological journal of every meaningful twist and
turn — current, by reading the recent conversation and writing a structured
entry only you (the model, with full chat context) can produce.

## When to run

- **As the commit ritual:** run `/worklog` *before* `git add` + `git commit` so
  the new journal entry is included in that commit (no chicken-and-egg).
- On explicit request: "log this", "document the decisions", "update worklog".
- After any meaningful arc even without a commit (a big test result, a rejected
  approach, a design decision).

## What to do

1. **Find the gap.** Read the tail of `docs/WORKLOG.md` to see the timestamp/
   commit of the last entry. Read `state/commit_log.tsv` (written by the
   post-commit hook: `iso<TAB>hash<TAB>subject<TAB>files`) to list commits since
   then — those are the commits this entry should cover. If the file is missing,
   use `git log --oneline` since the last logged hash.

2. **Reconstruct the arc from THIS conversation.** You have the chat in context —
   that is the source the hook cannot access. Extract, for the period since the
   last entry:
   - **Context** — why the work was undertaken (the user's goal / what prompted it).
   - **Did** — what was actually built / changed / run.
   - **Tested** — concrete commands and their **results**: numbers, p-values,
     pass/fail, trade counts, error messages. Quote real figures, not "it worked".
   - **Decided** — the call made *and the reasoning*. Include advisor input,
     user redirections, and trade-offs weighed.
   - **Dead-ends / caveats** — approaches tried and **rejected**, and why. This
     is the highest-value part; never omit a rejected idea.
   - **Next** — what the work sets up.

3. **Append, don't rewrite.** Add one new `## YYYY-MM-DD HH:MM UTC — <title>
   [commit <hash>]` section at the end of `docs/WORKLOG.md`, matching the format
   documented in that file's header. Use the actual UTC time. If the entry
   precedes the commit (the normal ritual), write `[commit pending]` and the
   hook/next run reconciles it, or fill the hash after committing.
   - Multiple related commits → one entry listing all hashes is fine.
   - Be specific and concise. Real numbers and file names. No filler.
   - Preserve everything already in the file; only append.

4. **Verify the write** (read back the tail) so a swallowed write is caught —
   durability matters in this repo.

5. **Hand back to the commit flow.** Remind the user (or proceed, in auto mode)
   that the worklog entry is ready to be staged with the rest of the commit:
   `git add docs/WORKLOG.md && git commit ...`.

## Rules

- **Never invent.** Only log what actually happened in the conversation/tools.
  If a result is uncertain or a run is still in flight, say so explicitly.
- **Record rejections.** A tried-and-failed approach (e.g. a validation that
  came back null, an overlay that didn't help) is a required part of the entry.
- **Respect repo guardrails.** Commit messages and log entries must NOT mention
  Claude / Anthropic / AI agents (per global instructions). Keep the journal
  professional and factual.
- **Decisions need rationale.** "Chose X" is incomplete; write "Chose X over Y
  because Z".
- This skill writes only `docs/WORKLOG.md`. It does not commit on its own unless
  the user asks — it prepares the entry for the surrounding commit.
