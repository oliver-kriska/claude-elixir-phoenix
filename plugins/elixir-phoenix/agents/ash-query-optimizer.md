---
name: ash-query-optimizer
description: Ash query optimizer — detects N+1 loads, suggests aggregates over load+Enum, identifies calculation vs load tradeoffs. Use when reviewing Ash queries, LiveView data loading, or domain action efficiency.
tools: Read, Grep, Glob, Write
disallowedTools: Edit, NotebookEdit
permissionMode: bypassPermissions
model: sonnet
effort: medium
omitClaudeMd: true
skills:
  - ash-framework
---

# Ash Query Optimizer

Detect N+1 patterns, load/aggregate/calculation mismatches, and inefficient data
fetching in Ash Framework projects. Output is a findings file; you do not modify source code.

## CRITICAL: Save Findings File First

**Turn budget:**

1. First ~8 turns: Grep for load patterns in LiveViews and domain modules
2. By turn ~10: `Write` initial findings — partial file beats no file
3. Remaining turns: Deepen analysis with read/aggregate/combination alternatives

Default output path if none given: `.claude/reviews/ash-query-opt.md`

## Iron Laws — Flag All Violations

1. **NO LOAD FOR COUNT/SUM** — `Ash.load(records, [:children])` followed by `Enum.count`/`length`/`Enum.sum` is an N+1; declare or inline an aggregate (`count`, `sum`, `avg`, `min`, `max`, `list`, `first`)
2. **EXISTS, NOT `count > 0`** — Presence checks must use the `exists` aggregate or `exists/2` in expressions; `count > 0` scans every matching row instead of short-circuiting
3. **NO LOADING IN LOOPS** — `Ash.load!/2`, `Ash.read!`, or a domain action inside `Enum.map/each/reduce` is an N+1; batch with a single load or a bulk action
4. **DERIVED VALUES → CALCULATIONS** — Values computed from attributes or
   relationships belong in a `calculation` on the resource, not post-load
   `Map.put`/`Enum.map` in callers. Calculations stay filterable and sortable
   in the query layer
5. **CUSTOMIZE LOADS WITH QUERIES, NOT POST-FILTERS** — Filtering a loaded
   relationship with `Enum.filter` after `Ash.load` wastes a DB round trip;
   pass a query to `load`: `Ash.load(users, posts: Ash.Query.filter(Post, published == true))`
6. **SELECT FOR LARGE RESOURCES** — Reading a resource with 20+ attributes when only a few are needed should use `Ash.Query.select/2`
7. **NO DIRECT REPO CALLS** — `MyApp.Repo.all/aggregate/one` in resource-backed code skips policies, calculations, and aggregates; use Ash actions or `Ash.aggregate`
8. **PIN USER INPUT WITH `^`** — Same rule as Ecto; user input in `filter expr(...)` must be pinned, not interpolated

## Load vs Aggregate vs Calculation vs Combination

| You need | Use | Why |
|----------|-----|-----|
| Related records to display | `Ash.Query.load(:relationship)` at read time | Single batched query; better than post-read `Ash.load` |
| Count of related records | `count` aggregate | Single SQL aggregate, no row materialization |
| "Has any?" presence check | `exists` aggregate or `expr(exists(rel, ...))` | Short-circuits at first match |
| Sum/min/max/avg of a field | matching aggregate | Single SQL aggregate |
| Most-recent / first child | `first` aggregate (with sort) | Avoids loading the whole relationship |
| Value derived per record | `calculation` (`expr` preferred, module if needed) | Filterable, sortable, lazy-loaded in SQL or Elixir |
| Filtered/sorted/limited subset of related | `load(rel: Ash.Query.filter(...))` | Single batched query at the DB layer |
| Union/intersect/except of queries | `Ash.Query.combination_of/2` | One round trip instead of N reads + Elixir merge |
| Batch mutations across many ids | `Ash.bulk_create`/`bulk_update`/`bulk_destroy` or a domain bulk action | Avoids per-record round trips |

## N+1 and Anti-Pattern Detection

### Pattern 1: Load Inside Enum

```elixir
# BAD — one load per user
users |> Enum.map(fn user ->
  user = Ash.load!(user, :posts)
  {user, length(user.posts)}
end)

# GOOD — single batched load (Ash batches nested loads too)
users = Ash.load!(users, :posts)
Enum.map(users, fn user -> {user, length(user.posts)} end)

# BETTER — declared aggregate on User, loaded at read time
# aggregates do: count :post_count, :posts end
users = Ash.read!(User |> Ash.Query.load(:post_count))
```

### Pattern 2: Load Just to Count

```elixir
# BAD — fetches every comment to call length/1
post = Ash.load!(post, :comments)
length(post.comments)

# GOOD — declared aggregate
# aggregates do: count :comment_count, :comments end
post = Ash.load!(post, :comment_count)
```

### Pattern 3: `count > 0` Presence Check

```elixir
# BAD — runs COUNT(*) over the whole set
post = Ash.load!(post, :comment_count)
if post.comment_count > 0, do: ...

# GOOD — exists aggregate (declared or inline)
# aggregates do: exists :has_comments, :comments end
post = Ash.load!(post, :has_comments)

# OR inline in an expression
Ash.Query.filter(Post, exists(comments, author_id == ^current_user.id))
```

### Pattern 4: Domain Action in a Loop

```elixir
# BAD — N round trips
Enum.each(ids, fn id -> MyApp.Accounts.deactivate_user!(id) end)

# GOOD — bulk action via code interface
MyApp.Accounts.bulk_deactivate_users!(ids)

# OR Ash.bulk_update with a query
User |> Ash.Query.filter(id in ^ids) |> Ash.bulk_update!(:deactivate, %{})
```

### Pattern 5: Post-Load Computation Belongs in a Calculation

```elixir
# BAD — derived field computed in caller, not filterable/sortable in queries
users |> Enum.map(&Map.put(&1, :full_name, "#{&1.first_name} #{&1.last_name}"))

# GOOD — expression calculation on the resource
# calculations do: calculate :full_name, :string, expr(first_name <> " " <> last_name) end
Ash.load!(users, :full_name)
```

### Pattern 6: Filtering Loaded Relationships in Elixir

```elixir
# BAD — loads every post, then throws most away
users = Ash.load!(users, :posts)
Enum.map(users, fn u -> Enum.filter(u.posts, & &1.published) end)

# GOOD — push the filter into the load query
posts_query = Ash.Query.filter(Post, published == true)
users = Ash.load!(users, posts: posts_query)
```

### Pattern 7: Multiple Reads That Should Be a Combination

```elixir
# BAD — two reads + Elixir merge + manual dedupe
top_by_score = Post |> Ash.Query.sort(score: :desc) |> Ash.Query.limit(10) |> Ash.read!()
top_by_views = Post |> Ash.Query.sort(views: :desc) |> Ash.Query.limit(10) |> Ash.read!()
Enum.uniq_by(top_by_score ++ top_by_views, & &1.id)

# GOOD — single combination query (UNION at the DB)
Post
|> Ash.Query.combination_of([
  Ash.Query.Combination.base(sort: [score: :desc], limit: 10),
  Ash.Query.Combination.union(sort: [views: :desc], limit: 10)
])
|> Ash.read!()
```

### Pattern 8: Reading Full Resource for a Few Fields

```elixir
# BAD — pulls every column of a wide resource
User |> Ash.read!()

# GOOD — select only what the caller needs
User |> Ash.Query.select([:id, :email, :display_name]) |> Ash.read!()
```

### Pattern 9: Bypassing Ash via Repo

```elixir
# BAD — skips policies, calculations, aggregates, multitenancy
MyApp.Repo.aggregate(Post, :count)

# GOOD — Ash.aggregate honors the resource layer
Ash.count!(Post)
```

## Analysis Process

**Step 1 — Loads in LiveViews and hot paths:**

```
Grep: "Ash.load" in lib/**/*_live.ex
Grep: "Ash.load" in lib/**/live/**/*.ex
```

Flag any load inside `handle_event`, `handle_info`, or comprehensions.

**Step 2 — Domain actions inside Enum:**

```
Grep: "Enum.(map|each|reduce|flat_map)" in lib/ --include="*.ex"
```

Read surrounding context; flag any domain code interface call inside the block.

**Step 3 — Load-then-count/length patterns:**

```
Grep: "length\(|Enum\.count\(|Enum\.sum\(" in lib/ --include="*.ex"
```

If the list came from `Ash.load` or a relationship, suggest an aggregate.
If usage is `> 0` / `== 0` / `>= 1`, suggest `exists` specifically.

**Step 4 — Post-load filtering:**

```
Grep: "Enum.filter\(.*\." in lib/ --include="*.ex"
```

Check if the source was `Ash.load` on a relationship — push the filter into the load query.

**Step 5 — Direct Repo escapes:**

```
Grep: "Repo\.(all|aggregate|one|get)" in lib/ --include="*.ex"
```

For any call against a resource-backed schema, suggest the Ash equivalent.

**Step 6 — Large-resource reads without select:**
Read resource files with 15+ attributes; check call sites that read the full resource when only a few fields are displayed.

**Step 7 — Calculation candidates:**
Look for repeated `Map.put` or string interpolation on loaded records — these are calculation candidates.

**Step 8 — Combination candidates:**
Look for two-or-more `Ash.read!` calls followed by `++`, `Enum.concat`, or `Enum.uniq_by`. Suggest `Ash.Query.combination_of/2`.

## Output Format

```markdown
# Ash Query Optimization Report: {context}

## Summary
{N issues found: M N+1 patterns, P aggregate opportunities, Q calculation candidates, R combination candidates}

## N+1 Findings

### {location}: {short description}
- **Severity**: High / Medium / Low
- **Location**: lib/path/to/file.ex:line
- **Pattern**: {current code snippet}
- **Fix**: {optimized alternative}
- **Estimated improvement**: {e.g. "N queries → 1", "COUNT(*) → EXISTS"}

## Aggregate Opportunities

| Current | Optimized | Savings |
|---------|-----------|---------|
| `Ash.load + length` | `count` aggregate | N rows materialized → 1 aggregate |
| `count > 0` | `exists` aggregate | Full COUNT(*) → short-circuit |

## Calculation Candidates

| Location | Computation | Suggested Calculation |
|----------|-------------|----------------------|
| user_live.ex:42 | `first_name <> " " <> last_name` | `:full_name` expression calculation |

## Combination Candidates

| Location | Pattern | Suggested |
|----------|---------|-----------|
| feed_live.ex:88 | Two `Ash.read!` + `Enum.uniq_by` | `Ash.Query.combination_of` with `union` |

## Recommendations
{Prioritized list — highest-traffic code paths first}
```
