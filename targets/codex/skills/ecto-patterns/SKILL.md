---
name: ecto-patterns
description: Ecto patterns — schemas, changesets, queries, migrations, Multi, associations,
  preloads, upserts. Use when editing Repo calls, Ecto.Query, or schema fields. Skip
  for Ash.
metadata:
  effort: medium
  user-invocable: false
  paths:
  - '**/migrations/*.exs'
  - '**/*_schema.ex'
  - '**/*changeset*.ex'
---

# Ecto Patterns Reference

Reference for working with Ecto schemas, queries, and migrations.

## Iron Laws — Never Violate These

1. **CHANGESETS ARE FOR EXTERNAL DATA** — Use `cast/4` for user/API input, `change/2` or `put_change/3` for internal trusted data
2. **NEVER USE `:float` FOR MONEY** — Always use `:decimal` or `:integer` (cents)
3. **NO RAILS-STYLE POLYMORPHIC ASSOCIATIONS** — They break foreign key constraints; use multiple nullable FKs or separate join tables
4. **ALWAYS PIN VALUES IN QUERIES** — `u.name == ^user_input` is safe, string interpolation causes SQL injection
5. **PRELOAD COLLECTIONS, NOT INDIVIDUALS** — Preloading in loops = N+1 queries
6. **CONSTRAINTS BEAT VALIDATIONS FOR RACE CONDITIONS** — Validations provide quick feedback, constraints provide DB-level safety
7. **SEPARATE QUERIES FOR `has_many`, JOIN FOR `belongs_to`** — Avoids row multiplication
8. **NO IMPLICIT CROSS JOINS** — `from(a in A, b in B)` without `on:` creates Cartesian product
9. **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** — When multiple parents share child data, deduplicate child records BEFORE building changesets. Dedup only works within a single changeset

## Quick Schema Template

```elixir
defmodule MyApp.Context.Entity do
  use Ecto.Schema
  import Ecto.Changeset

  @primary_key {:id, :binary_id, autogenerate: true}
  @foreign_key_type :binary_id

  schema "entities" do
    field :name, :string
    field :status, Ecto.Enum, values: [:draft, :active, :archived]
    field :amount_cents, :integer  # Never :float for money!
    belongs_to :user, MyApp.Accounts.User
    timestamps(type: :utc_datetime_usec)
  end

  def changeset(entity, attrs) do
    entity
    |> cast(attrs, [:name, :status, :amount_cents])
    |> validate_required([:name])
    |> foreign_key_constraint(:user_id)
  end
end
```

## Quick Decisions

### cast vs put_change vs change

| Function | Use When |
|----------|----------|
| `cast/4` | External data (user input, API) |
| `put_change/3` | Internal trusted data (timestamps, computed) |
| `change/2` | Internal data from existing struct |

### Preload Strategy

| Relationship | Strategy |
|--------------|----------|
| `belongs_to` | JOIN (single query) |
| `has_many` | Separate queries (avoid row multiplication) |

## Common Anti-patterns

| Wrong | Right |
|-------|-------|
| `field :amount, :float` | `field :amount_cents, :integer` |
| `"SELECT * WHERE name = '#{name}'"` | `from(u in User, where: u.name == ^name)` |
| `Repo.all(User) \|> Enum.filter(& &1.active)` | `from(u in User, where: u.active)` |
| Preloading in loops | `Repo.preload(posts, :comments)` |
| `Repo.get!(User, user_id)` with user input | `Repo.get(User, id)` + handle nil |

## References

For detailed patterns, see:

- `references/changesets.md` - cast vs put_change, custom validations, prepare_changes
- `references/queries.md` - Composable queries, dynamic, subqueries, preloading
- `references/migrations.md` - Safe migrations, concurrent indexes, NOT NULL
- `references/transactions.md` - Repo.transact, Ecto.Multi, upserts

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
