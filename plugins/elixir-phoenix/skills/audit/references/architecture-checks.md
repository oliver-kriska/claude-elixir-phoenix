# Architecture Checks Reference

Detailed criteria for architecture health assessment.

## Context Health Matrix

### What to Check

For each context in `lib/{app}/`:

| Metric | Healthy Range | Red Flag |
|--------|---------------|----------|
| Modules per context | 3-15 | >20 or <2 |
| Public API functions | 5-30 | >40 |
| Schemas per context | 1-5 | >8 |
| Fan-out (contexts called) | 1-4 | >6 |
| Fan-in (called by contexts) | 1-6 | >10 |

### Commands

```bash
# Module count per context
for dir in lib/my_app/*/; do
  echo "$(basename $dir): $(find $dir -name '*.ex' | wc -l) modules"
done

# Public function count
grep -r "^  def " lib/my_app/*.ex --include="*.ex" | wc -l

# Schema count
grep -rl "use Ecto.Schema" lib/my_app/ | wc -l

# Fan-out via xref
mix xref graph --format stats
```

## Coupling Analysis

### Fan-Out (Efferent Coupling)

How many other contexts does this context depend on?

```bash
# For each context, count outgoing dependencies
mix xref graph --label compile-connected --format dot | grep "my_app_accounts ->"
```

| Fan-Out | Assessment |
|---------|------------|
| 0-2 | Excellent - well isolated |
| 3-4 | Good - reasonable dependencies |
| 5-6 | Warning - consider splitting |
| 7+ | Critical - "god context" |

### Fan-In (Afferent Coupling)

How many contexts depend on this context?

| Fan-In | Assessment |
|--------|------------|
| 0 | Dead code? Or utility only |
| 1-4 | Good - clear responsibility |
| 5-8 | Common utility - ensure stable API |
| 9+ | Core abstraction - avoid changes |

## Cohesion Analysis

### Signs of Low Cohesion

- Context name is generic ("Utils", "Helpers", "Services")
- Functions don't share domain vocabulary
- Multiple unrelated schemas in same context
- Context has >50 public functions

### Assessment

```bash
# Check for generic names
ls lib/my_app/ | grep -E "utils|helpers|services|common|shared"

# Large API surface
for file in lib/my_app/*.ex; do
  funcs=$(grep -c "^  def " "$file" 2>/dev/null || echo 0)
  if [ "$funcs" -gt 30 ]; then
    echo "WARNING: $(basename $file) has $funcs public functions"
  fi
done
```

## Boundary Violations

### Types of Violations

| Violation | Severity | Example |
|-----------|----------|---------|
| Direct Repo from web | High | `Web.Controller` calls `Repo.all` |
| Cross-context schema import | Medium | `Orders` aliases `Accounts.User` |
| Direct schema access | Medium | `%Accounts.User{}` outside Accounts |
| Context calling _web module | High | Business logic → presentation |

### Detection

```bash
# Repo calls outside contexts
grep -rn "Repo\." lib/my_app_web/ --include="*.ex"

# Cross-context schema aliases
grep -rn "alias MyApp\." lib/my_app/ --include="*.ex" | grep -v "alias MyApp\.$(dirname)"
```

## Circular Dependencies (Compile-Time)

Runtime cycles (e.g., from `verified_routes()`) are benign and don't cause recompilation cascades.
Only compile-time cycles affect build performance and are scored.

### Detection

```bash
mix xref graph --format cycles --label compile
```

### Assessment

| Cycles | Assessment |
|--------|------------|
| 0 | Excellent |
| 1-2 | Warning - analyze and fix |
| 3+ | Critical - architectural issue |

### Resolution Patterns

1. **Extract shared module** - Move shared code to new context
2. **Behavior/protocol** - Define interface, implement separately
3. **Event-driven** - Replace direct calls with PubSub
4. **Merge contexts** - If truly coupled, they're one context

## Naming Conventions

### Module Naming

| Pattern | Assessment |
|---------|------------|
| `MyApp.{Domain}.{Entity}` | Correct |
| `MyApp.{Domain}Service` | Avoid "Service" suffix |
| `MyApp.{Domain}Manager` | Avoid "Manager" suffix |
| `MyApp.{Domain}Helper` | Move to domain context |

### Function Naming

| Pattern | Assessment |
|---------|------------|
| `get_user/1` | Correct - raises |
| `fetch_user/1` | Correct - returns tuple |
| `list_users/0` | Correct |
| `find_user/1` | Inconsistent - use get/fetch |
| `user/1` | Too vague |

### Context API Surface

Well-designed context has:

```elixir
defmodule MyApp.Accounts do
  # Queries (list/get/fetch)
  def list_users(opts \\ [])
  def get_user!(id)
  def fetch_user(id)

  # Commands (create/update/delete)
  def create_user(attrs)
  def update_user(user, attrs)
  def delete_user(user)

  # Domain operations
  def authenticate(email, password)
  def verify_email(token)
end
```

## Output Format

```markdown
## Architecture Review

### Context Health Matrix

| Context | Modules | Public API | Fan-Out | Fan-In | Assessment |
|---------|---------|------------|---------|--------|------------|
| Accounts | 5 | 12 | 2 | 4 | Healthy |
| Orders | 18 | 45 | 8 | 3 | Too Large |
| Shared | 2 | 8 | 0 | 12 | Utility OK |

### Boundary Violations

| Type | Location | Severity |
|------|----------|----------|
| Direct Repo | post_controller.ex:45 | High |

### Circular Dependencies

- None found ✅

### Recommendations

1. **Split Orders context** - 18 modules is too large
   - Extract Fulfillment (shipping, tracking)
   - Extract Invoicing (billing, receipts)

2. **Fix boundary violation** - Move Repo call to context
   - `PostController.create/2` should call `Blog.create_post/1`
```
