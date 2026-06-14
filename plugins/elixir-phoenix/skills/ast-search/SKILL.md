---
name: phx:ast-search
description: "Search and refactor Elixir by AST pattern via ex_ast — structural find/replace/diff by arity, pipe form, or call shape, with preview before apply. Use for structure-aware searches, not text grep."
effort: medium
argument-hint: "pattern | old new path | diff a.ex b.ex"
allowed-tools: Read, Grep, Glob, Bash
---

# Structural AST Search & Refactor

Drive `ex_ast` to find, rewrite, or diff Elixir by **structure**, not text. See the
`ex-ast` skill for the full pattern language; this skill is the interactive workflow.

## Iron Laws

1. **PREVIEW BEFORE APPLY** — Run `mix ex_ast.replace` with NO `--apply` first; show the
   plan; only apply after the user confirms (or the task is explicitly autonomous)
2. **DEP CHECK FIRST** — Confirm `:ex_ast` is in `mix.exs`; if absent, offer the dep line
   and stop until installed
3. **VERIFY AFTER APPLY** — After `--apply`, run `mix format` + `mix compile
   --warnings-as-errors` + `mix test` on affected files before claiming done
4. **AST OVER GREP** — This command is for structural queries; redirect plain
   text/comment searches back to `grep`

## Step 0: Dependency Check (ALWAYS FIRST)

```bash
grep -q ':ex_ast' mix.exs && echo "ex_ast: ✓" || echo "ex_ast: ✗"
```

If absent, tell the user and offer:

```elixir
# mix.exs deps/0
{:ex_ast, "~> 0.12", only: [:dev, :test], runtime: false}
```

Then `mix deps.get` and re-run. Do not proceed without the dep.

## Step 1: Pick the Mode

Infer from the argument:

| Argument shape | Mode | Task |
|----------------|------|------|
| one `'pattern'` | Search | `mix ex_ast.search` |
| `'old' 'new' path` | Refactor | `mix ex_ast.replace` (preview → apply) |
| `diff a.ex b.ex` | Diff | `mix ex_ast.diff` |
| empty / vague | Ask | clarify the pattern and scope |

If the user described intent in prose ("find all one-arg IO.inspect"), translate it to a
pattern first (see the `ex-ast` skill's pattern table) and echo the pattern you'll run.

## Step 2: Search

```bash
mix ex_ast.search 'IO.inspect(_)' lib/        # scope to a path when known
mix ex_ast.search 'Repo.get(_, _)' --json     # --json when piping results
```

Report `file:line` matches grouped sensibly. If zero matches, say so plainly — for
verification sweeps a zero-match result is a valid, meaningful answer.

## Step 3: Refactor (preview → apply)

```bash
# 1. PREVIEW — no files changed
mix ex_ast.replace 'IO.inspect(expr, _)' 'Logger.debug(inspect(expr))' lib/

# 2. Show the plan, confirm, THEN apply
mix ex_ast.replace 'IO.inspect(expr, _)' 'Logger.debug(inspect(expr))' lib/ --apply
```

Captures (`expr`) carry from pattern to replacement. Surface any conflicts the plan
reports; never apply over unresolved conflicts.

## Step 4: Diff

```bash
mix ex_ast.diff lib/old.ex lib/new.ex
```

Syntax-aware — quieter than `git diff` for refactors that move code. Use it to confirm a
change altered only the intended structure.

## Step 5: Verify (after any apply)

Scope to changed files when possible:

```bash
mix format $(git diff --name-only --diff-filter=d | grep '\.exs\?$')
mix compile --warnings-as-errors
mix test
```

Only claim done when these pass (Iron Law #22). Hand the user a re-runnable structural
check too, e.g. "`mix ex_ast.search 'IO.inspect(_, label: _)'` now returns 0 matches."

## Usage

1. `/phx:ast-search 'IO.inspect(_)'` — find all one-arg debug inspects
2. `/phx:ast-search 'IO.inspect(expr, _)' 'Logger.debug(inspect(expr))' lib/` — preview a
   rewrite, confirm, apply, verify
3. `/phx:ast-search diff lib/a.ex lib/b.ex` — structural diff
