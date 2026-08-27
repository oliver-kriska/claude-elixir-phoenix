# Error Patterns - Read Error LITERALLY

## Common Elixir/Phoenix Errors

| Error | Literal Meaning | Check |
|-------|-----------------|-------|
| `UndefinedFunctionError: MyMod.func/2` | Function doesn't exist with that arity | Is it `func/1` not `func/2`? |
| `KeyError: key :name not found` | Map doesn't have `:name` key | String key `"name"` instead? |
| `FunctionClauseError` | No pattern matched | `IO.inspect` the actual data |
| `(Ecto.NoResultsError)` | Query returned nil | Data doesn't exist in DB |
| `(Protocol.UndefinedError)` | Protocol not implemented | Wrong data type passed |

## Ralph Wiggum Checklist

Check systematically, or delegate to a generic read-only subagent if native DeepSeek Harness subagent tooling is available:

1. Is the file saved?
2. Atom vs string key mismatch?
3. Is data preloaded?
4. Is the pattern match correct?
5. Is nil being passed somewhere?
6. Is the return value correct (conn/socket)?
7. Did you restart the server?

## Temporary Diagnostics

Only when the user explicitly authorizes temporary source edits, add and later remove diagnostics such as:

```elixir
# Add to suspected location
|> IO.inspect(label: "DEBUG: data after transform")
```

## When Stuck

1. Inspect values through failing test output or an available safe runtime eval
2. Run a focused IEx expression without modifying source files
3. Trace reachability through existing logs or tests; source edits require approval
4. Compare the working and broken paths
