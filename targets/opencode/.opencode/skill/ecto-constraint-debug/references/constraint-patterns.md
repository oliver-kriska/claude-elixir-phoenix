# Constraint Debugging Patterns

## Unique Constraint Violations

### Pattern 1: Race Condition (Double Submit)

**Symptom**: `unique_constraint` error on user action, works on retry.

**Root cause**: Two concurrent requests insert the same unique value.

**Fix**: Upsert pattern

```elixir
def create_or_update_link(attrs) do
  %Link{}
  |> Link.changeset(attrs)
  |> Repo.insert(
    on_conflict: {:replace, [:updated_at]},
    conflict_target: [:url],
    returning: true
  )
end
```

### Pattern 2: Shared Data via `cast_assoc`

**Symptom**: Inserting parent records that share child associations fails on the second parent.

**Root cause**: `cast_assoc` builds separate INSERT for each parent's children. If two parents reference the same child (e.g., same URL), the second INSERT violates the unique constraint.

**Fix**: Deduplicate before building changesets

```elixir
# BAD: Each contact gets its own link changesets
contacts
|> Enum.map(fn contact ->
  Contact.changeset(contact, %{links: extract_links(contact.text)})
end)

# GOOD: Deduplicate links first, then associate
all_links = contacts |> Enum.flat_map(&extract_links(&1.text)) |> Enum.uniq_by(& &1.url)
{:ok, links} = Repo.insert_all(Link, all_links, on_conflict: :nothing, returning: true)
link_map = Map.new(links, &{&1.url, &1.id})

contacts
|> Enum.map(fn contact ->
  link_ids = contact.text |> extract_links() |> Enum.map(&link_map[&1.url])
  Contact.changeset(contact, %{link_ids: link_ids})
end)
```

### Pattern 3: Bulk Insert with Duplicates

**Symptom**: `insert_all` fails when input data has duplicate values for a unique column.

**Fix**: Deduplicate input or use `on_conflict: :nothing`

```elixir
# Deduplicate input
unique_records = Enum.uniq_by(records, & &1.email)

# Or handle at DB level
Repo.insert_all(User, records,
  on_conflict: :nothing,
  conflict_target: [:email]
)
```

## Foreign Key Violations

### Pattern 1: Orphaned Reference

**Symptom**: Insert/update fails because referenced record doesn't exist.

**Root cause**: Parent record was deleted between validation and insert, or ID was passed incorrectly.

**Fix**: Check existence in transaction

```elixir
Repo.transact(fn ->
  case Repo.get(Parent, parent_id) do
    nil -> {:error, :parent_not_found}
    parent ->
      %Child{parent_id: parent.id}
      |> Child.changeset(attrs)
      |> Repo.insert()
  end
end)
```

### Pattern 2: Cascade Delete Surprise

**Symptom**: Deleting a parent silently deletes children (or fails if no cascade).

**Check migration**: Look for `on_delete` option

```elixir
# In migration
add :parent_id, references(:parents, on_delete: :delete_all)  # CASCADE
add :parent_id, references(:parents, on_delete: :restrict)      # BLOCK
add :parent_id, references(:parents, on_delete: :nilify_all)    # SET NULL
add :parent_id, references(:parents, on_delete: :nothing)       # DB DEFAULT
```

## Check Constraint Violations

### Pattern 1: Enum Mismatch

**Symptom**: Insert fails on check constraint for an Ecto.Enum field.

**Root cause**: Value not in the allowed list defined in migration.

**Debug**: Compare schema enum values with migration constraint

```elixir
# Schema
field :status, Ecto.Enum, values: [:draft, :active, :archived]

# Migration must match
create constraint(:items, :status_must_be_valid,
  check: "status IN ('draft', 'active', 'archived')")
```

### Pattern 2: Range Violation

**Symptom**: Value fails a range check constraint.

**Debug**: Read the constraint definition in migration

```bash
grep -r "create constraint.*table_name" priv/repo/migrations/
```

## Debugging Techniques

### Inspect the Changeset Error

```elixir
case Repo.insert(changeset) do
  {:ok, record} -> {:ok, record}
  {:error, changeset} ->
    # constraint errors appear in changeset.errors
    IO.inspect(changeset.errors, label: "INSERT ERRORS")
    IO.inspect(changeset.changes, label: "ATTEMPTED CHANGES")
    {:error, changeset}
end
```

### Check for Existing Data

```elixir
# Find what's violating the unique constraint
Repo.all(from r in Record, where: r.unique_field == ^value)
```

### Trace with Tidewave (when available)

```
mcp__tidewave__execute_sql_query "SELECT * FROM table WHERE unique_col = 'value'"
mcp__tidewave__project_eval "MyApp.Repo.all(from r in MyApp.Record, where: r.field == ^value)"
```

## Prevention Patterns

### Always Handle Constraint Errors

```elixir
def create_entity(attrs) do
  %Entity{}
  |> Entity.changeset(attrs)
  |> Repo.insert()
  |> case do
    {:ok, entity} -> {:ok, entity}
    {:error, %{errors: [field: {_, [constraint: :unique]}]}} ->
      # Handle duplicate gracefully
      {:error, :already_exists}
    {:error, changeset} -> {:error, changeset}
  end
end
```

### Use Upserts for Idempotency

```elixir
def upsert_entity(attrs) do
  %Entity{}
  |> Entity.changeset(attrs)
  |> Repo.insert(
    on_conflict: {:replace, [:name, :updated_at]},
    conflict_target: [:external_id],
    returning: true
  )
end
```

### Add Both Validation AND Constraint

```elixir
def changeset(entity, attrs) do
  entity
  |> cast(attrs, [:email])
  |> validate_required([:email])
  |> unsafe_validate_unique(:email, MyApp.Repo)  # Quick feedback
  |> unique_constraint(:email)                     # DB safety
end
```
