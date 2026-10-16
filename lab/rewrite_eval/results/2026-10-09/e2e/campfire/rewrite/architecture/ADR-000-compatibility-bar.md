# ADR-000: Compatibility Bar

**Status**: ASSUMED (auto, needs approval)
**Date**: 2026-10-09 · **Source**: `~/Projects/campfire-bench/once-campfire-elixir/reference` @ `90b330024dec` · **Decided by**: `--auto`

## Assumptions

Each default below follows a rule in the plugin's `compatibility-bar.md`. None of them is approved.

1. **Cutover = Replacement.** Rule: `runtime.md` shows one deployable (single ONCE container) and one database (one SQLite file under `/rails/storage`).
2. **Data = Keep schema as-is.** Rule: always. Ecto maps the legacy tables, and Rails `schema_migrations` rows are preserved.
3. **Identity = Keep sessions and hashes.** Rule: always. No user is forced to log out.
4. **Clients = Keep UI and wire protocols.** Rule: the app has a UI. This keeps the Hotwire/Stimulus frontend, served from Phoenix behind an isolated Action Cable shim (`kb/ui-strategy.md` row 1).
5. **Contracts = Keep all.** Rule: always. All 57 contracts in `analysis/contracts.md` are kept, except the Redis/Resque substrate (C-59/C-60 substrate only), which the charter retires.
6. **Performance = No regression vs a measured baseline.** Rule: the baseline is a roadmap slice-0 task.
7. **Steering = Charter wins.** No steering files were found, so there are no conflicts.
8. **Triage = preserve.** All 20 triage items in `features.md` are kept as `preserve` (ASSUMED), including the security-relevant T-03, T-04, T-06 and T-07.

## Cutover Mode

**Replacement.** Campfire ships as one container with one SQLite file and auto-updates through ONCE. The Elixir release replaces the Rails image on the same `/rails/storage` volume, under the same image name and tags (C-50). On boot it opens the existing database in place and runs any pending migrations (C-01, C-55).

- **Rollback** is by restoring the pre-upgrade backup taken by `/hooks/pre-backup` (C-53).
- The pinned Rails image must also still boot on a database the port has written. While Status is ASSUMED, this rollback window has no end date. It means the port makes no destructive schema change, and FTS stays maintained by app code (C-09) unless a later ADR changes that.
- There is no staged cutover and no time when both runtimes are live, so the Transition Contract below does not apply. Rehearsal is a roadmap release slice.

## Kept Contracts

| Contract | Surface | Disposition | Consumers | Witness |
|----------|---------|-------------|-----------|---------|
| C-01 in-place SQLite at schema `20251212154340`, `schema_migrations` kept | data | keep | every install | contracts.md C-01 |
| C-02 UTC text timestamps `YYYY-MM-DD HH:MM:SS.ffffff` | data | keep | pagination, unread, rollback | C-02 |
| C-03 role/status integer enums | data | keep | auth, admin, bots | C-03 |
| C-04 involvement strings | data | keep | push routing, sidebar | C-04 |
| C-05 STI `rooms.type` strings, direct immutable | data | keep | rooms, rollback | C-05 |
| C-06 polymorphic type strings | data | keep | bodies, files | C-06 |
| C-07 bcrypt `password_digest` | data | keep | every user | C-07 |
| C-08 `sessions` rows as revocation authority | data | keep | logged-in users | C-08 |
| C-09 FTS5 `message_search_index`, app-maintained | data | keep | search, rollback | C-09 |
| C-10 Action Text HTML + sgid mentions (incl. Rails 7/Trix forms) | data | keep | every stored message | C-10 |
| C-11 Active Storage tables, disk layout, variants | data | keep | every attachment/avatar | C-11 |
| C-12 singleton account + JSON settings | data | keep | account | C-12 |
| C-13 derived state on every write (touches, unread) | data | keep | sidebar, unread | C-13 |
| C-14 unique keys and their case semantics | data | keep | signup, membership | C-14 |
| C-15 push subscriptions + VAPID keys | data | keep | push users | C-15 |
| C-16 boosts length unenforced (existing rows) | data | keep | boosts | C-16 |
| C-17 searches retention, public-IP bans | data | keep | search, bans | C-17 |
| C-20 legacy `session_token` signed cookie read by the port | wire | keep | logged-in browsers | C-20 |
| C-21 `_campfire_session` encrypted cookie (CSRF secret, return_to) | wire | keep | browsers | C-21 |
| C-22 Rails CSRF token semantics | wire | keep | bundled JS, forms | C-22 |
| C-23 avatar URLs (signed_id, no expiry) | wire | keep | stored HTML, browsers | C-23 |
| C-24 transfer links (4 h) | wire | keep | admins | C-24 |
| C-25 invite link `/join/<code>` | wire | keep | invitees | C-25 |
| C-26 bot key format | wire | keep | bots | C-26 |
| C-27 blob redirect URLs (signed, no expiry, unauthenticated) | wire | keep | stored HTML, shared links | C-27 |
| C-28 stream authorization at subscribe + disconnect on revoke | wire | keep | security | C-28 |
| C-30–C-34 bot HTTP API (raw body, JSON shapes, `Link`/`X-Total-Count`, 403 elsewhere) | wire | keep, byte-compatible | bots | C-30..C-34 |
| C-35–C-36 outbound webhook payload, 7 s timeouts, reply semantics, no signature, no retry | wire | keep, byte-compatible | bot endpoints | C-35, C-36 |
| C-37–C-39 push payload, endpoint allow-list + DNS pinning, SW and manifest URLs | wire | keep | push users | C-37..C-39 |
| C-40 bookmarkable URLs | wire | keep | users | C-40 |
| C-41 Action Cable `/cable` channels | wire | keep via isolated shim (`Compat.ActionCable`) | bundled JS / open tabs | C-41 |
| C-42 login rate limit 10/3 min per IP → 429; banned-IP non-GET/HEAD → 429 | wire | keep (BEAM-native store) | abuse protection | C-42 |
| C-43 logout semantics incl. socket close + push sub delete | wire | keep | users | C-43 |
| C-44 client cookies/localStorage keys | wire | keep | browsers | C-44 |
| C-45 browser floor page | wire | keep | old browsers | C-45 |
| C-46 caching headers | wire | keep | browsers, proxies | C-46 |
| C-47 `GET /up` | wire | keep | ONCE health check | C-47 |
| C-48 JSON endpoints used by bundled JS | wire | keep | bundled JS | C-48 |
| C-49 `client_message_id` DOM keys | wire | keep | bundled JS | C-49 |
| C-50 image name and tags, drop-in upgrade | operational | keep | ONCE installs | C-50 |
| C-51 env var names and meaning | operational | keep | operators | C-51 |
| C-52 all state under `/rails/storage` | operational | keep | operators, backups | C-52 |
| C-53 ONCE hooks | operational | keep | ONCE | C-53 |
| C-54 admin script paths/args/output | operational | keep | operators | C-54 |
| C-55 auto-migrate on boot from any released schema | operational | keep | ONCE upgrades | C-55 |
| C-56 TLS via `TLS_DOMAIN` / `DISABLE_SSL` | operational | keep (mechanism open: Thruster vs in-release ACME) | operators | C-56 |
| C-57 STDOUT logs with bot-key and param filtering | operational | keep | operators | C-57 |
| C-58 `config/purchased_by.yml` | operational | keep | UI text | C-58 |

## Changed or Retired Contracts

| Contract | Change | Consumers affected | Approval |
|----------|--------|--------------------|----------|
| C-59 Redis + Resque substrate | Retired; background work moves to Oban (Lite engine, same SQLite file). The bundled Redis is non-persistent today, so no queued jobs need draining. Delivery semantics (at-most-once for webhooks) stay as C-35/C-36 require | none outside the container; external `REDIS_URL` users unknown | ASSUMED (charter goal) |
| C-60 process sizing knobs | `WEB_CONCURRENCY` / `JOB_CONCURRENCY` lose meaning; Oban queue limits derive from CPU count instead | operators who set them | ASSUMED |

## Data

- **Schema:** Keep as-is. Ecto schemas map the existing tables, including STI strings, polymorphic type strings, integer enums and text timestamps. No destructive DDL is allowed while the rollback window is open.
- **DDL authority:** The port owns DDL after cutover.
  - **Pending Rails migrations** for older installs (C-55) are applied by a port-side Rails migrator that writes the identical version strings into Rails' `schema_migrations`.
  - **The port's own migrations** are additive only and tracked in a separate Ecto `migration_source` (`ecto_schema_migrations`). Ecto's default table name would collide with Rails' table, whose columns it cannot write.
  - **Timestamps** are written in Rails' exact text format by a custom Ecto type. ecto_sqlite3's `:text_datetime` drops microseconds; see `consults/ecto-schema-designer.md`.
- **Oban:** Oban needs its own table, created by an additive migration.
- **Files:** Active Storage disk layout, tables and signed URLs are kept.

## Identity

- **Session reader:** The port reads the legacy `session_token` signed cookie (C-20), using the existing `sessions` table as the revocation authority (C-08).
- **New sessions:** The port mints new sessions in the same format, so a rollback to Rails keeps users logged in.
- **Crypto parameters:** Need test vectors from the pinned Rails image before the identity slice ships.
- **Passwords:** bcrypt hashes verify unchanged (C-07).
- **Logout and ban:** Revocation closes open sockets (C-28, C-43).

## Clients and UI

- **Frontend:** The UI and the bundled Hotwire/Stimulus JS keep working unchanged. Phoenix controllers and HEEx reproduce the HTML.
- **Realtime:** Realtime reaches the existing JS through an Action Cable protocol shim. It lives in one namespace and only translates to and from Phoenix.PubSub. Core contexts never depend on it.
- **LiveView:** Not allowed as a UI replacement under this bar. Moving to LiveView, or to `<turbo-stream-source>` over Phoenix, is a later ADR that would retire C-41, C-48 and C-49. Those three contracts only affect open tabs, which reload.

## Performance Goal

No regression against a measured legacy baseline: p95 latency for message post→broadcast, room load and search, plus memory at idle and under a chat-burst workload. Slice 0 measures the baseline on the pinned Rails image with a production-shaped database copy.

## Steering Files

| File | Weight | Conflict | Resolution |
|------|--------|----------|------------|
| none found | — | — | — |

## Transition Concerns

Not applicable: Replacement mode, so the two runtimes never run live together. The rollback-by-restore requirements in the Cutover section stand in for the transition contract.
