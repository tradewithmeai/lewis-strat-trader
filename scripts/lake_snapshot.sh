#!/usr/bin/env bash
# Daily backup to Google Drive as dated, versioned tarballs.
# Canonical source lives here in the repo; deployed to /home/kc-user/lake_snapshot.sh
# on the VPS, run by lake-snapshot.service (timer: 04:00 UTC daily).
#
#   1) crypto-lake-<date>.tar     the parquet lake (bar data)         14-day retention
#   2) stratbot-state-<date>.tar  the irreplaceable SMALL state       60-day retention:
#        - repo state/  (the live paper-race record: paper_accounts.json,
#          equity_history.jsonl, status.json, submissions, community picks — all
#          gitignored, so this snapshot is their ONLY off-box copy)
#        - Darren's evolved state in ~/.hermes: memories/, cron/ (jobs + outputs),
#          state.db (session/conversation history), gateway_state.json, history.
#      EXCLUDES secrets (~/.hermes/auth.json — a live token, deliberately kept OUT
#      of cloud backup) and all reinstallable bulk (venv / node / code / caches).
#
# Both upload to gdrive:crypto-lake-snapshots. Dated names never overwrite; a local
# tar is deleted only AFTER a successful upload (a failed upload keeps it for retry).
# A failure in one tarball does NOT skip the other; the service exits non-zero if
# either failed, so the lake-snapshot-failure hook still fires.
#
# Restore:
#   rclone copy gdrive:crypto-lake-snapshots/<file> .
#   tar xf <file> -C /home/kc-user
#
set -uo pipefail

HOME_DIR=/home/kc-user
SNAPDIR="$HOME_DIR/lake-snapshots"
REMOTE=gdrive:crypto-lake-snapshots
LOG="$HOME_DIR/lake_backup.log"
STAMP=$(date -u +%Y-%m-%d)
ts() { date -u +%FT%TZ; }
mkdir -p "$SNAPDIR"
overall=0

# ---- 1) parquet lake ----------------------------------------------------------
LAKE_TAR="$SNAPDIR/crypto-lake-$STAMP.tar"
echo "[$(ts)] building $LAKE_TAR" >> "$LOG"
if tar -cf "$LAKE_TAR" -C "$HOME_DIR/crypto-lake-rs/data" parquet 2>>"$LOG" && [ -s "$LAKE_TAR" ]; then
  echo "[$(ts)] uploading $(du -h "$LAKE_TAR" | cut -f1) lake to $REMOTE" >> "$LOG"
  if rclone copy "$LAKE_TAR" "$REMOTE" --log-file="$LOG"; then
    rm -f "$LAKE_TAR"
    rclone delete "$REMOTE" --min-age 14d --include "crypto-lake-*.tar" --log-file="$LOG"
    echo "[$(ts)] lake snapshot OK" >> "$LOG"
  else
    echo "[$(ts)] LAKE UPLOAD FAILED — kept $LAKE_TAR for retry" >> "$LOG"; overall=1
  fi
else
  echo "[$(ts)] LAKE TAR FAILED" >> "$LOG"; rm -f "$LAKE_TAR"; overall=1
fi

# ---- 2) irreplaceable small state (race record + Darren's brain) --------------
STATE_TAR="$SNAPDIR/stratbot-state-$STAMP.tar"
# Build the item list; include the SQLite sidecars only if present (WAL/shm come
# and go across checkpoints — listing a missing path would noise up the log).
STATE_ITEMS=(
  lewis-strat-trader/state
  .hermes/memories
  .hermes/cron
  .hermes/gateway_state.json
  .hermes/.hermes_history
  .hermes/state.db
)
for opt in .hermes/state.db-wal .hermes/state.db-shm; do
  [ -e "$HOME_DIR/$opt" ] && STATE_ITEMS+=("$opt")
done
echo "[$(ts)] building $STATE_TAR" >> "$LOG"
# Live files (equity_history.jsonl, state.db) can change mid-read → tar returns
# rc=1 with a benign "file changed as we read it". We upload as long as a
# non-empty tarball was produced (append-only / small-json are safe point-in-time).
tar -cf "$STATE_TAR" -C "$HOME_DIR" "${STATE_ITEMS[@]}" 2>>"$LOG"
trc=$?
if [ -s "$STATE_TAR" ]; then
  [ "$trc" -ne 0 ] && echo "[$(ts)] note: state tar rc=$trc (live file changed mid-read; tarball still valid)" >> "$LOG"
  echo "[$(ts)] uploading $(du -h "$STATE_TAR" | cut -f1) state to $REMOTE" >> "$LOG"
  if rclone copy "$STATE_TAR" "$REMOTE" --log-file="$LOG"; then
    rm -f "$STATE_TAR"
    rclone delete "$REMOTE" --min-age 60d --include "stratbot-state-*.tar" --log-file="$LOG"
    echo "[$(ts)] state snapshot OK" >> "$LOG"
  else
    echo "[$(ts)] STATE UPLOAD FAILED — kept $STATE_TAR for retry" >> "$LOG"; overall=1
  fi
else
  echo "[$(ts)] STATE TAR produced no output (rc=$trc)" >> "$LOG"; overall=1
fi

echo "[$(ts)] backup run complete (rc=$overall)" >> "$LOG"
exit "$overall"
