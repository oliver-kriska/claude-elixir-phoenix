# Example Review Output

```markdown
# Review: Magic Link Authentication

**Date**: 2024-01-15
**Files Reviewed**: 12
**Reviewers**: elixir-reviewer, testing-reviewer, security-analyzer

## Summary

| Severity | Count |
|----------|-------|
| Blockers | 1 |
| Warnings | 2 |
| Suggestions | 3 |

**Verdict**: BLOCKED

## Requirements Coverage (from Linear AUTH-142)

| # | Requirement | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Users can request a magic link by email | MET | `request_magic_link_live.ex:34` submit handler |
| 2 | Clicking the link logs the user in | MET | `session_controller.ex:18` verify flow |
| 3 | Tokens expire after 24 hours | UNMET | `auth.ex:45` — no expiry check (see Blocker #1) |
| 4 | Rate-limit per email to 5 requests / hour | UNMET | no Hammer/PlugAttack usage in diff (see Warning #1) |
| 5 | Failed attempts logged for audit | UNCLEAR | `Logger.warn` calls present, no structured audit trail — manual check |

**Summary**: 2 MET · 0 PARTIAL · 2 UNMET · 1 UNCLEAR

## Blockers (1)

### 1. Magic Token Never Expires

**File**: lib/my_app/auth.ex:45
**Reviewer**: security-analyzer
**Issue**: Magic tokens have no expiration, allowing indefinite reuse.
**Why this matters**: An attacker who obtains a token can use it forever.

**Current code**:

```elixir
def verify_magic_token(token) do
  Repo.get_by(MagicToken, token: token)
end
```

**Recommended approach**:

```elixir
def verify_magic_token(token) do
  MagicToken
  |> where([t], t.token == ^token)
  |> where([t], t.inserted_at > ago(24, "hour"))
  |> Repo.one()
end
```

## Warnings (2)

### 1. Missing Rate Limiting

**File**: lib/my_app_web/live/request_magic_link_live.ex
**Reviewer**: security-analyzer
**Issue**: No rate limiting on magic link requests
**Recommendation**: Add Hammer rate limiting

### 2. Test Coverage Gap

**File**: test/my_app/auth_test.exs
**Reviewer**: testing-reviewer
**Issue**: No test for expired token scenario
**Recommendation**: Add expiration test case

## At a Glance

| # | Finding | Severity | Reviewer | File | New? |
|---|---------|----------|----------|------|------|
| 1 | Magic token never expires | BLOCKER | security-analyzer | auth.ex:45 | Yes |
| 2 | Missing rate limiting | WARNING | security-analyzer | request_magic_link_live.ex | Yes |
| 3 | No expired token test | WARNING | testing-reviewer | auth_test.exs | Yes |

## Next Steps

How would you like to proceed?

- `/phx:plan` — Replan the fixes (for complex/architectural issues)
- `/phx:work .claude/plans/magic-link-auth/plan.md` — Fix directly
- I'll handle it myself

```
