---
name: liveview-patterns
description: Build LiveView — assign_async, PubSub (check connected?), phx-change
  events, forms, modals, uploads, streams, live_patch. Use for interactions, events,
  or Presence.
metadata:
  effort: medium
  user-invocable: false
  paths:
  - '**/*_live.ex'
  - '**/*_component.ex'
  - '**/*.sface'
  - '**/*_channel.ex'
---

# LiveView Patterns Reference

> **Ash projects**: Use `ash-framework` skill for `AshPhoenix.Form`. Lifecycle: `AshPhoenix.Form.validate/3` on `phx-change`, `AshPhoenix.Form.submit/2` on submit, `to_form/1` for HEEx. Do not use `Ecto.Changeset.cast/3`.

Reference for building with Phoenix LiveView 1.0/1.1.

## Iron Laws — Never Violate These

1. **NO UNCONDITIONAL DB QUERIES IN MOUNT** — Mount runs TWICE. Default: `assign_async`. SEO routes: `connected?` guard + cache-backed disconnected branch (crawlers read that HTML)
2. **ALWAYS USE STREAMS FOR LISTS** — Regular assigns = O(n) memory per user. Streams = O(1)
3. **CHECK connected?/1 BEFORE SUBSCRIPTIONS** — Prevents double subscriptions
4. **EXTRACT VARIABLES BEFORE assign_async CLOSURE** — Closures copy entire referenced variables
5. **LOAD PRIMARY DATA IN mount/3, PAGINATION IN handle_params/3** — handle_params runs on EVERY URL change
6. **NEVER PASS SOCKET TO BUSINESS LOGIC** — Extract data before calling contexts
7. **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** — Silent form save = check `{:error, changeset}` first, not viewport/JS
8. **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** — Every required field in an embedded schema MUST have a `hidden_input` if not directly editable
9. **NEVER USE `assign_new` FOR LIFECYCLE VALUES** — `assign_new` skips the function if key exists. Use `assign/3` for locale, current user, or any value refreshed every mount

## Memory Impact

| Pattern | 3K items | 10K users × 10K items |
|---------|----------|----------------------|
| Regular assigns | ~5.1 MB | ~10+ GB |
| Streams | ~1.1 MB | Minimal (O(1)) |

**Decision**: Lists with >100 items → Use streams, not assigns

## Quick Patterns

### Async Assigns (CRITICAL)

```elixir
def mount(%{"slug" => slug}, _session, socket) do
  # Extract needed values BEFORE the closure
  scope = socket.assigns.current_scope

  {:ok,
   socket
   |> assign_async(:org, fn -> {:ok, %{org: fetch_org(scope, slug)}} end)}
end
```

### Streams for Lists

```elixir
def mount(_params, _session, socket) do
  {:ok, stream(socket, :items, Items.list_items())}
end

# Insert/update/delete
stream_insert(socket, :items, item, at: 0)
stream_delete(socket, :items, item)
```

### SEO Dead-Render (cache-backed disconnected branch)

For public/SEO-visible routes (marketing, articles, product listings) the
disconnected render IS the HTML crawlers see. Fetch from a cache there, real
data on connect:

```elixir
def mount(_params, _session, socket) do
  products =
    if connected?(socket),
      do: Catalog.list_products(),
      else: Cache.get_products() || []

  {:ok, assign(socket, products: products)}
end
```

Empty list → `<noscript>`-friendly skeleton. Cache → `:persistent_term`, ETS,
or Cachex. This satisfies Iron Law #1 AND keeps Googlebot/GPTBot happy.

### PubSub with connected? check

```elixir
def mount(_params, _session, socket) do
  if connected?(socket), do: Chat.subscribe(room_id)
  {:ok, socket}
end
```

## Navigation Decision Tree

```
Same LiveView, different params? → patch / push_patch
Different LiveView, same live_session? → navigate / push_navigate
Different live_session or non-LiveView? → href / redirect
```

## Component Decision Tree

```
Does component need BOTH internal state AND event handling?
│
├── YES → Does it encapsulate APPLICATION logic (not just DOM)?
│   ├── YES → Use LiveComponent ✅
│   └── NO → Refactor to function component with parent handling
│
└── NO → Use Function Component ✅
```

**Official guidance**: "Prefer function components over live components"

## Common Anti-patterns

| Wrong | Right |
|-------|-------|
| DB queries without `assign_async` | Use `assign_async` for all queries |
| `assign(socket, items: list)` for lists | `stream(socket, :items, list)` |
| PubSub subscribe without `connected?` | `if connected?(socket), do: subscribe()` |
| Passing socket to context functions | Extract `socket.assigns` first |
| Business logic in `handle_event` | Delegate to context |
| `assign_new` for locale/user in hooks | `assign/3` (must run every mount) |

## References

For detailed patterns, see:

- `references/async-streams.md` - assign_async, stream_async, streams
- `references/forms-uploads.md` - Forms, validation, file uploads
- `references/components.md` - Function components, LiveComponents
- `references/pubsub-navigation.md` - PubSub, navigation, JS commands
- `references/js-interop.md` - Third-party JS libraries, phx-update="ignore", hooks
- `references/channels-presence.md` - Phoenix Channels, Presence, token auth

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
