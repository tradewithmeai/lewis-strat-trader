# VPS full migration plan — lock, stock, the whole lot (2026-07-17)

Migrate **everything** off the current VPS (`stratbot`, 185.44.253.199, Ubuntu
24.04.4, 2 vCPU / 5.7G RAM / 96G disk, 34G used) to a new box: the crypto lake
with all files, the Hermes agent ("Darren") with all its state, the live
dashboard + paper race, all timers, nginx/TLS, and the secrets that glue it
together. Grounded in a live inventory taken 2026-07-17 (all services healthy,
repo synced at `8085d5d`), then hardened by a three-lens adversarial review
(data integrity / cutover ordering / completeness+secrets — 34 findings folded
in below).

**Guiding rules** (learned the hard way, recorded in the worklog):
- **Copy bytes, never process during transfer.** tar/rsync raw files; no
  consolidation, no decoding, no "tidy while we move". This includes the
  target: **no consolidation runs on transferred data until it has been
  checksum-verified** against the source.
- **Detach every long transfer** — `systemd-run`/`nohup` on the box, never tied
  to an interactive SSH session — and **gate on its logged exit status**, never
  on "it looks done".
- **One writer per state file, ever.** The paper-trader, the Hermes gateway
  (Telegram bot), and the dream cron each run on exactly one box at any moment
  — enforced by **disabling** (not just stopping) units, because a reboot of a
  "stopped" box with enabled units + linger silently resurrects every writer.
- **Old box stays intact and deliberately re-startable until soak completes.**
  Rollback is a written runbook (§9), not an improvisation.
- Steps needing Captain's accounts (registrar, provider console, Google,
  Anthropic) are tagged **[CAPTAIN]** and collected in §11.

---

## 0. Bill of materials (what exists — the transfer checklist)

### Services (systemd, no crontabs anywhere)
| Unit | Level | Role |
|---|---|---|
| `cryptolake.service` | system | crypto-lake-rs collector + lake API :8000 (`target/release/crypto-lake-rs --config config.yml --no-tray --retention-days 0`, WorkingDirectory `~/crypto-lake-rs`) |
| `cryptolake-failure.service` | system | alert notifier hook (ExecStart/token → Phase-0 sweep) |
| `stratbot-dashboard.service` | system | Streamlit on 127.0.0.1:8501 from repo `.venv` |
| `lake-snapshot.service` + `.timer` | system | daily 04:00 gdrive tarball via `/home/kc-user/lake_snapshot.sh` (rclone). **Canonical backup.** As of 2026-07-17 it uploads TWO dated tarballs to `gdrive:crypto-lake-snapshots`: `crypto-lake-*.tar` (parquet, 14-day retention) + `stratbot-state-*.tar` (repo `state/` race record + `~/.hermes` memories/cron/state.db, 60-day retention; excludes `auth.json` + `data/raw`). Script now version-controlled at `scripts/lake_snapshot.sh` |
| `lake-snapshot-failure.service` | system | alert hook |
| `lake-backup.service` + `.timer` | system | **DEAD — do not migrate/enable.** Confirmed 2026-07-17: disabled + inactive, last ran ~2026-06-12, only 78.8 MiB partial (superseded first attempt). `gdrive:crypto-lake` is its stale stub |
| `reflect-daily.service` + `.timer` | system | nightly walk-forward reflect 00:20 (can run long on 2 vCPU) |
| `signals-monitor.service` + `.timer` (+ `-failure`, `-failure@`) | system | 04:15 signals run |
| `paper-trader.service` | **user** | the live $1,000 race engine — sole writer of `state/paper_accounts.json`, `equity_history.jsonl`, `status.json` |
| `hermes-gateway.service` | **user** | Darren: Telegram gateway + internal cron (05:00 UTC dream in `~/.hermes/cron/jobs.json`) |
| `lake-consolidate.service` + `.timer` | **user** | 00:10 daily partition consolidation (memory-capped duckdb) — **special handling, §5/§6** |
| linger | — | `loginctl enable-linger kc-user` |

**Phase-0 unit sweep (mandatory):** for every unit above run `systemctl cat
<unit>` and record every `ExecStart=`, `OnFailure=`, `Environment=`,
`EnvironmentFile=` — each referenced script (e.g. notifier scripts under
`/usr/local/bin`), env file, and embedded token joins this bill. Also sweep
non-stock `/etc`: `systemd-delta` + `ls /etc/systemd/system/*.d/` (MemoryMax
caps may live in **drop-ins**, not unit files — they must move), `/etc/sysctl.d`,
`/etc/logrotate.d`, `/etc/security/limits.d`, `/etc/apt/apt.conf.d`
(unattended-upgrades — note: its auto-reboot setting is one of the reasons §6
disables old-box units), `/etc/systemd/journald.conf`.

**Phase-0 env sweep (mandatory):** `VPS_SETUP.md` documents `OPENAI_API_KEY`
and `LAKE_ROOT` as load-bearing (LAKE_ROOT required at import by the strategy
stack; OPENAI_API_KEY by the LLM stance layer). Locate every source —
`systemctl show -p Environment -p EnvironmentFile <unit>` (system and user),
`systemctl --user show-environment`, `~/.profile`/`~/.bashrc` — and add each
env file/key to the secrets list below. Nothing starts on the new box until
these resolve.

### Data (the transfer bill)
| What | Size / count (2026-07-17) | Method |
|---|---|---|
| `~/crypto-lake-rs/data/parquet` | 4.1G, **111,927 files** | tar-over-ssh bulk, rsync delta, full checksum verify (§5, §8) |
| `~/crypto-lake-rs/data/raw` | 5.2G (zstd) | same |
| `~/lewis-strat-trader/state/` runtime files (gitignored: `paper_accounts.json`, `equity_history.jsonl`, `status.json`, `submissions.jsonl`, `community_strategies.json`, `state/signals/`, `state/lake_rollup/`) | small | freeze-window copy with fingerprint verify (§6.3) |
| `~/.hermes` state subset (§4.4) | of 3.5G, ~100s MB matters | fresh install + `rsync -a` state copy |
| `~/.claude` minus credentials | 7.3M | `rsync -a --exclude='.credentials.json' ~/.claude/ newbox:~/.claude/` — the exclude is **mandatory**; verify on the new box `test ! -f ~/.claude/.credentials.json` **before** Captain logs in |
| Git repos | — | **clone fresh** (deploy keys); then `cp scripts/post-commit .git/hooks/post-commit` (the worklog-spine hook does not travel with a clone) |
| Python venvs | ~GBs | **rebuild** from `pip freeze` manifests, never copy |
| `crypto-lake-rs` binary + `config.yml` | in 587M `target/` | copy the one release binary (same OS/arch); repo cloned for future rebuilds — **note: no Rust toolchain is installed by this plan; a future rebuild requires `rustup` first** (deliberate deferral) |

### Secrets that must move (each travels exactly once, direct box-to-box)
| # | File | Destination, owner, mode |
|---|---|---|
| 1 | `~/.config/rclone/rclone.conf` | kc-user, 600 |
| 2 | `/etc/nginx/.htpasswd_lake` | `sudo install -o root -g www-data -m 640` — **not** 600 (nginx workers run as www-data and read it at request time; 600 root = 500s on lake.solvx.uk) |
| 3 | `~/.hermes/auth.json` (Hermes provider keys / Telegram bot token) | kc-user, 600 — travels **only** here, not again in the §4.4 state copy |
| 4 | `~/.ssh/github_deploy` + `github_lake_deploy` (+ `.pub`s) | kc-user, 600 |
| 5 | `~/.ssh/config` (per-repo host aliases for the two deploy keys) + `authorized_keys` | kc-user, 600 |
| 6 | Any env files found by the Phase-0 env sweep (OPENAI_API_KEY etc.) | kc-user, 600 |
| — | `~/.hermes/state.db*` (full chat history — sensitive) | rides in §4.4 state copy; owner-only, direct box-to-box, never staged through a third host |

Do **not** copy:
- `~/.claude/.credentials.json` — **[CAPTAIN] re-runs `claude auth login` on the
  new box**; verify `claude auth status` → `subscriptionType: "max"`. Enforced
  by the `--exclude` + `test ! -f` steps above, not by hoping.
- Certbot certs/keys — re-issued on the new box (§6.6).

### Network / edge
- nginx sites: `stratbot` (→ :8501), `lake` (basic-auth → :8000), `default`.
- Certs: `stratbot.solvx.uk`, `lake.solvx.uk` (current ones valid to ~Sep 9-10).
- DNS: both A records → 185.44.253.199. **[CAPTAIN]** controls registrar.
- UFW: OpenSSH + Nginx Full. sshd: key-only.
- **Verify (don't assume) both GitHub deploy keys are read-only**: repo
  Settings → Deploy keys shows "Read-only", and from the new box
  `git push --dry-run` must be rejected. Record in worklog. (An autonomous
  agent runs on this box; a silently push-capable key is not acceptable.)

---

## 1. Target spec — [CAPTAIN] decision

- Ubuntu 24.04 LTS x86_64 (binary-compatible → the rust binary copies over).
- **RAM 8–16G strongly recommended** (5.7G OOM-killed duckdb consolidations
  twice; keep the MemoryMax caps regardless). 4 vCPU nice-to-have.
- Disk ≥ 100G (34G used; lake grows ~1.5-2G/month). 4G swapfile.
- EU region (exchange-websocket latency parity).

## 2. Phase 0 — pre-flight (old box live, zero risk)

1. Everything committed & pushed (done 2026-07-17 at `8085d5d`) — repeat on
   migration day.
2. Trigger a manual `lake-snapshot` → confirm SUCCESS + tarball in gdrive
   (offsite restore point independent of the migration).
3. Run the **unit sweep**, **/etc sweep**, and **env sweep** from §0; commit the
   manifests (`pip freeze` × both venvs, unit list + drop-ins, file count + du
   -sb per data dir, current DNS TTLs) to the repo.
4. `lake-backup` vs `lake-snapshot` — **resolved 2026-07-17**: `lake-snapshot`
   is canonical (now covers lake + state); `lake-backup` is dead (do not
   migrate or enable it). No further action beyond not carrying it forward.
5. **[CAPTAIN]** Provision target (§1 spec); add Captain's SSH key; create the
   `ssh stratbot-new` alias in Windows `~/.ssh/config` (old alias keeps
   pointing at the old box **until §8 step 3** — every runbook line below says
   which box it runs on).
6. **[CAPTAIN]** Record current TTL of both A records, then lower to 300s **at
   least 24–48h before the cutover window** (resolvers that cached under the
   old TTL honour it until it expires — lowering on the morning is too late).
   This is a hard precondition of Phase 4.
7. Establish transfer trust: generate an ephemeral keypair on the **old** box,
   append its `.pub` to the **new** box's `authorized_keys` (with a `from=`
   old-box-IP restriction). All bulk/delta transfers below run over this.
   (Removed in §8.)

## 3. Phase 1 — base provisioning (new box)

1. Create `kc-user`; passwordless sudo for service restarts (as today); sshd
   `PasswordAuthentication no`; UFW allow OpenSSH + Nginx Full; 4G swapfile;
   `loginctl enable-linger kc-user`.
2. `timedatectl` must show "System clock synchronized: yes", and `date -u`
   agrees with the old box to ~1s (clock skew misnames partition files at the
   freeze boundary and breaks mtime-based deltas).
3. Packages: `nginx certbot python3-certbot-nginx python3.12-venv git rclone
   build-essential`. Node prefix-install under `~/.hermes/node` (as today) +
   `npm install -g @anthropic-ai/claude-code`.
4. Pre-seed GitHub: `ssh-keyscan github.com >> ~/.ssh/known_hosts`, verify the
   fingerprint against GitHub's published keys (fresh box + deploy keys +
   missing known_hosts = interactive prompt that breaks unattended fetches).
5. Copy the §0 secrets (each exactly once, exact owner/mode from the table).
6. **Disk/inode preflight**: `df -h` + `df -i` on the filesystem holding
   `/home/kc-user` — require ≥3× the 9.3G payload free and ≥500k free inodes.
   (Re-checked again before the Phase-4 final delta.)

## 4. Phase 2 — code + config (idempotent, no cutover pressure)

1. Clone both repos via their deploy-key aliases; install the post-commit hook
   (`cp scripts/post-commit .git/hooks/post-commit`); run the deploy-key
   read-only verification from §0.
2. Rebuild repo `.venv` from the pip-freeze manifest; smoke:
   `.venv/bin/python -m py_compile dashboard.py`.
3. Copy the crypto-lake-rs release binary + `config.yml`.
4. **Hermes: fresh install, then state copy.** Install source: the same
   hermes-agent distribution/version the old box runs — **record the source URL
   + version in Phase 0** (it is not one of our two repos; "run the setup
   script" must name where the script comes from). Then `rsync -a` (perms
   preserved) the state subset only: `cron/jobs.json` + `cron/output/`,
   `memories/`, custom `skills/`, `state.db*`, `gateway_state.json`,
   `.hermes_history`, `pastes/`. (`auth.json` already arrived via §3.5.)
   Never copy the hermes venv or node dir — paths are embedded.
5. Copy all §0 units **and their drop-in dirs** (`/etc/systemd/system/*.d/`),
   `lake_snapshot.sh`, notifier scripts + env files found in the Phase-0 sweep;
   fix absolute paths if home differs; `systemctl daemon-reload`.
   **Enable nothing yet.**
6. nginx: copy the 3 site files, then **strip/comment the certbot-managed 443
   blocks** (they reference `/etc/letsencrypt/live/...` paths that don't exist
   here yet — verbatim copies fail `nginx -t` and would be discovered
   mid-cutover). Gate: `nginx -t` passes, nginx serves :80.
7. **[CAPTAIN]** `claude auth login` (after the §0 `test ! -f
   .credentials.json` check) → `claude auth status` shows `max`.
8. **[CAPTAIN if re-auth needed]** `rclone lsd gdrive:` works from the new box
   (Google may balk at a new IP → `rclone config reconnect gdrive:`).
9. **TLS pre-issue (preferred path):** issue both certs **before** the DNS flip
   via DNS-01 (`certbot --preferred-challenges dns` + manual TXT records at the
   registrar — **[CAPTAIN]**). The new box then serves valid HTTPS the instant
   DNS flips, and §6.6's HTTP-01-after-flip becomes the fallback, not the plan.

## 5. Phase 3 — bulk data transfer (old box still live and collecting)

0. Preflight re-check on target (disk/inodes, §3.6).
1. Bulk pass, **detached on the old box**, with real error handling:

```bash
systemd-run --user --unit=lake-xfer bash -c '
  set -o pipefail
  cd /home/kc-user/crypto-lake-rs
  tar cf - data/parquet data/raw | ssh newbox "cd /home/kc-user/crypto-lake-rs && tar xf -"
  rc=$?
  echo "XFER_EXIT=$rc $(date -u +%FT%TZ)" >> /home/kc-user/lake_xfer.log
'
```

   Gate: `lake_xfer.log` shows `XFER_EXIT=0` (a live collector makes benign
   "file changed as we read it" warnings possible on the *current* day's files
   — those are healed by the delta; any other tar error is a stop). Do not
   start the delta until the gate passes.
2. **Immediately after the bulk pass: stop + disable the old box's
   `lake-consolidate.timer`.** Consolidation rewrites day-partitions (merges
   small files, deletes originals); if it runs between bulk and cutover, the
   delta rsync (which does not `--delete`) leaves the target holding **both**
   the stale small files and the merged ones — the same bars twice. Skipping
   consolidation for a few days is harmless.
3. First delta while still live: `rsync -a --partial --delete
   data/parquet/ newbox:.../data/parquet/` (ditto `raw`). `--delete` is
   **mandatory** on every delta pass for the same reason as step 2.
4. Coarse verify (fast, catches gross loss — the *real* verify is §8.2):
   file count per top-level dir and `du -sb` (apparent size — `du -s` block
   counts differ across filesystems on identical data) old vs new.

## 6. Phase 4 — cutover (freeze window ~30-60 min, target ~09:00 UTC)

**Entry gates (all must pass before step 1):**
- DNS TTL lowered ≥24h ago (§2.6); disk preflight green (§5.0); §4 complete
  including `nginx -t` and TLS pre-issue; Darren pre-briefed that this window
  is a no-work freeze **[CAPTAIN sends the note]**.
- **No in-flight jobs on the old box** — stopping a `.timer` does not stop a
  running `.service`, and reflect/dream can run long on 2 vCPU:
  `systemctl is-active reflect-daily signals-monitor lake-snapshot
  lake-backup lake-consolidate` all `inactive`, and hermes has no running
  dream child (process tree + `cron/output/` mtime). If anything is active,
  wait — do not start the freeze.

**Steps (each verified before the next):**

1. **Old box — stop AND disable the writers** (disable matters: linger +
   enabled units means a provider reboot during soak resurrects a second
   paper-trader, Telegram gateway, dream cron, and snapshot job):
   - Send a maintenance notice via the gateway first, then
     `systemctl --user stop paper-trader hermes-gateway && systemctl --user
     disable paper-trader hermes-gateway lake-consolidate.timer`
   - `sudo systemctl stop reflect-daily.timer signals-monitor.timer
     lake-snapshot.timer lake-backup.timer && sudo systemctl disable <same>`
   - Verify hermes exited cleanly before its state is copied (torn sqlite is
     forever); prefer `sqlite3 state.db ".backup"` on the stopped DB.
   - Fingerprint the race state **now**: `python -m json.tool
     state/paper_accounts.json > /dev/null` (torn-JSON check), record sha256 of
     `paper_accounts.json` + `status.json`, and line count + last line of
     `equity_history.jsonl` into the worklog. This is the freeze-point
     fingerprint the new box must match.
2. **Old box — stop + disable the collector**: `sudo systemctl stop cryptolake
   && sudo systemctl disable cryptolake`. Record the timestamp (lake gap
   starts). Check `journalctl -u cryptolake` for a clean exit (no SIGKILL) and
   `zstd -t` the current day's raw file — a torn final file must not enter the
   delta.
3. **Final delta** (minutes): rsync `--delete` parquet + raw; copy
   `lewis-strat-trader/state/`; rsync the §4.4 hermes state delta. Verify the
   race-state fingerprint on the new box (sha256 + line count match step 1)
   **before anything starts**.
4. **New box — start in dependency order, verifying each**:
   a. `sudo systemctl enable --now cryptolake` → journal shows "Wrote N bars",
      new parquet files appear. **Lake gap ends** (target < 15 min).
      **Timebox: if not writing within ~10 min, re-enable + restart the old
      collector** (collector overlap is safe — public read-only feeds) and
      debug without data loss; redo steps 2–3 later.
      Then assert the boundary: query the lake API for the freeze window per
      exchange/symbol — each bar timestamp appears **exactly once** (gap extent
      recorded in the worklog; no overlap duplicates).
   b. `systemctl --user enable --now paper-trader` → `status.json` ticks,
      `equity_history.jsonl` first new line **continues** from the recorded
      last line (same account equities, no reset — the forward record since
      27 Jun must survive unbroken).
   c. `systemctl --user enable --now hermes-gateway` → Telegram responds,
      `cron/jobs.json` shows the 05:00 dream.
   d. Enable the **enumerated** timers: `reflect-daily.timer
      signals-monitor.timer lake-snapshot.timer` (+ `lake-backup.timer` only
      if §2.4 ruled it canonical). **`lake-consolidate.timer` stays disabled**
      until the §8.2 checksum verify passes — consolidating unverified
      transferred data is processing-during-transfer by another name, and it
      destroys both the checksum comparison and the rollback path.
   e. `sudo systemctl enable --now stratbot-dashboard`.
5. **[CAPTAIN] DNS flip** both A records → new IP. Check against the
   authoritative NS (`dig @<ns> stratbot.solvx.uk`), not the local cache.
6. **TLS**: already live if §4.9 pre-issued (preferred). Fallback: HTTP-01
   `certbot --nginx` per domain once authoritative DNS answers new-IP (LE
   queries authoritative servers, so stale resolver caches don't block
   issuance).
7. **Edge verify**: `https://stratbot.solvx.uk` 200 with fresh `updated`
   timestamp; `https://lake.solvx.uk` 401 → 200 with htpasswd creds.
8. **Propagation honesty**: stale-resolver clients hitting the old box get a
   working HTTPS handshake but: stratbot = stale (frozen) dashboard, lake =
   **502** (its :8000 backend is stopped). Accepted for the ≤TTL window; once
   authoritative propagation is confirmed, `sudo systemctl stop
   stratbot-dashboard nginx && sudo systemctl disable stratbot-dashboard` on
   the old box (nothing user-facing remains there).

## 7. Phase 5 — post-cutover verification (same evidence bar as the Jul 17 sweep)

- All units `active` + `enabled`; `systemctl list-timers` shows the enumerated
  set with sane next-elapse; linger on.
- Lake: files written in the last 10 min; API :8000 = 200; boundary-window
  dedup assertion from §6.4a recorded.
- Board: standings equal the freeze fingerprint ± live moves; "trading live
  since 27 Jun" day count unbroken.
- Manual `lake-snapshot` run → SUCCESS → tarball in gdrive.
- **Test-fire the failure alerts**: `sudo systemctl start
  cryptolake-failure.service` (and one of each `-failure` flavour) → the alert
  actually arrives in its channel. A soak with silent-failure monitoring is
  not a soak. **[CAPTAIN]** also points an external uptime check (any free
  monitor) at `https://stratbot.solvx.uk` for the soak week — the box can't
  report its own total death.
- Next 05:00 UTC: Darren's dream fires from the new box, report lands in
  Telegram, artifacts in the repo checkout; `claude auth status` = max and the
  REPL smoke-runs inside Darren's window.

## 8. Phase 6 — soak (7 days), full verify, decommission

1. Soak: old box **stopped + disabled but intact**. Set a hostile MOTD on it
   ("DECOMMISSIONING — do not start services").
2. **Full-content verify (the real one — gates decommission):** the frozen set
   is now immutable on both sides, so run detached on each box: xxh128/sha256
   manifest over `data/parquet` + `data/raw` restricted to files present at
   freeze; diff the manifests (or `rsync -rcn --itemize-changes old→new`
   expecting zero lines). Count/du checks (§5.4) do not catch truncation or
   bit-flips; this does. **Only after it passes:** enable
   `lake-consolidate.timer` on the new box and log the enable time.
3. Repoint the Windows `ssh stratbot` alias to the new IP **now** (not at
   decommission) and rename the old entry `stratbot-old` — every runbook and
   muscle-memory session must land on the new box during soak, not the old
   one. Remove the ephemeral transfer key from the new box's authorized_keys.
4. After soak: final archival `lake-snapshot` from the old box **[CAPTAIN]**,
   download a local copy of the gdrive archive, then destroy the old VPS
   **[CAPTAIN]**. Raise DNS TTL back to 3600 **[CAPTAIN]**. Update
   `docs/VPS_SETUP.md` + memory notes with the new IP; remove the old host key
   from `known_hosts`.

## 9. Rollback runbook (mirror of §6, pre-written — not improvised)

**Triggers (any one):** race-state corruption (fingerprint mismatch/torn JSON);
lake gap or dedup-assert failure > 2h unresolved; recurring OOM kills; dream
cron fails 2 consecutive days; §8.2 checksum verify fails irrecoverably.

1. **New box — stop AND disable all writers** (paper-trader, hermes-gateway,
   cryptolake, all timers). Verify stopped. Same discipline as §6.1-6.2 —
   rollback must not create the dual-writer state either.
2. **Reverse delta, scoped to post-freeze artifacts only** — never let the
   possibly-faulty new box overwrite pristine pre-freeze data on the old box:
   rsync the parquet + raw partitions **created after the freeze timestamp**,
   `lewis-strat-trader/state/`, and the full §4.4 hermes state set (state.db*,
   cron/, gateway_state.json, memories/ — Darren's soak-week memory is part of
   the record), using the freeze timestamp / `--ignore-existing` as the guard.
3. Old box: re-enable + start in §6.4 dependency order (collector → verify →
   paper-trader → fingerprint-continuity check → hermes → timers → dashboard
   + nginx).
4. **[CAPTAIN]** flip DNS back (TTL still 300).
5. Keep the new box stopped + disabled for post-mortem; do not destroy it.

## 10. Risk register

| Risk | Mitigation |
|---|---|
| Undersized RAM again (OOM-killed consolidations ×2) | 8–16G target; MemoryMax caps + their drop-ins explicitly copied (§0 sweep) |
| 112k small files: rsync crawl / silent truncation | tar-stream bulk with pipefail+exit gate; `--delete` deltas; §8.2 full checksum before decommission |
| Duplicated bars from consolidation racing the transfer | old consolidate timer disabled right after bulk (§5.2); new one disabled until checksum verify (§6.4d) |
| Two paper-traders / gateways / dream crons | stop **and disable** on old box; enumerated enables on new; reboot-safe on both sides; rollback preserves the same guarantee |
| Old box reboots mid-soak (provider/unattended-upgrades) | everything disabled + MOTD guard; re-enable commands live only in §9 |
| Lake gap at cutover | sequential handover < 15 min target, 10-min timebox with restart-old-collector fallback, boundary dedup assertion, gap logged |
| Race state torn at freeze | JSON validate + sha256/line-count fingerprint before and after copy, continuity assert before the new trader starts |
| nginx fails on copied certbot configs | 443 blocks stripped + `nginx -t` gated in Phase 2, certs pre-issued DNS-01 |
| DNS TTL trap | TTL recorded + lowered ≥24h ahead; authoritative-NS checks, not resolver cache |
| rclone/gdrive or Claude auth surprises | both verified in Phase 2, before anything depends on them; both tagged [CAPTAIN] |
| Transfer dies mid-stream (has lost a day before) | detached systemd-run with logged exit sentinel; resumable `--partial` deltas; explicit gates |
| Alerting silently dead on new box | test-fired in Phase 5 + external uptime check during soak |
| Hermes venv path rot / unknown installer | fresh install from a source+version recorded in Phase 0; state-only rsync |
| Muscle-memory `ssh stratbot` lands on old box mid-soak | alias repointed at Phase-5 pass; old renamed `stratbot-old`; hostile MOTD |

## 11. [CAPTAIN] checklist (every human-account step, in order)

| Phase | Step |
|---|---|
| 0 | Provision target box (§1 spec); add SSH key |
| 0 | Record + lower DNS TTLs to 300 (≥24–48h before cutover) |
| 2 | `claude auth login` on new box (after the no-credentials check) → verify `max` |
| 2 | rclone gdrive re-auth if Google balks at the new IP |
| 2 | DNS-01 TXT records at registrar for cert pre-issue |
| 4 | Pre-brief Darren: cutover window is a no-work freeze |
| 4 | DNS flip both A records |
| 5 | Point an external uptime monitor at stratbot.solvx.uk for the soak |
| 6 | Final archival snapshot, download archive copy, destroy old VPS, raise TTL |

## 12. Open decisions

1. **Target provider/spec** (§1 — the 8-16G RAM recommendation).
2. **Migration window date** (~09:00-11:00 UTC weekday; entry gates in §6).
3. ~~`lake-backup` vs `lake-snapshot`~~ — **resolved** (see §2.4): snapshot
   canonical + now covers state, lake-backup dead.
4. Whether to keep the old box a full billing cycle as cold standby (§9.5
   argues yes — it is the rollback target and the post-mortem evidence).
