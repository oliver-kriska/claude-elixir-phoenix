# Example Full Cycle Run

## Magic Link Authentication

```
$ /phx:full Add magic link authentication

[INITIALIZING] Creating feature branch: feature/magic-link-auth
[DISCOVERING] Scanning codebase for patterns...
  Complexity: HIGH (8/10) — security-critical, new auth mechanism
  User choice: "research it"

[PLANNING] Spawning 4 research agents (comprehensive)...
  ✓ web-researcher: Found 5 relevant discussions
  ✓ hex-library-researcher: Evaluated swoosh, bamboo
  ✓ phoenix-patterns-analyst: Identified existing auth patterns
  ✓ security-analyzer: Reviewed token security patterns
[PLANNING] Creating implementation plan...
  Phase 1: Token Schema (3 tasks)
  Phase 2: Auth Context (4 tasks)
  Phase 3: LiveView Components (5 tasks)
  Phase 4: Tests (4 tasks)
[PLANNING] Written: .claude/plans/magic-link-auth/plan.md

[WORKING] Phase 1: Token Schema
  ✓ Task 1/3: Create magic_tokens migration
  ✓ Task 2/3: Add indexes
  ✓ Task 3/3: Create MagicToken schema
[WORKING] Phase 1 complete, committed

[WORKING] Phase 2: Auth Context
  ✓ Task 1/4: Generate Auth context
  ✓ Task 2/4: Implement create_magic_token/1
  ✗ Task 3/4: Implement verify_magic_token/1 (retry 1/3)
  ✓ Task 3/4: Implement verify_magic_token/1
  ✓ Task 4/4: Add email sending
[WORKING] Phase 2 complete, committed

[WORKING] Phase 3: LiveView Components
  ✓ Task 1/5: Create RequestMagicLinkLive
  ✓ Task 2/5: Create VerifyMagicLinkLive
  ✓ Task 3/5: Add routes
  ✓ Task 4/5: Email template
  ✓ Task 5/5: Flash messages
[WORKING] Phase 3 complete, committed

[WORKING] Phase 4: Tests
  ✓ Task 1/4: Context tests
  ✓ Task 2/4: LiveView tests
  ✓ Task 3/4: Integration tests
  ✓ Task 4/4: Email tests
[WORKING] Phase 4 complete, committed

[REVIEWING] Spawning 4 review agents...
  ✓ elixir-reviewer: 2 suggestions (non-critical)
  ✓ testing-reviewer: PASS
  ✓ security-analyzer: 1 suggestion (token expiry)
  ✓ verification-runner: All tests pass

[REVIEWING] Adding security suggestion to plan...
[WORKING] Implementing token expiry check...
  ✓ Added 24-hour expiry validation
[REVIEWING] Re-review passed

[LEARNING] Captured: "Magic link tokens should expire within 24 hours"

## Feature Complete

**Feature**: Magic link authentication
**Duration**: ~15 minutes
**Files Modified**: 12
**Tests Added**: 8

<promise>DONE</promise>
```
