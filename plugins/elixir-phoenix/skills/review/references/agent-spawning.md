# Review Agent Spawning Reference

Detailed tables and prompt templates for spawning review specialists.
Referenced by `/phx:review` Step 2.

## Agent Selection Table

| Agent | subagent_type | When to spawn |
|-------|---------------|---------------|
| Elixir Reviewer | `phx:elixir-reviewer` | **Always** |
| Iron Law Judge | `phx:iron-law-judge` | Only if >200 lines changed AND auth/LiveView/Oban files in diff. **Skip** if PostToolUse hooks already verified all files |
| Verification Runner | `phx:verification-runner` | Only if `mix test` has NOT been run in this session. **Skip** if `/phx:work` just passed all verification tiers |
| Security Analyzer | `phx:security-analyzer` | Auth/session/password/token files changed |
| Testing Reviewer | `phx:testing-reviewer` | Test files changed OR new public functions |
| Oban Specialist | `phx:oban-specialist` | Worker files changed (*_worker.ex) |
| Deploy Validator | `phx:deployment-validator` | Dockerfile/fly.toml/runtime.exs changed |
| Requirements Verifier | `phx:requirements-verifier` | Task ID detected OR plan/spec path passed (Step 1c succeeded). **Skip** on `--no-requirements` |
| Codex Reviewer | `phx:codex-reviewer` | **ONLY when `--codex` passed** — never in default selection. Does not count toward the max-5 cap |

Min 1, max 5 agents. For <200 lines changed: spawn only elixir-reviewer +
security-analyzer (if auth files).

## Output File Mapping

Every agent prompt MUST include an explicit `output_file` path.

| Agent | output_file |
|-------|-------------|
| elixir-reviewer | `.claude/plans/{slug}/reviews/elixir.md` |
| testing-reviewer | `.claude/plans/{slug}/reviews/testing.md` |
| iron-law-judge | `.claude/plans/{slug}/reviews/iron-laws.md` |
| security-analyzer | `.claude/plans/{slug}/reviews/security.md` |
| oban-specialist | `.claude/plans/{slug}/reviews/oban.md` |
| deployment-validator | `.claude/plans/{slug}/reviews/deploy.md` |
| verification-runner | `.claude/plans/{slug}/reviews/verification.md` |
| requirements-verifier | `.claude/plans/{slug}/reviews/requirements.md` |
| codex-reviewer | `.claude/plans/{slug}/reviews/codex.md` |

## Standard Prompt Block

Include this instruction block in every agent prompt:

```
output_file: .claude/plans/{slug}/reviews/{agent}.md

CRITICAL: Write your findings to the output_file above. By turn ~12 at the
latest, call Write with whatever you have — partial is better than nothing
if you hit the turn limit. Continue analyzing and Write again to overwrite
with the full version. Your chat response body must be ≤300 words — the
file IS the real output.
```

## Codex Reviewer Prompt Block (`--codex` only)

Spawn `phx:codex-reviewer` in the SAME parallel batch as the
other agents with this prompt (plus the Standard Prompt Block above):

```
Run a Codex CLI review of this diff and normalize the findings.

base_branch: {default branch, e.g. main}
diff_files: {git diff --name-only output}
output_file: .claude/plans/{slug}/reviews/codex.md

Preflight `command -v codex` first. If codex is missing or the review
fails, write output_file with a SKIPPED note and stop — NEVER error.
Do not pass custom instructions with --base (CLI rejects it); the rubric
comes from the project's AGENTS.md "Review guidelines" section.
Normalize P0/P1→BLOCKER, P2→WARNING, P3→SUGGESTION. Tag every finding
with source [codex].
```

The codex review takes 1–5+ minutes — spawn it FIRST in the batch so it
overlaps the Claude agents. In Step 3b, mark issues flagged by both a
Claude agent and `[codex]` as HIGH CONFIDENCE (cross-model consensus).

## Focused Review Mode

When the user passes a focus argument, spawn only the specified agent:

| Argument | subagent_type |
|----------|---------------|
| `test` | `phx:testing-reviewer` |
| `security` | `phx:security-analyzer` |
| `oban` | `phx:oban-specialist` |
| `deploy` | `phx:deployment-validator` |
| `iron-laws` | `phx:iron-law-judge` |

Zero agents spawned = skill failure.
