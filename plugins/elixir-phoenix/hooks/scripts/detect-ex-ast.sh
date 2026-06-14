#!/usr/bin/env bash
# SessionStart hook: Detect the ex_ast structural-AST tooling
if [ -f "mix.exs" ] && grep -q ':ex_ast' mix.exs 2>/dev/null; then
  echo "✓ ex_ast detected — ex-ast skill auto-loads for structural Elixir search/refactor"
  echo "  Tasks: mix ex_ast.search 'pattern' | mix ex_ast.replace 'old' 'new' path | mix ex_ast.diff a.ex b.ex"
  echo "  Prefer ex_ast over grep for structural queries (arity, pipe form, struct shape)"
  echo "  ALWAYS preview mix ex_ast.replace (no --apply) before applying. Command: /phx:ast-search"
elif [ -f "mix.exs" ]; then
  echo "○ ex_ast not in deps — for structural AST search/replace add to mix.exs:"
  echo "  {:ex_ast, \"~> 0.12\", only: [:dev, :test], runtime: false}"
fi
