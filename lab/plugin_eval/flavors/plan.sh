# shellcheck shell=bash
# flavor: plan — two /phx:plan outputs, one in progress, one not started.
mkdir -p .claude/plans/user-authentication .claude/plans/admin-panel-redesign

cat > .claude/plans/user-authentication/plan.md <<'MD'
# Plan: User Authentication

## Decisions

- **Schema**: `users` keeps `email` (citext, unique index) and gains
  `hashed_password`; tokens live in a separate `users_tokens` table so sessions
  can be revoked without touching the user row.
- **Hashing**: Argon2 via `argon2_elixir`; no plaintext password ever assigned.
- **LiveView**: `UserLoginLive` and `UserRegistrationLive` share a
  `MyAppWeb.AuthComponents.form/1` function component; `on_mount` hook
  `MyAppWeb.UserAuth.require_authenticated/4` guards live routes.

## Tasks

### Phase 1: Schema

- [x] Migration: add `hashed_password` to users, create `users_tokens`
- [x] `User.registration_changeset/2` with password validation + hashing

### Phase 2: Context

- [x] `Accounts.register_user/1`, `Accounts.get_user_by_email_and_password/2`
- [ ] Session token generation and revocation in `Accounts`

### Phase 3: Web

- [ ] `UserAuth` plug + `on_mount` hooks
- [ ] Login and registration LiveViews with shared form component
- [ ] Router: authenticated `live_session` for `/settings`

### Verification

- [ ] `mix compile --warnings-as-errors && mix test`
MD

cat > .claude/plans/user-authentication/progress.md <<'MD'
# Progress: user-authentication

- Phase 1 complete (2/2). Phase 2: 1/2 — stopped before session tokens.
MD

cat > .claude/plans/admin-panel-redesign/plan.md <<'MD'
# Plan: Admin Panel Redesign

## Decisions

- Replace the controller-rendered admin tables with LiveView + streams (user
  list can exceed 10k rows).
- Authorization through `MyApp.Admin.Policy.authorize/3`, called in every
  `handle_event`.

## Tasks

- [ ] `AdminLive.Users` with `stream(:users, ...)` and server-side pagination
- [ ] Bulk actions (suspend, export CSV) as Oban jobs
- [ ] Audit log entries for every admin action
- [ ] Remove `AdminController` and its templates
MD
