# ex_ast CLI Tasks & Programmatic API

Three mix tasks plus a programmatic API. The tasks are the fast path for ad-hoc work;
the API is for building checks, batch sweeps, or custom tooling.

> Flags below reflect the documented surface. ex_ast moves quickly — if a flag is
> rejected, run the task with `--help` (e.g. `mix help ex_ast.search`) to confirm the
> exact option name for the installed version, then proceed.

## `mix ex_ast.search`

Locate every structural match of a pattern.

```bash
# basic search across the default paths (lib/)
mix ex_ast.search 'IO.inspect(_)'

# scope to specific paths
mix ex_ast.search 'Repo.get(_, _)' lib/my_app/accounts

# machine-readable output for piping into other tools
mix ex_ast.search 'IO.inspect(_)' --json

# show surrounding lines for context
mix ex_ast.search 'IO.inspect(_)' --context
```

Output lists `file:line` for each match (and captured bindings when the pattern names
them). `--json` emits structured results (path, line, captures) suitable for
post-processing.

## `mix ex_ast.replace`

Rewrite matches. **Default is preview** — it shows the planned changes. Pass `--apply`
to write to disk. This two-phase design is the safe path; honor Iron Law #2.

```bash
# PREVIEW (no files changed) — always do this first
mix ex_ast.replace 'IO.inspect(expr, _)' 'Logger.debug(inspect(expr))' lib/

# APPLY after reviewing the preview
mix ex_ast.replace 'IO.inspect(expr, _)' 'Logger.debug(inspect(expr))' lib/ --apply
```

Captures from the search pattern (`expr` above) are substituted into the replacement.
The replacement is itself plain Elixir. Conflicting/overlapping rewrites are surfaced in
the plan rather than silently applied.

After `--apply`, run the project formatter and verification (`mix format`, `mix compile
--warnings-as-errors`, `mix test`) — a structural rewrite is not "done" until it compiles
and tests pass (Iron Law #22).

## `mix ex_ast.diff`

Syntax-aware diff between two files. Understands code *movement* and structural change,
not just changed lines, so it is quieter than `git diff` for refactors that move code.

```bash
mix ex_ast.diff lib/old.ex lib/new.ex
```

Use it to confirm a refactor changed only what you intended structurally.

## Programmatic API

For batch checks and custom tooling. Parse source with `Code.string_to_quoted/1` (or read
via the library's helpers), then match.

| Module / function | Purpose |
|-------------------|---------|
| `ExAST.Patcher.find_all/2` | All matches of one pattern in an AST |
| `ExAST.Patcher.find_many/2` | Match many patterns in one pass (batch checks) |
| `ExAST.Rewriter` / `ExAST.rewrite_plan/3` | Build a replacement plan, inspect before applying |
| `ExAST.Query` (`from/1`, `where/1`) | SQL-like filtering with capture guards |
| `ExAST.Selector` (`find_all/3`, `match?/3`) | CSS-like selector builder over the AST |
| `ExAST.Pattern` | Compile a pattern (also `ExAST.CompiledPattern`) |
| `ExAST.Symbols` (`definitions/1`, `references/1`, `qualified_name/1`) | Extract defs/refs |
| `ExAST.Comments` (`extract/1`, `associated/3`) | Comments with position + association |
| `ExAST.Diff` | Syntax-aware diff programmatically |
| `ExAST.Index.plan/1` | Advisory candidate-index metadata for narrowing search |
| `ExAST.Sigil` (`~p`) | Compile-time pattern parsing |

### Example: batch structural lint

```elixir
patterns = [
  ~p"IO.inspect(_)",
  ~p"IO.inspect(_, _)",
  ~p"String.to_atom(_)"
]

{:ok, ast} = Code.string_to_quoted(File.read!(path))
ExAST.Patcher.find_many(ast, patterns)
# => matches grouped by pattern, with file/line + captures
```

### Example: rewrite with preview

```elixir
plan = ExAST.rewrite_plan(ast, ~p"IO.inspect(expr, _)", ~p"Logger.debug(inspect(expr))")
# inspect `plan` (matches + conflicts) BEFORE applying
```

## Indexing (large codebases)

`ExAST.Index.plan/1` exposes advisory metadata an external indexer can use to *narrow*
the candidate file set before ex_ast verifies matches semantically. The pattern: a cheap
text index proposes candidates, ex_ast confirms structurally. Useful when scanning very
large trees where parsing every file is wasteful.

## Relationship to existing plugin tools

- **`mix xref callers`** finds *who calls* a function (cross-module graph). **ex_ast**
  finds *call sites by structure/arity* within files. They complement each other — xref
  for the dependency graph, ex_ast for the precise shape at each site.
- **`grep`** stays correct for strings, comments, and non-Elixir files. Use ex_ast the
  moment the query depends on Elixir structure.
- Supersedes the proof-of-concept Sourceror snippet in
  `call-tracing/references/argument-extraction.md` for real argument extraction.
