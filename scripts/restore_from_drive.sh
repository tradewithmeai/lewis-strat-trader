#!/usr/bin/env bash
# ONE-SCRIPT restore of the whole stack onto a fresh Ubuntu 24.04 box, from:
#   - the bootstrap bundle (secrets + infra)          -> arg $1
#   - the hermes runtime tarball (optional)           -> arg $2, or auto-detected
#   - the daily DATA backup in Google Drive           -> pulled via restored rclone.conf
#   - GitHub (both repos) + committed uv.lock/nginx templates
#
# The migration vehicle: provision a cheap box, copy the bundle(s) over, run this.
# Deliberately NOT `set -e` — a long provisioning script must not abort half-built
# on a benign non-zero (ufw already-enabled, grep no-match, an absent optional
# tarball). Must-succeed steps are guarded with `|| die`; everything else is
# tolerant. Safe to re-run: it will NOT clobber a live paper-race state unless you
# pass FORCE_DATA=1, and it skips the TLS-less nginx step once real certs exist.
#
# Usage (as kc-user, passwordless sudo, on the NEW box):
#   scp stratbot-bootstrap-*.tgz stratbot-hermes-*.tgz newbox:~/
#   ssh newbox 'git clone git@github.com:tradewithmeai/lewis-strat-trader.git /tmp/lst \
#     && bash /tmp/lst/scripts/restore_from_drive.sh ~/stratbot-bootstrap-*.tgz'
set -uo pipefail
shopt -s nullglob

BUNDLE="${1:?usage: restore_from_drive.sh <stratbot-bootstrap-*.tgz> [stratbot-hermes-*.tgz]}"
HERMES_TGZ="${2:-}"
H=/home/kc-user
REMOTE=gdrive:crypto-lake-snapshots
SNAP="$H/lake-snapshots/restore"
export XDG_RUNTIME_DIR="/run/user/$(id -u)"   # so `systemctl --user` can reach the bus
export PATH="$H/.local/bin:$PATH"
say(){ printf '\n\033[1;36m== %s\033[0m\n' "$*"; }
manual(){ printf '\n\033[1;33m[MANUAL] %s\033[0m\n' "$*"; }
die(){ printf '\n\033[1;31m!! FATAL: %s\033[0m\n' "$*"; exit 1; }

[ "$(id -un)" = kc-user ] || die "run as kc-user"
[ -f "$BUNDLE" ] || die "bundle not found: $BUNDLE"
# auto-detect the hermes tarball next to the bundle if not given
if [ -z "$HERMES_TGZ" ]; then for c in "$(dirname "$BUNDLE")"/stratbot-hermes-*.tgz; do HERMES_TGZ="$c"; done; fi

say "unpacking bootstrap bundle"
STAGE=$(mktemp -d)
tar xzf "$BUNDLE" -C "$STAGE" || die "cannot unpack $BUNDLE"
[ -f "$STAGE/MANIFEST.txt" ] && cat "$STAGE/MANIFEST.txt"

say "1/12  base packages (flock/util-linux already present; do NOT apt it)"
sudo apt-get update -qq
sudo apt-get install -y -qq nginx certbot python3-certbot-nginx python3.12-venv \
  git rclone build-essential curl jq zstd >/dev/null || die "apt install failed"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
command -v flock >/dev/null || die "flock missing (expected in util-linux)"

say "2/12  host hardening (linger, swap, ufw, clock)"
sudo loginctl enable-linger kc-user
if ! swapon --show | grep -q /swapfile && [ ! -f /swapfile ]; then
  sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile \
    && sudo swapon /swapfile && echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi
sudo ufw allow OpenSSH  >/dev/null 2>&1 || true
sudo ufw allow 'Nginx Full' >/dev/null 2>&1 || true
sudo ufw --force enable >/dev/null 2>&1 || true
timedatectl set-ntp true 2>/dev/null || true

say "3/12  secrets into place (owner-only)"
install -d -m700 "$H/.ssh" "$H/.config" "$H/.config/rclone" "$H/.config/systemd/user" "$H/.hermes" "$H/bin"
install -m600 "$STAGE/secrets/rclone.conf"       "$H/.config/rclone/rclone.conf"      || die "no rclone.conf in bundle"
install -m600 "$STAGE/secrets/signals-alert.env" "$H/.config/signals-alert.env"       || true
install -m600 "$STAGE/secrets/hermes-auth.json"  "$H/.hermes/auth.json"               || true
for k in "$STAGE"/secrets/ssh-*; do b=$(basename "$k"); install -m600 "$k" "$H/.ssh/${b#ssh-}"; done
ssh-keyscan github.com >> "$H/.ssh/known_hosts" 2>/dev/null || true
sort -u "$H/.ssh/known_hosts" -o "$H/.ssh/known_hosts" 2>/dev/null || true

say "4/12  rclone connectivity to Drive (before we depend on it)"
if ! rclone lsd "$REMOTE" >/dev/null 2>&1; then
  manual "rclone can't reach Drive from this box (new IP?). Run:  rclone config reconnect gdrive:"
  manual "then re-run this script. Stopping here so nothing half-restores."
  die "Drive unreachable — reconnect rclone and re-run"
fi

say "5/12  clone repos + build venv (accept-new host keys so it can't hang)"
cd "$H"
[ -d lewis-strat-trader/.git ] || GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new' \
  git clone git@github.com:tradewithmeai/lewis-strat-trader.git || die "clone lewis failed"
[ -d crypto-lake-rs/.git ] || GIT_SSH_COMMAND='ssh -o StrictHostKeyChecking=accept-new' \
  git clone git@github-lake:tradewithmeai/crypto-lake-rs.git || die "clone crypto-lake-rs failed"
cp -a lewis-strat-trader/scripts/post-commit lewis-strat-trader/.git/hooks/post-commit 2>/dev/null || true
( cd lewis-strat-trader && uv sync ) || die "uv sync failed"
install -m755 lewis-strat-trader/scripts/lake_snapshot.sh "$H/lake_snapshot.sh"

say "6/12  crypto-lake-rs binary (from bundle; skip the rust build)"
install -D -m755 "$STAGE/binary/crypto-lake-rs" "$H/crypto-lake-rs/target/release/crypto-lake-rs" \
  || die "collector binary missing from bundle"

say "7/12  hermes runtime install (BEFORE state, so restored state wins)"
if [ -n "$HERMES_TGZ" ] && [ -f "$HERMES_TGZ" ]; then
  echo "  extracting $HERMES_TGZ"
  tar xzf "$HERMES_TGZ" -C "$H" || die "hermes tarball extract failed"
elif [ ! -x "$H/.local/bin/claude" ]; then
  manual "No hermes runtime tarball, and claude-code/hermes not installed. Reinstall per MANIFEST"
  manual "  (node prefix ~/.hermes/node + the pinned hermes-agent + claude-code npm), THEN re-run."
  echo "  Continuing without hermes; hermes-gateway will be skipped in step 11."
fi

say "8/12  restore DATA from Drive (newest of each; first-run only unless FORCE_DATA=1)"
mkdir -p "$SNAP" "$H/crypto-lake-rs/data"
pull_newest(){ # <glob> <extract-into>  — never fatal; warns on absence/failure
  local f; f=$(rclone lsf "$REMOTE" --include "$1" 2>/dev/null | sort | tail -1)
  [ -n "$f" ] || { echo "  !! no $1 in Drive — skipping"; return 0; }
  echo "  $f -> $2"
  rclone copy "$REMOTE/$f" "$SNAP/" && tar xf "$SNAP/$f" -C "$2" || echo "  !! restore of $f failed"
  rm -f "$SNAP/$f"
}
if [ -f "$H/lewis-strat-trader/state/paper_accounts.json" ] && [ "${FORCE_DATA:-0}" != 1 ]; then
  echo "  live state present — NOT overwriting (set FORCE_DATA=1 to force a data re-pull)"
else
  pull_newest "stratbot-state-*.tar" "$H"                       # state/ + .hermes state
  pull_newest "crypto-lake-*.tar"    "$H/crypto-lake-rs/data"   # parquet
  pull_newest "crypto-raw-*.tar"     "$H/crypto-lake-rs/data"   # raw
fi

say "9/12  helper scripts"
for f in "$STAGE"/bin/*; do install -m755 "$f" "$H/bin/$(basename "$f")"; done

say "10/12  systemd units + nginx (HTTP-only templates; certbot adds TLS later)"
sudo cp -a "$STAGE"/etc-systemd-system/. /etc/systemd/system/ || die "system unit copy failed"
cp -a "$STAGE"/user-systemd/. "$H/.config/systemd/user/" || die "user unit copy failed"
sudo systemctl daemon-reload; systemctl --user daemon-reload
sudo install -m640 -o root -g www-data "$STAGE/secrets/htpasswd_lake" /etc/nginx/.htpasswd_lake || true
if [ ! -d /etc/letsencrypt/live ]; then
  sudo install -m644 lewis-strat-trader/scripts/nginx/stratbot.conf /etc/nginx/sites-available/stratbot
  sudo install -m644 lewis-strat-trader/scripts/nginx/lake.conf     /etc/nginx/sites-available/lake
  for s in stratbot lake; do sudo ln -sf "/etc/nginx/sites-available/$s" "/etc/nginx/sites-enabled/$s"; done
  sudo rm -f /etc/nginx/sites-enabled/default
  sudo nginx -t || die "nginx -t failed on the http-only templates"
  sudo systemctl reload nginx
else
  echo "  certs already present — leaving nginx as-is (re-run is non-destructive to TLS)"
fi

say "11/12  start services (dependency order; consolidate + lake-backup stay OFF)"
sudo systemctl enable --now cryptolake || die "cryptolake failed to start"
sleep 5; journalctl -u cryptolake -n3 --no-pager | grep -q "Wrote" && echo "  lake writing OK" || echo "  !! check cryptolake journal"
systemctl --user enable --now paper-trader || echo "  !! paper-trader failed"
sudo systemctl enable --now stratbot-dashboard || echo "  !! dashboard failed"
sudo systemctl enable --now lake-snapshot.timer reflect-daily.timer signals-monitor.timer || true
if [ -x "$H/.local/bin/claude" ]; then systemctl --user enable --now hermes-gateway || echo "  !! hermes-gateway failed"; \
  else echo "  hermes not installed — skipping hermes-gateway (see step 7)"; fi
echo "  NOTE: lake-consolidate.timer + lake-backup.timer left DISABLED by design."

say "12/12  DONE — remaining human steps"
manual "claude auth login   ->  claude auth status must show subscriptionType: max"
manual "verify: board equities continued (no reset); curl -s localhost:8000 -o /dev/null -w '%{http_code}\\n' == 200"
manual "flip DNS A records (stratbot.solvx.uk + lake.solvx.uk) -> this box's IP"
manual "after DNS resolves here:  sudo certbot --nginx -d stratbot.solvx.uk -d lake.solvx.uk"
manual "once the transferred lake is trusted:  systemctl --user enable --now lake-consolidate.timer"
rm -rf "$STAGE"
echo "restore script complete."
