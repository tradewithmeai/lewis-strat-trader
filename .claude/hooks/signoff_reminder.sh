#!/usr/bin/env bash
# Stop hook — nudge to run /signoff when there is unlogged work.
# REMINDER ONLY: never commits, stages, or modifies any file. Rate-limited to
# once per ~2h via a marker inside .git/ (untracked, never committed).
# Signal: commits since the last commit that touched docs/WORKLOG.md (a /signoff
# commits the worklog, resetting this to 0) + any uncommitted TRACKED changes.
set +e

root="$(git rev-parse --show-toplevel 2>/dev/null)" || { echo '{}'; exit 0; }
cd "$root" 2>/dev/null || { echo '{}'; exit 0; }
gitdir="$(git rev-parse --git-dir 2>/dev/null)" || { echo '{}'; exit 0; }
marker="$gitdir/.signoff_reminder"

# Rate-limit: silent if we already reminded in the last 120 minutes.
if [ -f "$marker" ] && find "$marker" -mmin -120 2>/dev/null | grep -q .; then
  echo '{}'; exit 0
fi

last="$(git log -1 --format=%H -- docs/WORKLOG.md 2>/dev/null)"
if [ -n "$last" ]; then
  n="$(git rev-list --count "${last}..HEAD" 2>/dev/null)"
else
  n="$(git rev-list --count HEAD 2>/dev/null)"
fi
n="${n:-0}"

dirty="$(git status --porcelain -uno 2>/dev/null | head -1)"

if { [ "$n" -gt 0 ]; } 2>/dev/null || [ -n "$dirty" ]; then
  touch "$marker" 2>/dev/null
  if [ "$n" -gt 0 ] 2>/dev/null; then
    msg="${n} commit(s) since the last worklog entry"
    [ -n "$dirty" ] && msg="${msg} (plus uncommitted changes)"
  else
    msg="uncommitted changes present"
  fi
  msg="Reminder: ${msg} - run /signoff to journal the session before you go."
  printf '{"systemMessage": "%s"}\n' "$msg"
else
  echo '{}'
fi
exit 0
