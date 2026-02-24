# Common Entropy Patterns

Typical quality drift scenarios and recovery strategies.

## Pattern: Warning Creep

**Symptom**: Compile warnings slowly increase (0 → 3 → 7 → 12).
**Cause**: New code added without `--warnings-as-errors` check.
**Recovery**: Run `mix compile --warnings-as-errors`, fix all.
**Prevention**: PostToolUse hook already catches this per-file.

## Pattern: Credo Debt Accumulation

**Symptom**: Credo violations grow despite individual file checks.
**Cause**: New modules added without Credo review; complexity
grows in existing modules as features are added.
**Recovery**: `mix credo --strict` → fix priority A and B issues.
**Prevention**: Phase-level Credo check during `/phx:work`.

## Pattern: Circular Dependency Introduction

**Symptom**: `mix xref graph --format cycles` shows new cycles.
**Cause**: Module A imports Module B, which imports Module A
(often through context function calls).
**Recovery**: Extract shared functions to a third module.
**Prevention**: `/phx:boundaries` check after refactoring.

## Pattern: Test Coverage Erosion

**Symptom**: Test count stays flat while module count grows.
**Cause**: New features added without corresponding tests.
**Recovery**: Run `/phx:review test` to identify untested code.
**Prevention**: Plan template requires test tasks for each phase.

## Pattern: Dead Code Accumulation

**Symptom**: Unreachable function count grows.
**Cause**: Refactoring replaces functions but doesn't remove old.
**Recovery**: `mix xref unreachable` → delete unreachable functions.
**Prevention**: Review agent flags unused functions.

## Pattern: Context Boundary Erosion

**Symptom**: Contexts start calling each other's internal functions.
**Cause**: "Quick fix" shortcuts that bypass context boundaries.
**Recovery**: `/phx:boundaries` audit → refactor cross-context calls.
**Prevention**: Iron Laws + boundary checks in review.

## Recovery Strategies by Status

| Status | Strategy |
|--------|----------|
| HEALTHY | None — save baseline if metrics improved |
| DEGRADED | `/phx:audit --gc` for 2-3 minute targeted cleanup |
| CRITICAL | `/phx:audit --full` for comprehensive analysis + plan |
