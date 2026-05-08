# Review Agent Spawning Reference

Detailed tables and prompt templates for spawning review specialists.
Referenced by `/phx:review` Step 2.

## Agent Selection Table

| Agent | subagent_type | When to spawn |
|-------|---------------|---------------|
| Elixir Reviewer | `elixir-phoenix:elixir-reviewer` | **Always** |
| Iron Law Judge | `elixir-phoenix:iron-law-judge` | Only if >200 lines changed AND auth/LiveView/Oban files in diff. **Skip** if PostToolUse hooks already verified all files |
| Verification Runner | `elixir-phoenix:verification-runner` | Only if `mix test` has NOT been run in this session. **Skip** if `/phx:work` just passed all verification tiers |
| Security Analyzer | `elixir-phoenix:security-analyzer` | Auth/session/password/token files changed |
| Testing Reviewer | `elixir-phoenix:testing-reviewer` | Test files changed OR new public functions |
| Oban Specialist | `elixir-phoenix:oban-specialist` | Worker files changed (*_worker.ex) |
| Deploy Validator | `elixir-phoenix:deployment-validator` | Dockerfile/fly.toml/runtime.exs changed |
| Requirements Verifier | `elixir-phoenix:requirements-verifier` | Task ID detected OR plan/spec path passed (Step 1c succeeded). **Skip** on `--no-requirements` |

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

## Focused Review Mode

When the user passes a focus argument, spawn only the specified agent:

| Argument | subagent_type |
|----------|---------------|
| `test` | `elixir-phoenix:testing-reviewer` |
| `security` | `elixir-phoenix:security-analyzer` |
| `oban` | `elixir-phoenix:oban-specialist` |
| `deploy` | `elixir-phoenix:deployment-validator` |
| `iron-laws` | `elixir-phoenix:iron-law-judge` |

Zero agents spawned = skill failure.
