---
name: phx:deslop
description: "Clean AI-generated slop from Elixir/Phoenix code — dead code, duplication, needless abstraction, boundary violations, missing tests. Use after /phx:work or /phx:full to clean up implementation artifacts, or when codebase feels bloated with unnecessary wrappers and unused code."
effort: medium
argument-hint: "[--review|--fix] [path/to/scope]"
disable-model-invocation: true
---

# Deslop — Elixir AI Slop Cleaner

Identify and clean 5 categories of AI-generated code slop.

## Usage

```
/phx:deslop                    # Review mode (default) — identify only
/phx:deslop --fix              # Fix mode — identify + clean autonomously
/phx:deslop lib/my_app/        # Scope to directory
```

## Arguments

| Arg | Default | Description |
|-----|---------|-------------|
| `--review` | (default) | Identification only, no changes |
| `--fix` | false | Autonomous cleanup with verification |
| path | `lib/` | Scope to specific directory |

## Iron Laws

1. **NEVER delete code that has callers** — check with `mix xref callers` first
2. **NEVER simplify code without running tests** — `mix test` after every fix
3. **`--review` is default** — NEVER auto-fix without explicit `--fix` flag
4. **One category per pass** — don't mix dead code removal with refactoring

## Categories

### 1. Dead Code

Unused functions, unreachable handle_event clauses, orphaned modules.

**Detection**:

```bash
# Unused functions
mix xref unreachable
# Unused modules (no callers)
mix xref graph --format stats | grep "0 incoming"
# Dead handle_event for removed UI elements
grep -rn "def handle_event" lib/ | # cross-ref with templates
```

### 2. Duplication

Same validation in create/update changesets, copied context functions.

**Detection**: Grep for identical function bodies, changeset patterns
that differ only in field name.

### 3. Needless Abstraction

Single-caller wrapper functions, pass-through modules, unnecessary GenServers.

**Detection**: Functions with exactly 1 caller that add no logic
(just delegate). Check with `mix xref callers Module.function/arity`.

### 4. Boundary Violations

Repo calls outside contexts, direct schema access from LiveViews.

**Detection**: Same as Iron Law checks — `Repo.` in `*_live.ex` or
`*_controller.ex` files.

### 5. Missing Tests

New public functions without corresponding test coverage.

**Detection**: Compare public functions in changed files against test files.

## Workflow

### Review Mode (default)

1. Scan each category in scope
2. Report findings with file:line references
3. Classify severity: CRITICAL (breaks conventions) / WARNING / SUGGESTION
4. Present summary, let user decide

### Fix Mode (`--fix`)

4-pass regression-safe workflow:

1. **Identify** — scan all 5 categories
2. **Plan** — group fixes by risk level (safe → risky)
3. **Fix + verify** — apply one fix, run `mix test`, keep/revert
4. **Report** — summary of what was cleaned

## Integration

Suggest after `/phx:work` or `/phx:full`:
"Implementation done. Run `/phx:deslop --review` to check for AI slop?"

## References

- `${CLAUDE_SKILL_DIR}/references/slop-patterns.md` — detailed detection patterns
