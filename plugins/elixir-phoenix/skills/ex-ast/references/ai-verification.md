# Structural Verification of AI-Generated Code

ex_ast exists, in large part, to **check AI-generated Elixir**. Text diffs and regex
can't tell `IO.inspect(data)` from `IO.inspect(data, label: "debug")`, or a real guard
from an always-true one. Structural search can. Use these sweeps before claiming a change
is done (Iron Law #22) — especially after generating or refactoring code.

## When to run a structural sweep

- After generating a new module or sizable function
- After a `mix ex_ast.replace --apply` or any bulk refactor
- During `/phx:review` or `/phx:verify` on changed files
- Before opening a PR

Scope the sweep to changed files when possible:

```bash
mix ex_ast.search 'IO.inspect(...)' $(git diff --name-only --diff-filter=d | grep '\.exs\?$')
```

## Slop patterns to catch

### Debug leftovers

```bash
mix ex_ast.search 'IO.inspect(...)'      # any arity, piped or not
mix ex_ast.search 'IO.puts(...)'
mix ex_ast.search 'dbg(...)'
```

These are the single most common AI/codegen leftover. The existing
`debug-statement-warning.sh` hook catches edits; ex_ast catches them in bulk across an
already-written tree.

### Always-true / always-false comparisons

Structurally detect comparisons where both sides are the same captured node, or a literal
compared to itself:

```bash
mix ex_ast.search 'x == ^x'              # tautology
mix ex_ast.search 'x != ^x'              # always false
```

### Negative literal where a positive is expected

```bash
mix ex_ast.search 'Enum.take(_, -1)'     # often a generation slip
mix ex_ast.search 'String.slice(_, -1, _)'
```

### Compile-time config read in a function body

Reading config at compile time inside runtime code is a classic codegen mistake. Search
for `Application.compile_env` / `Application.get_env` used where a runtime fetch belongs,
then review each hit:

```bash
mix ex_ast.search '@_ Application.compile_env(_, _)'
mix ex_ast.search 'Application.get_env(_, _)'
```

### Unscoped or unpinned query interpolation

Pair with the Ecto Iron Laws — surface query calls that may interpolate user input
instead of pinning (`^`). ex_ast finds the call sites; you confirm each pins its values:

```bash
mix ex_ast.search 'Repo.all(_)'
mix ex_ast.search 'from(_ in _, where: _)'
```

## Batch lint via `find_many/2`

One pass, many patterns — cheaper than N searches and easy to wire into a custom mix task
or test:

```elixir
slop = [
  ~p"IO.inspect(...)",
  ~p"IO.puts(...)",
  ~p"dbg(...)",
  ~p"String.to_atom(_)",
  ~p"Enum.take(_, -1)"
]

for path <- Path.wildcard("lib/**/*.ex"),
    {:ok, ast} = Code.string_to_quoted(File.read!(path)),
    {pattern, matches} <- ExAST.Patcher.find_many(ast, slop),
    match <- matches do
  IO.puts("#{path}: #{inspect(pattern)} @ line #{match.line}")
end
```

## Verify intended structure (not just text)

After a refactor, assert the result has the shape you intended rather than eyeballing a
text diff. Example: confirm every old `IO.inspect(x, label: ...)` became `Logger.debug/1`
and none were missed:

```bash
# expect ZERO matches after the rewrite
mix ex_ast.search 'IO.inspect(_, label: _)' lib/
```

A zero-match result *is* the verification. Pair structural confirmation with
`mix compile --warnings-as-errors && mix test` for behavioral confirmation.

## Reviewer note (no-Bash agents)

A read-only reviewer without Bash can't run these tasks, but it can **recommend the exact
command** in its findings — e.g. "run `mix ex_ast.search 'IO.inspect(...)'` to confirm no
debug leftovers." That hands the user (or the verify step) a precise, runnable check.
