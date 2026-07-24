# Mix Xref Usage

Complete reference for using `mix xref` to trace function calls.

## Basic Commands

### Find All Callers

```bash
# Find who calls a specific function
mix xref callers MyApp.Accounts.update_user/2

# Output format:
# lib/my_app_web/controllers/user_controller.ex:45: MyApp.Accounts.update_user/2
# lib/my_app_web/live/settings_live.ex:67: MyApp.Accounts.update_user/2
```

### Trace a File

```bash
# Show all external calls FROM a file
mix xref trace lib/my_app/accounts.ex

# Output:
# lib/my_app/accounts.ex:5: call Ecto.Changeset.cast/4 (runtime)
# lib/my_app/accounts.ex:12: call MyApp.Repo.insert/1 (runtime)
# lib/my_app/accounts.ex:20: struct MyApp.Accounts.User (export)
```

### Dependency Graph

```bash
# Text format (default)
mix xref graph

# DOT format for visualization
mix xref graph --format dot > deps.dot
dot -Tpng deps.dot -o deps.png

# JSON format (Elixir 1.19+)
mix xref graph --format json --output deps.json

# Stats only
mix xref graph --format stats
```

## Dependency Types

`mix xref` tracks three types of dependencies:

| Type | Description | Example |
|------|-------------|---------|
| `compile` | Compile-time dependency (macros, module body) | `use MyMacro` |
| `export` | Struct or public definition usage | `%User{}` |
| `runtime` | Function calls inside functions | `Repo.get(User, id)` |

### Filter by Type

```bash
# Only runtime dependencies (function calls)
mix xref graph --only-runtime

# Only compile dependencies (macros)
mix xref graph --only-compile

# Exclude specific type
mix xref graph --exclude runtime
```

## Filtering Results

### By Source/Sink

```bash
# Calls FROM a specific file
mix xref graph --source lib/my_app/accounts.ex

# Calls TO a specific module
mix xref graph --sink MyApp.Repo

# Combine
mix xref graph --source lib/my_app/accounts.ex --sink MyApp.Repo
```

### By Label (Module Pattern)

```bash
# Only show calls to specific modules
mix xref graph --label MyApp.Accounts

# Multiple labels
mix xref graph --label MyApp.Accounts --label MyApp.Users
```

## Practical Examples

### Find All Database Calls

```bash
# Where is Repo used?
mix xref callers MyApp.Repo

# Which files call Repo.insert?
mix xref callers MyApp.Repo.insert/1
mix xref callers MyApp.Repo.insert/2
```

### Find All Uses of a Context

```bash
# Who uses the Accounts context?
mix xref graph --sink MyApp.Accounts --format stats
```

### Check Circular Dependencies

```bash
# Find compile-time cycles (runtime cycles like verified_routes() are benign)
mix xref graph --format cycles --label compile

# Output: No cycles found (good!)
# Or: lib/a.ex -> lib/b.ex -> lib/a.ex (bad!)
```

### Analyze a Single Module

```bash
# What does this module depend on?
mix xref graph --source lib/my_app/accounts.ex

# What depends on this module?
mix xref graph --sink lib/my_app/accounts.ex
```

## Integration with Call Tracer

For recursive call tree building:

```bash
# Step 1: Find direct callers
callers=$(mix xref callers MyApp.Target.function/2)

# Step 2: For each caller, find the containing function
# Parse: lib/path/file.ex:42: MyApp.Target.function/2
# Extract file and line, then read to find enclosing function

# Step 3: Recurse
# For each calling function, run mix xref callers again
```

## Fallback: When mix xref Unavailable

If not in a Mix project or xref fails:

```bash
# Grep for function calls (less accurate)
grep -rn "Accounts\.update_user\|update_user(" lib/ --include="*.ex" | grep -v "def update_user"

# Find function definitions
grep -rn "def update_user" lib/ --include="*.ex"

# Find module usage
grep -rn "alias.*Accounts\|MyApp\.Accounts\." lib/ --include="*.ex"
```

## Common Issues

### "Could not find callers"

```bash
# Ensure project is compiled
mix compile

# Check if function exists
mix run -e "IO.inspect MyApp.Accounts.__info__(:functions)"
```

### Too Many Results

```bash
# Filter by directory
mix xref callers MyApp.Repo.get/2 | grep "controllers"

# Focus on runtime only (skip compile-time)
mix xref graph --only-runtime --sink MyApp.Module
```

### Private Functions

`mix xref callers` only finds calls to public functions. For private functions:

```bash
# Grep within the module file
grep -n "function_name" lib/my_app/module.ex
```
