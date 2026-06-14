---
name: ex-ast
description: "Structural AST search/replace/diff for Elixir via ex_ast. Use when finding, refactoring, or verifying Elixir code by structure (arity, pipe form, call shape) instead of grep/regex."
effort: medium
user-invocable: false
---

# ex_ast — Structural AST Tooling

Search, replace, and diff Elixir code by **AST pattern**, not text. Patterns are
plain Elixir, so structure matches structure — `IO.inspect(x)` is distinct from
`IO.inspect(x, label: "debug")`. Prefer `ex_ast` over `grep`/`sed` for any
*structural* Elixir query or rewrite when the dep is present.

Library: [elixir-vibe/ex_ast](https://github.com/elixir-vibe/ex_ast) (dev/test only).

## Iron Laws — Never Violate These

1. **DEV/TEST ONLY** — Declare `runtime: false`, `only: [:dev, :test]`. Never a prod dep
2. **PREVIEW BEFORE REPLACE** — Run `mix ex_ast.replace` in dry-run (no `--apply`) or
   `ExAST.rewrite_plan/3` and read the plan BEFORE applying. Never blind-apply a rewrite
3. **AST SEARCH OVER GREP** — For structural queries (arity, pipe form, struct shape,
   call site) use `ex_ast`; reserve `grep` for plain text/strings/comments
4. **VERIFY AI-GENERATED CODE STRUCTURALLY** — Before claiming done (Iron Law #22),
   sweep generated code for structural slop (debug calls, always-true guards). See
   `${CLAUDE_SKILL_DIR}/references/ai-verification.md`

## Quick Reference

| Task | ex_ast | Fallback |
|------|--------|----------|
| Find a call pattern | `mix ex_ast.search 'IO.inspect(_)'` | `grep -rn "IO.inspect"` |
| Find by arity | `mix ex_ast.search 'Repo.get(_, _)'` | (grep can't count args) |
| Preview a rewrite | `mix ex_ast.replace 'old' 'new' lib/` | manual diff |
| Apply a rewrite | `mix ex_ast.replace 'old' 'new' lib/ --apply` | `sed` (unsafe) |
| Structural diff | `mix ex_ast.diff a.ex b.ex` | `git diff` (textual) |
| JSON for tooling | add `--json` | — |
| Programmatic find | `ExAST.Patcher.find_all/2` | `Code.string_to_quoted/1` |

## Pattern Syntax (plain Elixir)

| Syntax | Means | Example |
|--------|-------|---------|
| `_` | wildcard / capture-any | `Enum.map(_, _)` |
| `name` | named capture | `def unquote(name)(_)` → binds `name` |
| `^name` | pin (match a literal/bound value) | `^conn` |
| `...` | variable arity / multi-node run | `Logger.info(...)` |
| pipe-normalized | pipe == nested call | `x \|> f(y)` matches `f(x, y)` |
| partial struct/map | extra keys ignored | `%User{role: :admin}` |

Examples: `case _ do _ -> _ end`, `fn _ -> _ end`, `use GenServer`,
`@cfg Application.compile_env(_, _)`, `{:ok, result}`.

## Setup

```elixir
# mix.exs deps/0
{:ex_ast, "~> 0.12", only: [:dev, :test], runtime: false}
```

If a user asks to find/refactor Elixir by structure and `ex_ast` is absent, offer the
dep line above, then drive the workflow with `/phx:ast-search`.

## When to Reach for ex_ast

- **Refactors**: rename/reshape a call across the codebase safely (preview → apply)
- **Tracing**: find exact call sites by arity/shape (complements `mix xref callers`)
- **Review**: flag structural anti-patterns in AI-generated code
- **Verification**: confirm a generated change has the intended structure, not just text

## References

For detail, see:

- `${CLAUDE_SKILL_DIR}/references/pattern-language.md` — full pattern syntax, worked examples
- `${CLAUDE_SKILL_DIR}/references/cli-tasks.md` — search/replace/diff flags + programmatic API
- `${CLAUDE_SKILL_DIR}/references/ai-verification.md` — structural slop checks for generated code
