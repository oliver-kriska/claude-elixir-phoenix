# ex_ast Pattern Language

Patterns are **plain Elixir source**. ex_ast parses your pattern to AST and matches
it against the AST of target files. No regex, no custom DSL — if it parses as Elixir,
it is a valid pattern. Structure matches structure, so argument count, pipe form, and
data shape all matter (unless you opt out with a wildcard).

## Core matchers

### Wildcard / capture: `_` and bare names

`_` matches any single node and discards it. A **bare variable name** matches any node
and *captures* it under that name (available in replacements and query guards).

```elixir
# matches any one-arg IO.inspect call
mix ex_ast.search 'IO.inspect(_)'

# captures the inspected expression as `expr`
mix ex_ast.search 'IO.inspect(expr)'
```

`IO.inspect(_)` does **not** match `IO.inspect(x, label: "debug")` — that call has two
arguments. Arity is structural.

### Pin: `^name`

`^name` matches a *specific* value (a literal, or a name already bound earlier in the
pattern) rather than capturing freely. Use it to require the same value in two places.

```elixir
# assignment where both sides reference the same captured var
mix ex_ast.search 'x = f(^x)'
```

### Ellipsis: `...`

`...` matches **variable arity** (zero or more arguments) or a **run of contiguous
nodes** (multiple statements in a block). Use it when the argument count varies.

```elixir
# Logger.info with any number of args
mix ex_ast.search 'Logger.info(...)'

# any call to MyApp.Mailer.deliver regardless of arity
mix ex_ast.search 'MyApp.Mailer.deliver(...)'
```

Contrast with `_`, which is exactly one node.

### Pipe normalization

ex_ast normalizes pipes, so a piped expression and the equivalent nested call match the
**same** pattern. You don't have to write the pattern twice.

```elixir
# this pattern...
mix ex_ast.search 'Enum.map(list, f)'

# ...matches BOTH:
Enum.map(list, f)
list |> Enum.map(f)
```

### Partial struct / map matching

Structs and maps match **partially** — the pattern lists only the keys you care about;
extra keys in the target are ignored.

```elixir
# matches %User{role: :admin, name: "x", inserted_at: ...}
mix ex_ast.search '%User{role: :admin}'

# map with at least a :name key
mix ex_ast.search '%{name: name}'
```

## Form coverage

Patterns work across all common Elixir forms:

| Form | Example pattern |
|------|-----------------|
| Function call | `Enum.map(_, _)`, `Logger.info(...)` |
| Definition | `def handle_call(msg, _, state) do _ end` |
| Pipe (normalized) | `data \|> Enum.map(f)` |
| Tuple / data | `{:ok, result}`, `{:error, reason}` |
| Struct | `%User{role: :admin}` |
| Map | `%{name: name}` |
| Directive | `use GenServer`, `import Ecto.Query` |
| Module attr | `@cfg Application.compile_env(_, _)` |
| Control flow | `case _ do _ -> _ end`, `with _ <- _ do _ end` |
| Anonymous fn | `fn _ -> _ end` |

## Function-name capture

You can capture the **name** of a defined or called function:

```elixir
# capture every public function name in a module
mix ex_ast.search 'def name(_)'
```

Combine with `ExAST.Query` guards (see `cli-tasks.md`) to filter captures, e.g. keep
only names matching a prefix.

## The `~p` sigil (compile-time patterns)

For programmatic use, `ExAST.Sigil` provides `~p` to parse a pattern once at compile
time instead of re-parsing a string at runtime:

```elixir
import ExAST.Sigil

pattern = ~p"IO.inspect(_)"
ExAST.Patcher.find_all(source_ast, pattern)
```

## Mental model

1. **Write the code you'd be looking for**, then replace the parts you don't care about
   with `_` (one node) or `...` (variable run).
2. **Pin** (`^`) when two positions must hold the same value.
3. **Lean on normalization** — pipes and partial structs mean one pattern covers the
   variations you'd otherwise enumerate by hand.
4. **Arity is real** — if you want "any number of args", say `...`; `_` is exactly one.
