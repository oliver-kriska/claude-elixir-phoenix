# Entropy Metrics Glossary

What each metric means, how it's measured, and healthy ranges.

## Compile Warnings

**Command**: `mix compile --warnings-as-errors 2>&1 | grep -c "warning:"`

**What it measures**: Elixir compiler warnings — unused variables,
deprecated functions, unreachable clauses, type issues.

**Healthy range**: 0
**Why it matters**: Warnings accumulate silently. Each one is
technical debt. With `--warnings-as-errors`, they become errors.

## Credo Violations

**Command**: `mix credo --strict --format json | jq '.issues | length'`

**What it measures**: Code quality issues — complexity, naming,
consistency, potential bugs.

**Healthy range**: ≤5 (project-dependent)
**Why it matters**: Credo catches patterns that make code harder
to maintain: deep nesting, long functions, inconsistent naming.

## Circular Dependencies

**Command**: `mix xref graph --format cycles | grep -c "Cycle"`

**What it measures**: Modules that depend on each other in a cycle.

**Healthy range**: 0
**Why it matters**: Circular deps cause compile-time issues,
make refactoring harder, and indicate poor module boundaries.

## Test Count and Failures

**Command**: `mix test --trace 2>&1 | tail -5`

**What it measures**: Total tests and failures.

**Healthy range**: 0 failures, growing test count
**Why it matters**: Decreasing test count means coverage regression.
Failures mean broken code.

## Dead Code (Unreachable)

**Command**: `mix xref unreachable | grep -c "is unreachable"`

**What it measures**: Functions defined but never called.

**Healthy range**: ≤3
**Why it matters**: Dead code adds confusion and maintenance burden.

## Module Count

**Command**: `find lib/ -name "*.ex" | wc -l`

**What it measures**: Total Elixir source files.

**Healthy range**: Project-dependent (track trend, not absolute)
**Why it matters**: Rapid growth may indicate poor abstraction.
Sudden drops may indicate accidental deletion.
