# 00a dependency defaults — verified from hex package source (2026-10-09)

Method: downloaded tarballs from repo.hex.pm and read the source. Versions are hex.pm latest stable on 2026-10-09.

| Package | Version | Finding | Location |
|---------|---------|---------|----------|
| phoenix | 1.8.15 | `put_secure_browser_headers` defaults: referrer-policy strict-origin-when-cross-origin; content-security-policy `base-uri 'self'; frame-ancestors 'self';`; x-content-type-options nosniff; x-permitted-cross-domain-policies none. No x-frame-options | lib/phoenix/controller.ex:1410 |
| phoenix | 1.8.15 | `pipeline :name` compiles to a public `def name(conn, _)` | lib/phoenix/router.ex:968 |
| phx_new | 1.8.15 | sqlite3 single-app template adds `{Ecto.Migrator, skip: skip_migrations?()}` (runs migrations when RELEASE_NAME is set), DNSCluster and Phoenix.PubSub | templates/phx_single/lib/app_name/application.ex.eex |
| phx_new | 1.8.15 | sqlite prod config: `DATABASE_PATH` via get_env+raise; `pool_size` from `POOL_SIZE` default 5 | lib/phx_new/generator.ex:445 |
| phx_new | 1.8.15 | endpoint keeps `plug Plug.Session` even with --no-html/--no-live | templates/phx_web/endpoint.ex.eex:53 |
| ecto_sqlite3 | 0.25.0 | `default_opts/1` put_new: journal_mode :wal, cache_size -64000, temp_store :memory, pool_size 5 | lib/ecto/adapters/sqlite3/connection.ex:21-26 |
| ecto_sqlite3 | 0.25.0 | `lock_for_migrations/3` is a no-op | lib/ecto/adapters/sqlite3.ex:320 |
| exqlite | 0.42.0 | defaults: default_transaction_mode deferred, journal_mode delete (driver level), synchronous normal, foreign_keys on, busy_timeout 2000 (set via NIF, not PRAGMA) | lib/exqlite/connection.ex:95-145, pragma.ex |
| corsica | 2.1.3 | origins accept string, regex, `{m, f, a}` called as `f(conn, origin, ...a)`; `"*"` only as a sole value; defaults allow_headers [], allow_credentials false | lib/corsica.ex:46-110, 269-290 |

Local toolchain: Elixir 1.20.4 / OTP 29, phx_new archive 1.8.0, hex archive hex-2.3.1-otp-28.

Used by: `.claude/plans/rewrite-00a-skeleton-config-repo/plan.md`.
