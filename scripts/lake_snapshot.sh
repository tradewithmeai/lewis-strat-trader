#!/usr/bin/env bash
# Daily backup to Google Drive as dated, versioned tarballs.
# Canonical source lives here in the repo; deployed to /home/kc-user/lake_snapshot.sh
# on the VPS, run by lake-snapshot.service (timer: 04:00 UTC daily).
#
# Uploads (order = most-critical-and-smallest first, so the irreplaceable race
# record is safe within seconds even if a later big upload fails):
#   1) stratbot-state-<date>.tar  small state          60-day retention
#        repo state/ (live paper-race record: paper_accounts.json,
#        equity_history.jsonl, status, submissions, community — all gitignored,
#        so this is their ONLY off-box copy) + Darren's ~/.hermes memories/cron/
#        state.db/gateway_state.  EXCLUDES ~/.hermes/auth.json (a live token).
#   2) crypto-lake-<date>.tar     parquet bar data     14-day retention
#   3) crypto-raw-<date>.tar      raw tick capture     4-day  retention (5GB+/day)
#
# All upload to gdrive:crypto-lake-snapshots. Dated names never overwrite; a local
# tar is deleted only AFTER a successful upload (a failed upload keeps it for
# retry). One tarball's failure does NOT skip the others; the service exits
# non-zero if any failed, so the lake-snapshot-failure hook still fires.
#
# NOTE: this is the DATA backup. Infra (systemd units, nginx, binary, notifier
# scripts) is captured separately by scripts/backup_config.sh; secrets by
# scripts/export_secrets.sh. Together they enable scripts/restore_from_drive.sh.
#
# Restore one tarball:
#   rclone copy gdrive:crypto-lake-snapshots/<file> . && tar xf <file> -C /home/kc-user
#
set -uo pipefail

HOME_DIR=/home/kc-user
SNAPDIR="$HOME_DIR/lake-snapshots"
REMOTE=gdrive:crypto-lake-snapshots
LOG="$HOME_DIR/lake_backup.log"
STAMP=$(date -u +%Y-%m-%d)
ts() { date -u +%FT%TZ; }
mkdir -p "$SNAPDIR"

# Single-writer lock: if a run is already in progress (e.g. a manual run overlaps
# the 04:00 timer), skip rather than collide on identically-named tarballs.
exec 9>"$SNAPDIR/.snapshot.lock"
if ! flock -n 9; then
  echo "[$(ts)] another snapshot run holds the lock — skipping this invocation" >> "$LOG"
  exit 0
fi

overall=0

# upload_tar <label> <tar-path> <retain-glob> <retain-days> <tolerate-live-change>
#   tolerate-live-change=1 → accept tar rc!=0 as long as a non-empty tarball was
#   produced (for dirs being written live: raw capture, state.db, equity jsonl).
upload_tar() {
  local label="$1" tar="$2" glob="$3" days="$4" tolerate="$5" trc
  if [ ! -s "$tar" ]; then
    echo "[$(ts)] ${label^^} TAR produced no output" >> "$LOG"; overall=1; return
  fi
  echo "[$(ts)] uploading $(du -h "$tar" | cut -f1) $label to $REMOTE" >> "$LOG"
  if rclone copy "$tar" "$REMOTE" --log-file="$LOG"; then
    rm -f "$tar"
    rclone delete "$REMOTE" --min-age "${days}d" --include "$glob" --log-file="$LOG"
    echo "[$(ts)] $label snapshot OK" >> "$LOG"
  else
    echo "[$(ts)] ${label^^} UPLOAD FAILED — kept $tar for retry" >> "$LOG"; overall=1
  fi
}

# ---- 1) irreplaceable small state (race record + Darren's brain) — FIRST ------
STATE_TAR="$SNAPDIR/stratbot-state-$STAMP.tar"
STATE_ITEMS=(
  lewis-strat-trader/state
  .hermes/memories .hermes/cron .hermes/gateway_state.json
  .hermes/.hermes_history .hermes/state.db
)
for opt in .hermes/state.db-wal .hermes/state.db-shm; do
  [ -e "$HOME_DIR/$opt" ] && STATE_ITEMS+=("$opt")
done
echo "[$(ts)] building $STATE_TAR" >> "$LOG"
# --exclude auth.json: STATE_ITEMS already lists explicit non-secret paths, but this
# guarantees the live Hermes token can never ride into a cloud tarball even if the
# item list is later widened. auth.json travels only in the off-Drive bootstrap bundle.
tar -cf "$STATE_TAR" -C "$HOME_DIR" --exclude='.hermes/auth.json' "${STATE_ITEMS[@]}" 2>>"$LOG" || \
  echo "[$(ts)] note: state tar rc=$? (live file changed mid-read; tarball still valid)" >> "$LOG"
upload_tar state "$STATE_TAR" "stratbot-state-*.tar" 60 1

# ---- 2) parquet lake (write-once files, so tar is clean) ----------------------
LAKE_TAR="$SNAPDIR/crypto-lake-$STAMP.tar"
echo "[$(ts)] building $LAKE_TAR" >> "$LOG"
if tar -cf "$LAKE_TAR" -C "$HOME_DIR/crypto-lake-rs/data" parquet 2>>"$LOG"; then
  upload_tar lake "$LAKE_TAR" "crypto-lake-*.tar" 14 0
else
  echo "[$(ts)] LAKE TAR FAILED" >> "$LOG"; rm -f "$LAKE_TAR"; overall=1
fi

# ---- 3) raw tick capture (live-written; tolerate mid-read change) -------------
RAW_TAR="$SNAPDIR/crypto-raw-$STAMP.tar"
echo "[$(ts)] building $RAW_TAR" >> "$LOG"
tar -cf "$RAW_TAR" -C "$HOME_DIR/crypto-lake-rs/data" raw 2>>"$LOG" || \
  echo "[$(ts)] note: raw tar rc=$? (live capture changed mid-read; tarball still valid)" >> "$LOG"
upload_tar raw "$RAW_TAR" "crypto-raw-*.tar" 4 1

echo "[$(ts)] backup run complete (rc=$overall)" >> "$LOG"
exit "$overall"
