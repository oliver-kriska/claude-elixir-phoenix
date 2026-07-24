# Security

This plugin ships skills, agents, and hooks that run inside Claude Code with
your tool permissions. You should be able to verify it's safe before installing.
This document records an independent security scan and how to reproduce it.

## Independent scan: NVIDIA SkillSpector

Every distributed skill and agent is scanned with
[NVIDIA SkillSpector](https://github.com/NVIDIA/SkillSpector) — an open-source
(Apache-2.0) security scanner for AI-agent skills that checks 64 vulnerability
patterns across 16 categories (prompt injection, data exfiltration, privilege
escalation, supply chain, excessive agency, tool misuse, and more).

We run it **static-only (`--no-llm`)**, so the scan sends nothing off your
machine — no skill or agent content leaves the local process.

### Reproduce it yourself

```bash
pipx install --python python3.13 "git+https://github.com/NVIDIA/skillspector.git"
lab/skillspector/scan.sh        # scans all 77; exit 0 = baseline-aware gate passes
```

Or scan any single component directly:

```bash
skillspector scan plugins/elixir-phoenix/skills/work/ --no-llm
```

## Results

Raw results without reviewed baselines, using SkillSpector v2.x static analysis:

| Tier | Skills | Agents | Total |
|------|-------:|-------:|------:|
| SAFE (score 0–20)     | 42 | 24 | **66 / 77** |
| CAUTION (21–50)       |  6 |  1 |  7 |
| DO_NOT_INSTALL (51+)  |  3 |  1 |  4 |

The 4 `DO_NOT_INSTALL` components are **documented false positives** — the scanner
is a static regex/AST tool, so it's negation-blind and context-blind: it matches
a dangerous keyword without seeing the prohibition or detection-context around
it. Each is recorded in a reviewed baseline under
[`lab/skillspector/baselines/`](lab/skillspector/baselines/); after baselines
**the repository scan reports 0 components flagged and exits 0**. The 7
`CAUTION`-tier components (scores 21–32, all below the 51 `DO_NOT_INSTALL`
threshold) stay `CAUTION` and are not baselined — they are documented below.

### Triage of flagged components

| Component | Flag | Actual line | Why it's a false positive |
|-----------|------|-------------|---------------------------|
| `skills/quick` | `bypass security` (P1/RA1, conf 0.9) | `SKILL.md:43` → **"NEVER bypass security checks for speed"** | The line *forbids* it. Scanner matched the keyword, not the `NEVER`. |
| `skills/quick` | `skip verification` (EA2) | `SKILL.md:41` → **"NEVER skip verification"** | Same negation-blindness. |
| `skills/permissions` | `chmod 777`, `git push --force` (TM1/PE2) | `SKILL.md:25` → **"NEVER auto-allow RED — `rm`, `sudo`, … `chmod 777`"** | A risk table of commands the skill tells Claude to *refuse to allow*. |
| `skills/permissions` | `~/.claude/settings.json` (AS1 "agent snooping") | by design | The skill's job is to help you configure Claude Code's own permission allowlist. |
| `skills/deps-audit` | bidi chars, base64, `rm -rf` (P2/SC3/TM1) | detection signatures + smoke-test fixtures | This skill **is** a Hex supply-chain scanner; it contains the attack patterns it teaches Claude to detect. |
| `agents/ash-policy-reviewer` | `bypass policy` (AR3/YR4, conf 0.9) | `.md:34,49` | `bypass` is the Ash policy DSL keyword *and* the audit target ("undocumented bypass is a critical finding"). |

In short: the components that score "worst" are precisely the ones whose job is
to **enforce safety or detect attacks** — they discuss dangerous things in order
to forbid or find them.

### CAUTION-tier components (not baselined)

Seven components land in the `CAUTION` band (21–50). They are left un-baselined —
none crosses the `DO_NOT_INSTALL` threshold — and each is a benign artifact of
the plugin's own workflow design:

| Component | Score | Top flag | Why it's benign |
|-----------|------:|----------|-----------------|
| `skills/work` | 32 | AS1 agent-config access, EA2 autonomous | Reads/writes the plugin's own `.claude/plans/` artifacts and runs the execution phase. |
| `skills/full` | 27 | AS1 agent-config access, EA2 autonomous | Drives the autonomous plan→work→review cycle over `.claude/` artifacts. |
| `agents/ash-resource-designer` | 22 | AR3 anti-refusal | Its "design the Ash Way before hand-rolling" guidance matches the anti-refusal signature. |
| `skills/brief` | 21 | AS1 agent-config access | Reads `.claude/plans/{slug}/plan.md` to explain a plan. |
| `skills/compound` | 21 | RA1 self-modification | Writes solution docs into `.claude/solutions/`. |
| `skills/recall` | 21 | AS1 agent-config access | Reads `.claude/solutions/` and past-session paths for archaeology. |
| `skills/learn-from-fix` | 21 | AS1 agent-config access | Reads project and user Claude guidance to identify and persist a corrected convention. |

The six skill entries legitimately read or write the plugin's own `.claude/`
artifacts, which the scanner treats as generic agent-config access or
self-modification. The agent entry has the separate anti-refusal match shown in
the table.

## What this plugin does and doesn't do

- **No telemetry or covert egress.** Skills and agents are Markdown
  instructions and hooks are local shell scripts. Some workflows may invoke
  visible, user-authorized external services such as GitHub, Hex, web search,
  or configured MCP servers through the host runtime's normal permission model.
- **Hooks are auditable bash.** They format Elixir, verify Iron Laws, and block
  destructive ops (`mix ecto.reset`, `git push --force`, `MIX_ENV=prod`). Read
  them in [`plugins/elixir-phoenix/hooks/`](plugins/elixir-phoenix/hooks/).
- **Agents are read-only by default.** Review/analysis agents have
  `Edit, NotebookEdit` disallowed — they can write their own findings file but
  cannot modify your source.
- **`bypassPermissions` on agents** is required so background subagents don't
  hang on permission prompts; it does not grant them more tools than listed in
  each agent's `tools:` field.

## Reporting a vulnerability

Open a GitHub issue, or for sensitive reports email the maintainer at the
address in the plugin manifest. Please don't disclose exploitable issues in a
public issue before a fix is available.
