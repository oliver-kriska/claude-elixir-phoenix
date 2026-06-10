---
name: phoenix-contexts
description: Phoenix context design — creating/splitting contexts, Scope (1.8+), Ecto.Multi,
  PubSub, routers, plugs, controllers. Use when editing contexts, routers, or designing
  boundaries.
metadata:
  effort: medium
  user-invocable: false
---

# Phoenix Contexts Reference

> **Ash projects**: `Ash.Domain` replaces Phoenix contexts for data access — use the `ash-framework` skill. Context boundary and PubSub patterns still apply.

Reference for designing and implementing Phoenix contexts (bounded contexts).

## Iron Laws — Never Violate These

1. **CONTEXTS OWN THEIR DATA** — Never query another context's schema directly via Repo
2. **SCOPES ARE MANDATORY (Phoenix 1.8+)** — Every context function MUST accept scope as first parameter
3. **THIN CONTROLLERS/LIVEVIEWS** — Controllers translate HTTP, business logic stays in contexts
4. **NO SIDE EFFECTS IN SCHEMAS** — Use `Ecto.Multi` for transactions with side effects

## Context Structure

```
lib/my_app/
├── accounts/           # Context directory
│   ├── user.ex         # Schema
│   ├── scope.ex        # Scope struct (Phoenix 1.8+)
├── accounts.ex         # Context module (public API)
```

## Phoenix 1.8+ Scopes (CRITICAL)

All context functions MUST accept scope as first parameter:

```elixir
def list_posts(%Scope{} = scope) do
  from(p in Post, where: p.user_id == ^scope.user.id)
  |> Repo.all()
end

def create_post(%Scope{} = scope, attrs) do
  %Post{user_id: scope.user.id}
  |> Post.changeset(attrs)
  |> Repo.insert()
  |> broadcast(scope, :created)
end
```

## Quick Decisions

### When to SPLIT contexts?

- Module exceeds ~400 lines
- Functions don't share domain language
- Could theoretically be a separate microservice
- Team member could own it independently

### When to KEEP together?

- Resources share vocabulary and domain concepts
- Functions frequently operate on same data together
- Splitting would create excessive cross-context calls

### Cross-Context References

```elixir
# ✅ Reference by ID, convert at boundary
def create_order(%Scope{} = scope, user_id, product_ids) do
  with {:ok, user} <- Accounts.fetch_user(scope, user_id) do
    do_create_order(scope, user.id, product_ids)
  end
end

# ❌ Reaching into other context's internals
alias MyApp.Accounts.User  # Don't do this
Repo.all(from o in Order, join: u in User, ...)  # Don't query other schemas
```

## Anti-patterns

| Wrong | Right |
|-------|-------|
| Service objects (`UserCreationService`) | Context functions (`Accounts.create_user/2`) |
| Repository pattern wrapping Repo | Repo IS the repository |
| Direct Repo calls in controllers | Delegate to context |
| Schema callbacks with side effects | Use Ecto.Multi |

## Version Notes

- **Phoenix 1.8+**: Uses built-in `%Scope{}` struct for authorization context
- **Phoenix 1.7**: Requires manual authorization context (see `references/scopes-auth.md` "Pre-Scopes Patterns")

## References

For detailed patterns, see:

- `references/context-patterns.md` - Full context module, PubSub, Multi, cross-boundary
- `references/scopes-auth.md` - Scope struct, multi-tenant, authorization, plugs
- `references/routing-patterns.md` - Verified routes, pipelines, API auth
- `references/plug-patterns.md` - Function/module plugs, placement, guards
- `references/json-api-patterns.md` - JSON controllers, FallbackController, API auth

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
