# Subsystem: Backups

Automated, online-safe, verified, self-pruning backups of the SQLite database.

**Source**: `backend/services/backup_svc.py`
**DB path**: `backend/data/finhub.db` (from `DB_PATH`, default `<backend>/data/finhub.db`)

## Why backups matter

The database is a single SQLite file. One-file corruption = total loss of all
profiles, transactions, schedules, and snapshots. The DB runs in rollback-journal
mode (`PRAGMA journal_mode` = `delete`), so a plain file `cp` during a write is
**not safe** — it can produce a corrupt copy. Backups therefore use the stdlib
`sqlite3.Connection.backup()` API, which produces a consistent snapshot even
while the app holds the DB open and writes are in flight.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BACKUP_ENABLED` | `1` | `0` disables all backup activity (startup, scheduler, migrations) |
| `BACKUP_DIR` | `<db dir>/backups` | Where `.bak` files are stored |
| `BACKUP_TIMEZONE` | container local timezone | IANA name (e.g. `Asia/Tokyo`) for the daily cutover. If unset or invalid, falls back to `TZ`, then the container local timezone — never a startup error. |

**Timezone resolution** (never raises): `BACKUP_TIMEZONE` (valid IANA) → `TZ` (valid IANA) → container local timezone. `docker-compose.yml` / `docker-compose.prod.yml` mount the host's `/etc/localtime` and `/etc/timezone` into the backend read-only. On **Linux hosts** the container local timezone is therefore the host timezone and no env is needed. On **Docker Desktop (macOS/Windows)** the VM is UTC, so the mounts are a harmless no-op — set `BACKUP_TIMEZONE` (or the standard `TZ`) to the desired IANA name. The backend image installs `tzdata`, so any IANA name resolves even in the slim image.
| `BACKUP_CRON` | `03:00` | Daily backup time as `HH:MM` in `BACKUP_TIMEZONE` |
| `BACKUP_RETENTION` | `7` | Number of newest backups kept; older ones are pruned after each backup |

Backup files are named `finhub.db-YYYYMMDD-HHMMSS.bak` and created with mode
`0600` (owner-only).

## How the daily backup works

- On startup, **before migrations run**, `startup_daily_backup()` checks
  `is_daily_due(now)`: past the daily cutover (from `BACKUP_CRON` +
  `BACKUP_TIMEZONE`) **and** no backup exists for the current day → a
  `daily-catchup` backup is created. This captures the pre-migration state.
- A scheduler job (`backup_daily`, registered in `init_scheduler()`) runs the
  catch-up/refresh at `BACKUP_CRON` each day using APScheduler's `CronTrigger`
  with `misfire_grace_time=3600`.
- Each backup is **verified**: `PRAGMA integrity_check` plus row-count sanity
  on `profiles`, `entities`, and `transactions`. An unreadable/empty/garbage
  file fails verification and is deleted.
- After a successful backup, `prune_backups()` deletes the oldest files beyond
  `BACKUP_RETENTION`.

## Migration backups

If `init_db()` reports that migrations were **applied to an existing DB** (not a
fresh install), `migration_backups()` guarantees exactly **two** backups around
them:

1. **Pre-migration** — reused from the daily catch-up when it already ran this
   boot; otherwise created just before migrations apply.
2. **Post-migration** — created immediately after migrations complete.

Fresh installs and no-op boots (nothing applied) are skipped. This ensures a
restore point exists on either side of any schema change.

## Lifecycle order (`backend/main.py` lifespan)

1. `startup_daily_backup()` — daily catch-up (pre-migration state)
2. `init_db()` → returns `(fresh, applied)`
3. `migration_backups(fresh, applied, daily_ran)` — pre + post when needed
4. `seed_currencies`, `seed_default_profile`
5. `catch_up_missed_fires()`, `init_scheduler()` (registers `backup_daily`)

## Observability

- Every backup logs start and result (filename, size, duration, prune outcome)
  as structured JSON.
- `GET /api/v1/health` reports `checks.backup` as one of:
  `ok` (current day's backup exists) / `stale` (daily due, backup missing) /
  `never` (no backups yet) / `disabled` (`BACKUP_ENABLED=0`). Informational
  only — it never affects the overall health status or exposes paths.

## Operations (CLI)

Run from `backend/` (or via Make targets at the repo root).

```sh
make backup                    # create + verify + prune now
make restore BACKUP=<file>     # restore from a specific .bak file
make restore                   # restore from the newest backup
```

Equivalent direct commands:

```sh
cd backend && uv run python -m scripts.backup [--tag NAME]
cd backend && uv run python -m scripts.restore [BACKUP_PATH] [--force]
```

### Restore guardrails

- **Refuses while the backend is running**: `scripts/restore.py` first checks
  `http://localhost:8000/api/v1/health`. If reachable, restore aborts unless
  `--force` is passed (single-writer safety — restoring under a live app would
  corrupt the running instance's view).
- **Never destroys the current state**: the existing DB is preserved as
  `finhub.db.pre-restore-<timestamp>` before the backup file replaces it.
- The restored file passes the same `verify_backup()` checks.

### Typical restore procedure

1. Stop the backend.
2. `make restore BACKUP=backend/data/backups/finhub.db-YYYYMMDD-HHMMSS.bak`
3. Start the backend; confirm `/api/v1/health` shows `"database": "ok"`.

## Out of scope

- **Cloud / off-site sync** — planned as a follow-up item; backups are local.
- **Encryption at rest** — backups inherit the host file permissions (0600).
- **Corruption alarm** — periodic integrity monitoring is a separate feature.
