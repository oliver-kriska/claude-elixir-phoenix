---
name: narrow-bare-rescue
description: "Narrow bare `rescue _ ->` and `rescue e ->` clauses in Elixir code to explicit exception lists so programmer bugs (UndefinedFunctionError, KeyError, typos) propagate instead of being swallowed. Use when the user mentions bare rescues, silent error swallowing, secure-coding audits, rescue cleanup, `rescue _`, exception masking, auditing error handling, or 'rescue clauses are too broad' — even if they don't name the pattern by this exact term. Also use proactively when you notice a `rescue _ ->` or `rescue e ->` (no `in` clause) while editing Elixir code."
effort: medium
user-invocable: true
argument-hint: "[file_path | directory | --all]"
paths:
  - "**/*.ex"
  - "**/*.exs"
---

# Narrow Bare Rescue

Turn `rescue _ -> fallback` into `rescue _ in [ExceptionType1, ExceptionType2] -> fallback`.

## Why this matters

Bare rescues (`rescue _ ->`, `rescue e ->`, `rescue err ->` — any form without an `in` clause) swallow **every** exception, including programmer bugs:

- `UndefinedFunctionError` from a typo in a module name
- `KeyError` from a misspelled map key
- `CompileError` from bad HEEx in a template
- `ArithmeticError` from a hidden `nil` reaching arithmetic
- Provider-specific errors the author never anticipated

The symptom isn't a stack trace — it's a silent `{:error, :generic}` or a `nil` fallback. Bugs that should surface in tests or AppSignal become quiet degradations that only get noticed when a user complains.

Narrowing the rescue to the exception types the code path actually produces lets genuine bugs propagate with full stack traces while still handling the known failure modes.

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

Applies to both `try … rescue` and `def … rescue …`:

```elixir
# try/rescue form
try do
  risky()
rescue
  e in [MatchError, ArgumentError] -> {:error, e}
end

# def-body rescue form
def call do
  risky()
rescue
  e in [MatchError, ArgumentError] -> {:error, e}
end
```

## Workflow

The skill operates in three modes depending on scope:

1. **Single file** — `/narrow-bare-rescue path/to/file.ex`
2. **Directory** — `/narrow-bare-rescue lib/enaia/util/`
3. **Whole project** — `/narrow-bare-rescue --all`

Whatever the scope, follow this sequence:

### Step 1 — Find the sites

```bash
grep -rn "^\s*rescue\s*$" <scope> | head -200
```

Then for each hit, read the 3 lines after to see the actual pattern. Classify each site:

- **`rescue _ ->`** or **`rescue var ->`** — bare, needs narrowing
- **`rescue _ in [...] ->`** or **`rescue var in Something ->`** — already typed, skip
- **`rescue ExceptionType ->`** (no variable binding) — already typed, skip

### Step 2 — For each bare site, determine the exception set

Read the `try` / `def` body and trace what each call can raise. Don't guess from the function name — verify. The consult order is:

1. **Check the taxonomy table** at `references/taxonomy.md` for the work type (JSON, Ecto, Money, HTTP, etc.) — most sites map cleanly to one row.
2. **Grep deps for `defexception`** when a specific library is called but not in the taxonomy:
   ```bash
   grep -rn "defexception" deps/<libname>/lib/ | head -10
   ```
3. **Look at the `raise` calls** in the code path itself — if the code path explicitly raises `RuntimeError`, include it.

Narrowing goals, in priority order:

- Cover every exception the code path can actually raise (don't change observable behavior)
- Exclude programmer-bug exceptions (`UndefinedFunctionError`, `ArgumentError` from `String.to_atom/1`-style mistakes **at the callsite, not from the lib**, `CompileError`, `FunctionClauseError` from the caller matching the wrong clause — though `FunctionClauseError` from *inside* a lib is often valid to catch)
- Be specific: `Jason.DecodeError` beats `ArgumentError` if both could apply

### Step 3 — Apply the narrowing

**When a file has ≥3 rescues with the same taxonomy**, hoist to a module attribute at the top of the module:

```elixir
@rescuable_errors [
  RuntimeError, ArgumentError, MatchError, FunctionClauseError,
  KeyError, Ecto.NoResultsError, Ecto.StaleEntryError,
  Postgrex.Error, DBConnection.ConnectionError,
  Jason.DecodeError, ExAws.Error
]

defp run_tool(tool, args) do
  tool.call(args)
rescue
  e in @rescuable_errors ->
    Logger.warning("#{tool} failed: #{Exception.message(e)}")
    {:error, :tool_failed}
end
```

Give the attribute a name that reflects its scope (`@tool_rescuable_errors`, `@metrics_rescuable_errors`, `@form_atom_rescuable_errors`) so different taxonomies in the same module stay distinguishable.

### Step 4 — Verify

After changes in each file (or cluster of files), run in order:

```bash
mix compile --warnings-as-errors
mix format <files_changed>
mix test <test_files_for_affected_modules>
```

The compile step catches typos in exception module names — a real risk since you're writing module names from memory.

## Taxonomy table

The most common work types and their verified exception sets live in `references/taxonomy.md`. Read it before narrowing any site. It covers JSON, Ecto/Postgres, Money/Decimal, File I/O, Req HTTP, ExCmd, Regex, atoms-from-strings, forms, and more — plus the specific library gotchas (NimbleCSV, Phoenix LiveView tokenizer, Plug query decoder).

## Special patterns

### `is_exception/1` replaces try/rescue around `Exception.message/1`

`Exception.message/1` only works on exception structs, so a common defensive pattern is:

```elixir
# Before — try/rescue just to handle non-exceptions
message =
  try do
    Exception.message(reason)
  rescue
    _ -> inspect(reason)
  end

# After — guard replaces the rescue
message = if is_exception(reason), do: Exception.message(reason), else: inspect(reason)
```

The `is_exception/1` guard (available since Elixir 1.11) is strictly better: it's a compile-time guard, generates no exception, and removes the bare rescue entirely.

### Oban worker "log and reraise" pattern

Workers often catch exceptions only to log them, then reraise so Oban's retry machinery still fires. Narrow the set even here — programmer bugs then bypass the misleading log line:

```elixir
def perform(%Oban.Job{args: args}) do
  do_work(args)
rescue
  e in [Req.TransportError, Ecto.ConstraintError, Postgrex.Error] ->
    Logger.error("worker failed: #{Exception.message(e)}")
    reraise e, __STACKTRACE__
end
```

Always use `reraise e, __STACKTRACE__` (not `reraise e, []`) to preserve the original stack trace so Oban's retry metadata and error reporters show the right origin.

### ExCmd streams raise a specific exit error

`ExCmd.stream!/1` and `ExCmd.stream/1` raise `ExCmd.Stream.AbnormalExit` on non-zero exit. Every ExCmd rescue must include it — it's not caught by `ErlangError` or `RuntimeError`:

```elixir
rescue
  _ in [ExCmd.Stream.AbnormalExit, ErlangError, ArgumentError, MatchError, RuntimeError] ->
    {:error, :extraction_failed}
end
```

## Scale: partitioning large cleanups

When a codebase has ≥50 bare rescue sites, don't send one PR with 50 files changed. Split by directory into 3-7 clusters, one PR per cluster. Each cluster PR runs `mix test` independently and can land on its own schedule.

Typical partition boundaries (adjust to the codebase layout):

- `lib/<app>/util/` + `lib/<app>/workers/`
- `lib/<app>/ai/` + `lib/<app>/email_sync/`
- `lib/<app>/` remaining long tail
- `lib/<app>_web/`
- `lib/mix/tasks/`

This keeps each PR under ~200 lines changed and each reviewable on its own.

## Preventing regressions — the Credo check

After a cleanup pass lands, add a custom Credo check to prevent new bare rescues. A reference implementation lives in the Enaia codebase at `lib/mix/credo/no_bare_rescue.ex`.

Ship the check **disabled** (`{Credo.Check.Warning.NoBareRescue, false}` in `.credo.exs`) in the same PR that introduces it, then flip it to `[]` in a followup once the cleanup clusters have all merged and CI runs clean.

## What this skill does NOT do

- It does not auto-narrow every bare rescue blindly. Behavior preservation matters — if the code relied on catching an exception that isn't in the narrowed set, the narrowing is a regression.
- It does not touch rescues that are already typed (`rescue e in [X] ->`). Those are correct.
- It does not cover `catch` clauses — `catch :exit, reason ->` is a separate concern (throws and exits from the process).
- It does not replace `try/rescue` with `with` or error-tuple plumbing. That's a larger refactor; narrowing is the local, low-risk fix.

## References

For the full exception taxonomy with library-specific entries, see:

- `${CLAUDE_SKILL_DIR}/references/taxonomy.md` — verified exception types per work category, plus common gotchas
