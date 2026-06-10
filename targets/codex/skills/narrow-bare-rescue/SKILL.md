---
name: narrow-bare-rescue
description: Narrow bare rescue in Elixir so real errors like KeyError and typos propagate
  instead of being swallowed. Use to audit rescues and refactor error handling.
metadata:
  effort: medium
  user-invocable: true
  argument-hint: '[file_path | directory | --all]'
  paths:
  - '**/*.ex'
  - '**/*.exs'
---

# Narrow Bare Rescue

Turn `rescue _ -> fallback` into `rescue _ in [ExceptionType1, ExceptionType2] -> fallback`
so programmer bugs propagate while known failure modes stay handled.

## Why this matters

Bare rescues (`rescue _ ->`, `rescue e ->` — any form without an `in` clause) swallow
**every** exception, including `UndefinedFunctionError` from typos, `KeyError` from
misspelled map keys, and `CompileError` from bad HEEx templates. The symptom isn't a stack
trace — it's a silent `{:error, :generic}` or a `nil` fallback. Bugs that should surface
in tests or error reporters become quiet degradations.

The Erlang [Secure Coding Guide](https://www.erlang.org/doc/system/secure_coding.html) makes
the same case at the BEAM level — rule **LNG-002** ("Do Not Use `catch`") warns that the
legacy catch-all form conflates normal returns, throws, and errors. Bare `rescue` in Elixir
is the direct analogue.

## Iron Laws

1. **Never leave `rescue _ ->` or `rescue e ->` without an `in` clause.** Every rescue must
   list exact exception types. The Credo check enforces this after cleanup lands.
2. **Cover every exception the code path can actually raise.** Narrowing that drops a real
   exception is a behavioral regression — trace each call in the body before committing.
3. **Never include programmer-bug exceptions in the list.** `UndefinedFunctionError`,
   `CompileError`, `BadFunctionError`, and `BadArityError` must propagate.
4. **Use `reraise e, __STACKTRACE__`, never `reraise e, []`.** Preserve the original stack
   trace so Oban retry metadata and error reporters show the real origin.
5. **Run `mix compile --warnings-as-errors` before committing.** Typos in exception module
   names only surface at compile time — the code looks fine until it loads.

## The core transform

```elixir
# Before — masks programmer bugs
def parse(body) do
  Jason.decode!(body)
rescue
  _ -> %{}
end

# After — catches only what can actually fail here
def parse(body) do
  Jason.decode!(body)
rescue
  _ in [Jason.DecodeError, ArgumentError] -> %{}
end
```

Applies identically to `try … rescue …` and to function-body `def … rescue …`.

## Workflow

The skill operates in three modes depending on scope:

1. **Single file** — `/narrow-bare-rescue path/to/file.ex`
2. **Directory** — `/narrow-bare-rescue lib/my_app/util/`
3. **Whole project** — `/narrow-bare-rescue --all`

Whatever the scope, follow this sequence.

### Step 1 — Find the sites

```bash
grep -rn "^\s*rescue\s*$" <scope> | head -200
```

For each hit, read the 3 lines after to classify:

- `rescue _ ->` or `rescue var ->` — bare, needs narrowing
- `rescue _ in [...] ->` or `rescue var in Something ->` — already typed, skip
- `rescue ExceptionType ->` (no variable binding) — already typed, skip

### Step 2 — Determine the exception set for each bare site

Read the `try` / `def` body and trace what each call can raise. Don't guess from the
function name — verify. Consult order:

1. **Check `references/taxonomy.md`** for the work type (JSON, Ecto, Money, HTTP, etc.).
   Most sites map cleanly to one row.
2. **Grep deps for `defexception`** when a specific library isn't in the taxonomy:

   ```bash
   grep -rn "defexception" deps/<libname>/lib/ | head -10
   ```

3. **Check `raise` calls in the code path itself** — if the body explicitly raises
   `RuntimeError`, include it.

Priorities: cover everything the code can actually raise, exclude programmer-bug
exceptions (see Iron Law #3), and prefer specific types (`Jason.DecodeError` beats
`ArgumentError` if both could apply).

### Step 3 — Apply the narrowing

For files with ≥3 rescues sharing a taxonomy, hoist to a module attribute — see
`references/patterns.md` for the module-attribute pattern, Oban reraise, ExCmd exit
errors, and `is_exception/1` replacements.

### Step 4 — Verify

After changes in each file (or cluster of files), run:

```bash
mix compile --warnings-as-errors
mix format <files_changed>
mix test <test_files_for_affected_modules>
```

The compile step catches typos in exception module names — a real risk since you're writing
module names from memory.

## Scope

This skill narrows bare `rescue` clauses. It does not:

- Auto-narrow blindly — behavior preservation matters; trace each call path first
- Touch rescues that are already typed (`rescue e in [X] ->`) — those are correct
- Cover `catch` clauses — throws and exits from the process are a separate concern
- Replace `try/rescue` with `with` or error-tuple plumbing — that's a larger refactor

## References

- `references/taxonomy.md` — verified exception types per work
  category, plus library-specific gotchas (NimbleCSV, Plug, Phoenix LiveView tokenizer)
- `references/patterns.md` — special patterns: `is_exception/1`,
  Oban reraise, ExCmd exit errors, module-attribute hoisting, partitioning large
  cleanups, the regression-prevention Credo check
- [Erlang Secure Coding Guide — LNG-002: Do Not Use `catch`](https://www.erlang.org/doc/system/secure_coding.html)
  — BEAM-level rationale for preferring narrow `try ... catch` / `try ... rescue` over
  the legacy catch-all form

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
