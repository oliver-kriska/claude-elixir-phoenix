# ADR-018: One release in the same image contract; operator scripts, hooks, env and logs kept

**Status**: ASSUMED (auto; needs approval). Operational changes DV-07.
**Date**: 2026-10-09 · **Bar**: ADR-000 C-47, C-50..C-58, C-60

## Context

- Today: `bin/boot` (Ruby PID 1) runs `thrust bin/start-app`, `redis-server` and `resque-pool`, and kills all when any exits (R-01, M-55). `bin/start-app` runs `db:prepare` on every boot (R-03). Puma sizing knobs, SIGPROF thread dumps (R-04, R-06).
- Operator contract: image name and tags, uid/gid 1000, ports 80/443, `/rails/storage`, `/hooks/pre-backup` and `/hooks/post-restore`, `script/admin/*` paths, arguments, output and exit codes, env var names, `GET /up`, STDOUT logs with bot-key scrubbing, Sentry switches, optional `config/purchased_by.yml` (C-47, C-50..C-58, M-53, M-57..M-59).

## Decision

- **Image**: multi-stage `mix release` Dockerfile, `linux/amd64` + `linux/arm64`, same names and tag scheme (`X.Y.Z`, `X.Y`, `X`, `latest`, `main`), `USER 1000:1000`, `WORKDIR /rails`, `EXPOSE 80 443`, `VOLUME /rails/storage`. Process tree: `tini` (PID 1) → `thrust` (ADR-019) → `bin/campfire start`. `bin/boot`, Redis and resque-pool are deleted.
- **Boot**: `Campfire.Storage.ensure_dirs!/0` (`storage/db`, `storage/files`, `storage/backups`) then the supervision tree with `BootMigrator` (ADR-004). A fatal error exceeds the top-level restart intensity, the VM halts and the container exits (parity with `bin/boot`).
- **Admin scripts**: `/rails/script/admin/{prepare-backup,reset-password,generate-secrets,create-vapid-key}` stay as shell wrappers. DB-touching ones call `bin/campfire rpc` so writes go through the live writer; if the node is down they fall back to `bin/campfire eval` (no second writer can exist then). Output text and exit codes match C-54 (`User not found`, exit 255).
- **Backups**: `prepare-backup` runs `VACUUM INTO '/rails/storage/backups/production.sqlite3.tmp'` on the writer, then renames. Hooks keep their paths and semantics; `post-restore` stays a shell script (app stopped).
- **Env**: `runtime.exs` reads the same names. `REDIS_URL`, `WEB_CONCURRENCY`, `RAILS_MAX_THREADS`, `RAILS_MIN_THREADS`, `PIDFILE` are accepted and ignored with one boot log line. `JOB_CONCURRENCY` sets the `webhooks` queue limit (ADR-006). `PORT` = Bandit's loopback port. `RAILS_LOG_LEVEL` maps to Logger level. `RAILS_ENV` only selects the DB filename (`production.sqlite3`). `RAILS_MASTER_KEY` handling is UNDECIDED (runtime Q2): VAPID keys from env only until answered.
- **Logs**: STDOUT, `request_id` metadata, `/up` silenced, `:filter_parameters` with the legacy list, and a Logger formatter plus Phoenix telemetry handler that replace `/rooms/<id>/<id>-<token>` path segments with `[FILTERED]`. Sentry (`sentry` hex package, version `verify`) enabled when `SENTRY_DSN` set and `SKIP_TELEMETRY` blank, `send_default_pii: false`, release `GIT_REVISION`, `before_send` scrubbing bot keys.
- **Health**: `GET /up` returns 200 only after the Endpoint started (it starts last), log-silenced.
- **`config/purchased_by.yml`**: read if present (C-58).
- **Debugging**: `bin/campfire remote` replaces SIGPROF dumps (documented).

## Guarantees

| Guarantee | Kept / changed | Consumers |
|---|---|---|
| Drop-in upgrade on the same volume, same image and tags | kept | ONCE, operators |
| Admin scripts, hooks, `/up`, env names | kept | operators |
| Bot keys never in logs or Sentry | kept | operators |
| Sizing knobs and `REDIS_URL` | **changed** (DV-07): accepted and ignored; `JOB_CONCURRENCY` re-purposed | operators who set them |
| SIGPROF thread dump | **changed** (DV-07): replaced by remote shell | operators |

## Alternatives

- Keep a Ruby `bin/boot`. Rejected: the charter removes Ruby.
- Admin scripts via `eval` only. Rejected: a second writer on a live DB (sqlite-on-beam rules 1, 11).

## Consequences

- Source-ZIP export to once-store hosts (R-10) is UNDECIDED (runtime Q4); the release pipeline ships images only until answered.

## Validation

- `docker run` the port image on a legacy volume with the documented flags; files remain owned by 1000.
- Each admin script run via `docker exec` on a live container; stdout and exit codes match.
- `pre-backup` during a write burst → `PRAGMA integrity_check` ok; `post-restore` → restored data served.
- Log grep after bot traffic and login: no key, password or email.

## Ledger IDs

M-53, M-55, M-57, M-58, M-59, R-01, R-03, R-04, R-06, R-07, R-10, C-47, C-50, C-51, C-52, C-53, C-54, C-57, C-58, C-60
