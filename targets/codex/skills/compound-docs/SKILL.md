---
name: compound-docs
description: Searchable Elixir/Phoenix/Ecto solution documentation system with YAML
  frontmatter. Builds institutional knowledge from solved problems. Use when consulting
  past solutions before investigating new issues.
metadata:
  effort: low
  user-invocable: false
---

# Compound Docs — Institutional Knowledge Base

Searchable, categorized solution documentation that makes each
debugging session easier than the last.

## Directory Structure

```
.claude/solutions/
├── ecto-issues/
├── liveview-issues/
├── oban-issues/
├── otp-issues/
├── security-issues/
├── testing-issues/
├── phoenix-issues/
├── deployment-issues/
├── performance-issues/
└── build-issues/
```

## Iron Laws

1. **ALWAYS search solutions before investigating** — Check
   `.claude/solutions/` for existing fixes before debugging
2. **YAML frontmatter is MANDATORY** — Every solution needs
   validated metadata per `references/schema.md`
3. **One problem per file** — Never combine multiple solutions
4. **Include prevention** — Every solution documents how to
   prevent recurrence

## Solution File Format

```markdown
---
module: "Accounts"
date: "2025-12-01"
problem_type: runtime_error
component: ecto_schema
symptoms:
  - "Ecto.Association.NotLoaded on user.posts"
root_cause: missing_preload
severity: medium
tags: [preload, association, n-plus-one]
---

# Association NotLoaded on User Posts

## Symptoms
Ecto.Association.NotLoaded raised when accessing user.posts
in UserListLive after filtering.

## Root Cause
Query in Accounts context missing preload for :posts.

## Solution
Added `Repo.preload(:posts)` to `list_users/1`.

## Prevention
Use n1-check skill before shipping list views.
```

## Searching Solutions

Use Grep to search `.claude/solutions/` by symptom (e.g., `NotLoaded`), by tag (e.g., `tags:.*preload`), or by component (e.g., `component: ecto`).

## Integration

- `$phx-compound` creates solution docs here
- `$phx-investigate` searches here before debugging
- `$phx-plan` consults for known risks
- `learn-from-fix` feeds into this system

## References

- `references/schema.md` — YAML frontmatter validation schema
- `references/resolution-template.md` — Full solution template

## Iron Laws (Inlined)

- **NO unconditional DB queries in mount** — Mount runs twice. Default: `assign_async`. SEO routes: `connected?` + cache-backed disconnected branch (dead-render IS the crawler-indexed HTML)
- **ALWAYS use streams for lists >100 items** — Regular assigns = O(n) memory per user
- **CHECK `connected?/1` before PubSub subscribe** — Prevents double subscriptions
- **NEVER use `:float` for money** — Use `:decimal` or `:integer` (cents)
- **ALWAYS pin values with `^` in queries** — Never interpolate user input
- **SEPARATE QUERIES for `has_many`, JOIN for `belongs_to`** — Avoids row multiplication
- **Jobs MUST be idempotent** — Safe to retry
- **Args use STRING keys, not atoms** — Pattern match `%{"user_id" => id}`
- **NEVER store structs in args** — Store IDs, not `%User{}`
- **NO `String.to_atom` with user input** — Atom exhaustion DoS
- **AUTHORIZE in EVERY LiveView `handle_event`** — Don't trust mount authorization
- **NEVER use `raw/1` with untrusted content** — XSS vulnerability
- **NO process without runtime reason** — Processes model concurrency/state/isolation, NOT code structure
- **SUPERVISE ALL LONG-LIVED PROCESSES** — Never bare `GenServer.start_link`/`Agent.start_link` in production. Use supervision trees
- **NO IMPLICIT CROSS JOINS** — `from(a in A, b in B)` without `on:` creates Cartesian product
- **@external_resource FOR COMPILE-TIME FILES** — Modules reading files at compile time MUST declare `@external_resource`
- **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** — Deduplicate shared child records before building changesets, not inside them
- **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** — When a form save produces no visible error but no expected side effect, check `{:error, changeset}` first
- **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** — Every required field in an embedded schema MUST have a `hidden_input` if not directly editable
- **WRAP THIRD-PARTY LIBRARY APIs** — Always facade external dependency APIs behind a project-owned module. Enables swapping libraries without touching callers
- **NEVER use `assign_new` for values refreshed every mount** — `assign_new` skips the function if the key exists. Use `assign/3` for locale, current user, or any value that must be set on every mount
- **VERIFY BEFORE CLAIMING DONE** — Never say "should work" or "this fixes it." Run `mix compile && mix test` and show the result. If you can't verify, explicitly state what remains unverified
