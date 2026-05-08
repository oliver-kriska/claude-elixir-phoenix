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

Spawn `deep-bug-investigator` agent to systematically check:

1. Is the file saved?
2. Atom vs string key mismatch?
3. Is data preloaded?
4. Is the pattern match correct?
5. Is nil being passed somewhere?
6. Is the return value correct (conn/socket)?
7. Did you restart the server?

## IO.inspect Everything

```elixir
# Add to suspected location
|> IO.inspect(label: "DEBUG: data after transform")
```

## When Stuck

1. `IO.inspect(binding(), label: "all variables")`
2. Add `require IEx; IEx.pry` and step through
3. Check if code is even being reached (add `IO.puts "HERE"`)
4. Compare working vs broken path
