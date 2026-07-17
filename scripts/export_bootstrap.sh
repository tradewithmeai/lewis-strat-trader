#!/usr/bin/env bash
# Export the SECRETS + INFRA needed to rebuild the VPS — everything NOT in Google
# Drive and NOT in a git repo. Produces TWO local files you keep safe off-cloud:
#
#   stratbot-bootstrap-<date>.tgz  (small, ~16MB) — secrets + systemd units +
#       collector binary + helper scripts + MANIFEST.  Password-manager-able.
#   stratbot-hermes-<date>.tgz     (large) — the Hermes agent RUNTIME (code, node,
#       venv, skills) minus the state that's already in Drive and minus caches.
#       This is the one component with no other home (Hermes isn't in a repo and
#       its original install command isn't recorded), so we ship the runtime whole.
#
# Run ON the live VPS as kc-user (uses sudo for root-owned files):
#     bash scripts/export_bootstrap.sh
# then pull BOTH down and DELETE them from the box:
#     scp stratbot:~/stratbot-bootstrap-*.tgz stratbot:~/stratbot-hermes-*.tgz .
#     ssh stratbot 'shred -u ~/stratbot-bootstrap-*.tgz; rm -f ~/stratbot-hermes-*.tgz'
#
# The bootstrap tgz CONTAINS SECRETS (rclone token, ssh deploy keys, Telegram
# tokens, htpasswd, dashboard password inside unit env). Treat like a password.
# NEVER upload either file to Drive or commit it. Re-run when infra/secrets change.
set -uo pipefail
shopt -s nullglob

H=/home/kc-user
export PATH="$H/.local/bin:$PATH"   # so node/claude versions resolve for the MANIFEST
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
STAGE=$(mktemp -d)
OUT="$H/stratbot-bootstrap-$STAMP.tgz"
HERMES_OUT="$H/stratbot-hermes-$STAMP.tgz"
trap 'rm -rf "$STAGE"' EXIT
warn(){ printf '  !! %s\n' "$*"; }
need(){ [ -f "$1" ] || { echo "MISSING required file: $1 — aborting"; exit 1; }; }

mkdir -p "$STAGE"/{secrets,etc-systemd-system,user-systemd,bin,binary}

echo "== secrets =="
need "$H/.config/rclone/rclone.conf"; install -m600 "$H/.config/rclone/rclone.conf" "$STAGE/secrets/rclone.conf"
need "$H/.hermes/auth.json";         install -m600 "$H/.hermes/auth.json" "$STAGE/secrets/hermes-auth.json"
[ -f "$H/.config/signals-alert.env" ] && install -m600 "$H/.config/signals-alert.env" "$STAGE/secrets/signals-alert.env" || warn "no signals-alert.env"
for k in github_deploy github_deploy.pub github_lake_deploy github_lake_deploy.pub config known_hosts; do
  [ -f "$H/.ssh/$k" ] && install -m600 "$H/.ssh/$k" "$STAGE/secrets/ssh-$k" || warn "no ssh/$k"
done
sudo cat /etc/nginx/.htpasswd_lake > "$STAGE/secrets/htpasswd_lake" 2>/dev/null && chmod 600 "$STAGE/secrets/htpasswd_lake" || warn "no htpasswd_lake"

echo "== systemd units (system) + drop-ins (sudo — drop-ins may be root-only) =="
for u in /etc/systemd/system/cryptolake* /etc/systemd/system/stratbot-dashboard* \
         /etc/systemd/system/lake-snapshot* /etc/systemd/system/lake-backup* \
         /etc/systemd/system/reflect-daily* /etc/systemd/system/signals-monitor*; do
  sudo cp -a "$u" "$STAGE/etc-systemd-system/" || warn "copy $u"
done
sudo chown -R "$(id -u):$(id -g)" "$STAGE/etc-systemd-system"

echo "== systemd units (user) + drop-in dirs =="
for u in "$H/.config/systemd/user/"*.service "$H/.config/systemd/user/"*.timer "$H/.config/systemd/user/"*.d; do
  cp -a "$u" "$STAGE/user-systemd/" || warn "copy $u"
done

echo "== helper scripts (~/bin) — NOT lake_snapshot.sh (that's in the repo) =="
for f in "$H/bin/telegram-failure-alert.py" "$H/bin/consolidate_lake.py"; do
  [ -f "$f" ] && cp -a "$f" "$STAGE/bin/" || warn "no $(basename "$f")"
done

echo "== crypto-lake-rs release binary =="
need "$H/crypto-lake-rs/target/release/crypto-lake-rs"
cp -a "$H/crypto-lake-rs/target/release/crypto-lake-rs" "$STAGE/binary/"

echo "== MANIFEST =="
HVENV="$H/.hermes/hermes-agent/venv/bin/pip"
{
  echo "# stratbot bootstrap manifest — $STAMP"
  echo "host: $(hostname)   ubuntu: $(lsb_release -ds 2>/dev/null)   kernel: $(uname -r)"
  echo
  echo "## systemd enable-state (system)"
  for u in cryptolake cryptolake-failure stratbot-dashboard lake-snapshot.timer \
           lake-snapshot-failure reflect-daily.timer signals-monitor.timer; do
    echo "  $u = $(systemctl is-enabled "$u" 2>/dev/null)"
  done
  echo "  # lake-backup.timer = DEAD — do NOT enable"
  echo "## systemd enable-state (user)"
  for u in paper-trader hermes-gateway lake-consolidate.timer; do
    echo "  $u = $(systemctl --user is-enabled "$u" 2>/dev/null)"
  done
  echo
  echo "## repos (deploy keys are in secrets/; host aliases in ssh-config)"
  echo "  lewis-strat-trader: $(cd "$H/lewis-strat-trader" && git remote get-url origin 2>/dev/null)  HEAD $(cd "$H/lewis-strat-trader" && git rev-parse --short HEAD 2>/dev/null)"
  echo "  crypto-lake-rs:     $(cd "$H/crypto-lake-rs" && git remote get-url origin 2>/dev/null)"
  echo
  echo "## hermes agent — shipped whole in stratbot-hermes-$STAMP.tgz (restore extracts it)."
  echo "   Fallback reinstall recipe if that tarball is lost:"
  echo "     node prefix: ~/.hermes/node   node: $(node --version 2>/dev/null)"
  echo "     claude-code: npm i -g @anthropic-ai/claude-code  (installed: $(claude --version 2>/dev/null))"
  echo "     hermes pkg:  $(grep -iE '^(Name|Version):' "$H/.hermes/hermes-agent/hermes_agent.egg-info/PKG-INFO" 2>/dev/null | tr '\n' ' ')"
  echo "     hermes svc:  $(grep -h ExecStart "$H/.config/systemd/user/hermes-gateway.service" 2>/dev/null | sed 's/^/       /')"
  echo
  echo "## env vars set in unit drop-ins (values captured inside the copied units):"
  echo "   LAKE_ROOT, DASHBOARD_ADMIN_PASSWORD (in stratbot-dashboard drop-in)"
  echo
  echo "## drive backup layout (restore pulls the newest of each)"
  echo "   gdrive:crypto-lake-snapshots/{stratbot-state,crypto-lake,crypto-raw}-<date>.tar"
} > "$STAGE/MANIFEST.txt"

tar czf "$OUT" -C "$STAGE" .
chmod 600 "$OUT"

echo "== hermes runtime tarball (excludes Drive-backed state + caches + docs) =="
tar czf "$HERMES_OUT" -C "$H" \
  --exclude='.hermes/memories'          --exclude='.hermes/cron' \
  --exclude='.hermes/state.db*'         --exclude='.hermes/gateway_state.json' \
  --exclude='.hermes/.hermes_history'   --exclude='.hermes/auth.json' \
  --exclude='.hermes/sessions'          --exclude='.hermes/pastes' \
  --exclude='.hermes/logs'              --exclude='.hermes/cache' \
  --exclude='.hermes/*_cache.json'      --exclude='*/__pycache__' \
  --exclude='.hermes/hermes-agent/website' --exclude='.hermes/hermes-agent/.git' \
  .hermes 2>/dev/null || warn "hermes tar had read warnings (usually fine)"
chmod 600 "$HERMES_OUT"

echo
echo "=== bundles written ==="
echo "  $OUT        ($(du -h "$OUT" | cut -f1))  — secrets+infra, password-manager it"
echo "  $HERMES_OUT ($(du -h "$HERMES_OUT" | cut -f1))  — hermes runtime, store on disk"
echo "bootstrap contents (names only):"; tar tzf "$OUT" | sed 's/^/  /'
echo
echo "NEXT (do NOT skip):"
echo "  1. scp stratbot:$OUT stratbot:$HERMES_OUT ."
echo "  2. store the bootstrap tgz in your password manager; keep the hermes tgz on safe disk"
echo "  3. ssh stratbot 'shred -u $OUT; rm -f $HERMES_OUT'"
