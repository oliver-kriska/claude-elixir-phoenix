# Special Rescue Patterns

Patterns that come up repeatedly when narrowing bare rescues. Each one is the right shape for a specific callsite, not a generic recipe.

## `is_exception/1` replaces try/rescue around `Exception.message/1`

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

The `is_exception/1` guard (available since Elixir 1.11) is strictly better: it's a
compile-time guard, generates no exception, and removes the bare rescue entirely.

## Oban worker "log and reraise" pattern

Workers often catch exceptions only to log them, then reraise so Oban's retry machinery
still fires. Narrow the set even here — programmer bugs then bypass the misleading log line:

```elixir
def perform(%Oban.Job{args: args}) do
  do_work(args)
rescue
  e in [Req.TransportError, Ecto.ConstraintError, Postgrex.Error] ->
    Logger.error("worker failed: #{Exception.message(e)}")
    reraise e, __STACKTRACE__
end
```

Always use `reraise e, __STACKTRACE__` (not `reraise e, []`) to preserve the original stack
trace so Oban's retry metadata and error reporters show the right origin.

## ExCmd streams raise a specific exit error

`ExCmd.stream!/1` and `ExCmd.stream/1` raise `ExCmd.Stream.AbnormalExit` on non-zero exit.
Every ExCmd rescue must include it — it's not caught by `ErlangError` or `RuntimeError`:

```elixir
rescue
  _ in [ExCmd.Stream.AbnormalExit, ErlangError, ArgumentError, MatchError, RuntimeError] ->
    {:error, :extraction_failed}
end
```

## Module attribute for ≥3 rescues sharing a taxonomy

When a file has three or more rescues that all catch the same set, hoist to a module
attribute at the top. This prevents drift between clauses and makes the set easy to audit.

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

Give the attribute a name that reflects its scope (`@tool_rescuable_errors`,
`@metrics_rescuable_errors`, `@form_atom_rescuable_errors`) so different taxonomies in the
same module stay distinguishable.

## Scale: partitioning large cleanups

When a codebase has ≥50 bare rescue sites, don't send one PR with 50 files changed. Split
by directory into 3-7 clusters, one PR per cluster. Each cluster PR runs `mix test`
independently and can land on its own schedule.

Typical partition boundaries (adjust to the codebase layout):

- `lib/<app>/util/` + `lib/<app>/workers/`
- `lib/<app>/ai/` + `lib/<app>/email_sync/`
- `lib/<app>/` remaining long tail
- `lib/<app>_web/`
- `lib/mix/tasks/`

This keeps each PR under ~200 lines changed and each reviewable on its own.

## Preventing regressions — the Credo check

After a cleanup pass lands, add a custom Credo check to prevent new bare rescues from
re-entering the codebase. The check should flag `rescue _ ->` and `rescue var ->` patterns
and pass `rescue _ in [...] ->` and `rescue var in ExceptionType ->` patterns.

Ship the check **disabled** in the same PR that introduces it:

```elixir
# .credo.exs
{MyApp.Credo.Check.Warning.NoBareRescue, false}
```

Flip it to `[]` in a followup once the cleanup clusters have all merged and CI runs clean.
Shipping disabled first means the check module is loaded and its tests run in CI, but it
doesn't fail any pre-existing bare rescue that the cleanup hasn't reached yet.
