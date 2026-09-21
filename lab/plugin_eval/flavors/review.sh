# shellcheck shell=bash
# flavor: review — /phx:review output for the user-authentication plan.
mkdir -p .claude/plans/user-authentication/reviews .claude/plans/user-authentication/summaries

cat > .claude/plans/user-authentication/reviews/security-analyzer.md <<'MD'
# Security review: user-authentication

1. **HIGH** — `UserLoginLive.handle_event("login", ...)` logs the raw params map (includes password).
2. **HIGH** — Session tokens are not rotated on login (session fixation).
3. **MEDIUM** — No rate limiting on `get_user_by_email_and_password/2`.
4. **MEDIUM** — `users_tokens` has no expiry index; stale tokens never purged.
5. **LOW** — Password minimum length is 8; guidance recommends 12.
MD

cat > .claude/plans/user-authentication/reviews/elixir-reviewer.md <<'MD'
# Elixir review: user-authentication

1. **MEDIUM** — `register_user/1` matches `{:error, _}`; changeset errors never reach the form.
2. **MEDIUM** — `Accounts` calls `Repo` inside `Enum.map` when revoking tokens (N+1).
3. **LOW** — `with` chain in `UserAuth.fetch_current_user/2` has an unreachable `else` branch.
4. **LOW** — Missing `@doc` on public `Accounts` functions.
MD

cat > .claude/plans/user-authentication/summaries/consolidated.md <<'MD'
# Consolidated review findings (23 total)

| Severity | Count | Tracks |
|----------|-------|--------|
| HIGH     | 4     | security (2), testing (2) |
| MEDIUM   | 11    | security (2), elixir (2), testing (4), verification (3) |
| LOW      | 8     | elixir (2), security (1), testing (5) |

Top items: raw password logged in `UserLoginLive`; no session token rotation;
`{:error, _}` swallows changeset errors; N+1 when revoking tokens.
MD
