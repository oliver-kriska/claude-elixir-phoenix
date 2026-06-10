---
name: ecto-constraint-debug
description: Debug Ecto constraint violations - trace triggers, check migrations,
  find duplicate data. Use when seeing unique_constraint, foreign_key_constraint,
  or check_constraint errors.
metadata:
  effort: medium
---

# Ecto Constraint Debugging

> **Ash projects**: Ash surfaces DB constraints through its own error DSL. Use the `ash-framework` skill — `mix usage_rules.search_docs "constraint" -p ash_postgres`.

Systematic approach to diagnosing constraint violations. Load when you see `Ecto.ConstraintError`, `unique_constraint`, `foreign_key_constraint`, or constraint-related changeset errors.

## Iron Laws

1. **READ THE CONSTRAINT NAME** — The constraint name (e.g., `links_url_index`) tells you exactly which index/constraint failed. Parse it from the error message first
2. **CHECK MIGRATION BEFORE CODE** — Verify the constraint definition in `priv/repo/migrations/` matches what the schema expects
3. **TRACE ALL INSERT PATHS** — Find every code path that inserts into the constrained table. The bug is often in a path you didn't consider
4. **RACE CONDITION UNTIL PROVEN OTHERWISE** — If validation passes but constraint fails, assume concurrent inserts until you prove a single-request cause

## Step-by-Step Debugging

### Step 1: Parse the Error

Extract from the error message:

- **Constraint name** (e.g., `users_email_index`)
- **Table name** (e.g., `users`)
- **Operation** (insert, update, or delete)
- **Conflicting values** (if available in logs)

### Step 2: Find the Migration

Use Grep to search for the constraint name in `priv/repo/migrations/`. Also check for `create unique_index`, `create index`, `add constraint`.

Verify: Does the migration constraint match the schema's `unique_constraint/3` or `foreign_key_constraint/3` call?

### Step 3: Find the Schema

Use Grep to find constraint handling in changesets (`unique_constraint`, `foreign_key_constraint`, `check_constraint`) in `lib/`.

### Step 4: Trace Insert Paths

Find ALL callers that insert/update this schema:

Use Grep to find all insert/update paths (`Repo.insert`, `Repo.update`, `Repo.insert_all`, `cast_assoc`) in `lib/`.

### Step 5: Identify the Cause

| Symptom | Likely Cause | Fix Pattern |
|---------|-------------|-------------|
| Same user triggers twice | Race condition (double-click, retry) | Upsert with `on_conflict` |
| Multiple parents share child | `cast_assoc` doesn't dedup across changesets | Dedup before building changesets |
| Concurrent API requests | Missing transaction isolation | Wrap in `Repo.transaction` or use upsert |
| Migration added constraint to existing data | Data violates new constraint | Backfill or clean data first |

### Step 6: Apply Fix

See `references/constraint-patterns.md` for detailed fix patterns.

## Quick Fixes by Constraint Type

**Unique violation** → Upsert: `Repo.insert(changeset, on_conflict: :replace_all, conflict_target: [:field])`

**Foreign key violation** → Check: Does the referenced record exist? Was it deleted concurrently?

**Check constraint** → Validate: Does the value satisfy the constraint condition?

## References

- `references/constraint-patterns.md` - Detailed patterns for each constraint type

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
