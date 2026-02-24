# Common Elixir Compiler Warnings & Fixes

Quick reference for common compiler warnings encountered during
`/phx:work` execution. Used by the error-matcher hook to provide
remediation hints.

## Critical Warnings (--warnings-as-errors)

### Unused Variables

```
warning: variable "user" is unused
```

**Fix**: Prefix with underscore `_user` or remove if unneeded.

### Undefined Functions

```
warning: MyApp.Accounts.get_user/1 is undefined
```

**Checklist**:
1. Check spelling and arity
2. Is the module imported? `import MyApp.Accounts`
3. Is it aliased? `alias MyApp.Accounts`
4. Does the function exist? `grep -rn "def get_user" lib/`
5. Use full path: `MyApp.Accounts.get_user(id)`

### Module Not Available

```
warning: module MyApp.Schemas.User is not available
```

**Checklist**:
1. File exists? `find lib/ -name "*.ex" | xargs grep "defmodule MyApp.Schemas.User"`
2. Circular dependency? Check `mix xref graph --label compile`
3. Typo in module name?

### Deprecated Functions

```
warning: Ecto.Changeset.cast/4 is deprecated
```

**Fix**: Check the warning message — it always shows the replacement.

### Pattern Match Warnings

```
warning: this clause cannot match because of previous clause
```

**Fix**: Reorder clauses — specific patterns before general ones.

### Compile-Time Config Access

```
warning: Application.get_env/2 is called at compile time
```

**Fix**: Move to function body or use `config/runtime.exs`.

```elixir
# BAD (compile-time)
@api_key Application.get_env(:my_app, :api_key)

# GOOD (runtime)
def api_key, do: Application.get_env(:my_app, :api_key)
```

## Ecto-Specific Warnings

### Missing Index

No warning, but common performance issue:

```elixir
# If you query by field, add an index
create index(:users, [:email])
create index(:orders, [:user_id, :status])  # composite
create unique_index(:users, [:email])        # unique
```

### Unsafe Migration

```elixir
# BAD: Locks table in production
alter table(:users) do
  modify :email, :string, null: false  # TABLE LOCK
end

# GOOD: Add column first, then backfill, then add constraint
alter table(:users) do
  add :email_new, :string
end
```

## LiveView-Specific Warnings

### Unused Assigns

No compile warning, but wastes memory. Check with `/lv:assigns`.

### Missing `connected?` Check

No warning, but Iron Law #3. Check all `PubSub.subscribe` calls.

## Credo Priority Guide

| Priority | Action | Example |
|----------|--------|---------|
| A (Critical) | Must fix | IExPry, IoInspect, Dbg |
| B (Important) | Should fix | CyclomaticComplexity, Nesting |
| C (Minor) | Consider | WithSingleClause, FilterCount |
| D (Cosmetic) | Optional | Naming, formatting suggestions |

## Iron Law Quick Reference

When the error-matcher detects an Iron Law violation, it outputs
the law number and correct pattern. See the main Iron Laws in
CLAUDE.md for the complete list (21 laws).

Common violations during `/phx:work`:
- #1: DB queries in disconnected mount → use assign_async
- #4: :float for money → use :decimal
- #5: No pin in query → use ^value
- #10: String.to_atom with input → use String.to_existing_atom
- #11: No auth in handle_event → add authorization check
- #12: raw() with untrusted content → use html_escape
