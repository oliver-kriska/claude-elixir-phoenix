---
name: freeze
description: Freeze or scope which files can be edited — read-only investigate lock
  or keep a refactor inside specific dirs. Sentinel + PreToolUse hook.
metadata:
  effort: low
---

# Freeze — scoped edit lock

Toggle a project-local edit lock so Claude can only modify the files you intend
during a focused task (debugging, a tight refactor, a review pass). Enforced by
the `freeze-gate.sh` PreToolUse hook, which denies `Edit`/`Write`/`NotebookEdit`
outside the allow-list. No sentinel = no lock; the hook stays dormant.

The lock lives in `.claude/.freeze` — one allowed path prefix per line,
project-relative. Empty file = freeze everything.

## Usage

`phx-freeze [args]` — resolve `$ARGUMENTS` and run the matching Bash branch.

| Invocation | Effect |
|------------|--------|
| `phx-freeze` | Freeze ALL edits — read-only investigation mode |
| `phx-freeze lib/app_web priv/repo` | Allow edits only under these dirs |
| `phx-freeze status` | Show current lock state |
| `phx-freeze off` | Lift the lock (delete the sentinel) |

### Freeze all edits (investigation mode)

```bash
mkdir -p .claude && : > .claude/.freeze
echo "Freeze ON — all edits blocked. Lift with phx-freeze off"
```

### Scope edits to specific directories

```bash
mkdir -p .claude
printf '%s\n' lib/app_web priv/repo > .claude/.freeze
echo "Freeze ON — edits limited to: lib/app_web priv/repo"
```

Map `$ARGUMENTS` to the dirs the user named. Include any directory you still need
to write to — e.g. add `.claude` if progress/scratchpad logging must continue.

### Show status

```bash
if [ -f .claude/.freeze ]; then
  if [ -s .claude/.freeze ]; then echo "Freeze ON — limited to:"; cat .claude/.freeze
  else echo "Freeze ON — ALL edits blocked"; fi
else echo "Freeze OFF — no edit lock"; fi
```

### Lift the lock

```bash
rm -f .claude/.freeze && echo "Freeze OFF — edits unlocked"
```

## Iron Laws

1. **MANAGE the sentinel via Bash only** (`:>`, `printf`, `rm`) — NEVER via
   Edit/Write. The freeze hook gates Edit/Write and would block you from
   re-scoping or clearing the lock.
2. **NEVER leave a freeze active across unrelated tasks** — it persists until
   `phx-freeze off`, including into later sessions. Clear it when the task ends.
3. **PATHS ARE PROJECT-RELATIVE PREFIXES, one per line** — `lib/foo` allows
   `lib/foo` and everything under it; it does NOT allow `lib/foobar`.

## Notes

- The hook denies with a reason and tells Claude not to retry, so a frozen edit
  surfaces clearly instead of failing silently.
- Pairs with `phx-investigate` (freeze all while root-causing) and `phx-work`
  (scope to the plan's dirs). The lock is advisory tooling, not a security
  boundary — anyone can run `phx-freeze off`.

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
