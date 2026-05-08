---
name: security
description: Enforce Elixir/Phoenix security — auth, OAuth, sessions, CSRF, XSS, SQL
  injection, input validation, secrets. Use when editing auth files, login flows,
  RBAC, or API keys.
metadata:
  effort: medium
  user-invocable: false
  paths:
  - '**/*auth*.ex'
  - '**/*session*.ex'
  - '**/*password*.ex'
---

# Elixir/Phoenix Security Reference

Quick reference for security patterns in Elixir/Phoenix.

## Iron Laws — Never Violate These

1. **VALIDATE AT BOUNDARIES** — Never trust client input. All data through changesets
2. **NEVER INTERPOLATE USER INPUT** — Use Ecto's `^` operator, never string interpolation
3. **NO String.to_atom WITH USER INPUT** — Atom exhaustion DoS. Use `to_existing_atom/1`
4. **AUTHORIZE EVERYWHERE** — Check in contexts AND re-validate in LiveView events
5. **ESCAPE BY DEFAULT** — Never use `raw/1` with untrusted content
6. **SECRETS NEVER IN CODE** — All secrets in `runtime.exs` from env vars

## Quick Patterns

### Timing-Safe Authentication

```elixir
def authenticate(email, password) do
  user = Repo.get_by(User, email: email)

  cond do
    user && Argon2.verify_pass(password, user.hashed_password) ->
      {:ok, user}
    user ->
      {:error, :invalid_credentials}
    true ->
      Argon2.no_user_verify()  # Timing attack prevention
      {:error, :invalid_credentials}
  end
end
```

### LiveView Authorization (CRITICAL)

```elixir
# RE-AUTHORIZE IN EVERY EVENT HANDLER
def handle_event("delete", %{"id" => id}, socket) do
  post = Blog.get_post!(id)

  # Don't trust that mount authorized this action!
  with :ok <- Bodyguard.permit(Blog, :delete_post, socket.assigns.current_user, post) do
    Blog.delete_post(post)
    {:noreply, stream_delete(socket, :posts, post)}
  else
    _ -> {:noreply, put_flash(socket, :error, "Unauthorized")}
  end
end
```

### SQL Injection Prevention

```elixir
# ✅ SAFE: Parameterized queries
from(u in User, where: u.name == ^user_input)

# ❌ VULNERABLE: String interpolation
from(u in User, where: fragment("name = '#{user_input}'"))
```

## Quick Decisions

### What to validate?

- **All user input** → Ecto changesets
- **File uploads** → Extension + magic bytes + size
- **Paths** → `Path.safe_relative/2` for traversal
- **Atoms** → `String.to_existing_atom/1` only

### What to escape?

- **HTML output** → Auto-escaped by default (`<%= %>`)
- **User HTML** → HtmlSanitizeEx with scrubber
- **Never** → `raw/1` with untrusted content

## Anti-patterns

| Wrong | Right |
|-------|-------|
| `"SELECT * FROM users WHERE name = '#{name}'"` | `from(u in User, where: u.name == ^name)` |
| `String.to_atom(user_input)` | `String.to_existing_atom(user_input)` |
| `<%= raw @user_comment %>` | `<%= @user_comment %>` |
| Hardcoded secrets in config | `runtime.exs` from env vars |
| Auth only in mount | Re-auth in every `handle_event` |

## References

For detailed patterns, see:

- `references/authentication.md` - phx.gen.auth, MFA, sessions
- `references/authorization.md` - Bodyguard, scopes, LiveView auth
- `references/input-validation.md` - Changesets, file uploads, paths
- `references/security-headers.md` - CSP, CSRF, rate limiting, headers
- `references/oauth-linking.md` - OAuth account linking, token management
- `references/rate-limiting.md` - Composite key strategies, Hammer patterns
- `references/advanced-patterns.md` - SSRF prevention, secrets management, supply chain

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
