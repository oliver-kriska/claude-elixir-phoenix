---
name: ei:apply
description: >
  Generate concrete enforcement artifacts from Inspector scan findings — custom Credo checks
  (.ex files that compile and drop into lib/), Claude Code skills, CLAUDE.md Iron Laws, CI/CD
  shell scripts, and code review prompts in 3 formats (human checklist, Claude system prompt,
  GitHub Actions YAML). Requires prior /ei:scan run. Use when the user says generate artifacts,
  create credo checks, apply the findings, turn findings into rules, generate enforcement, create
  CI steps, or after reviewing scan results and wanting to act on them. Also use when user asks
  now what after a scan.
argument-hint: "[--pick|--credo|--skills|--ci|--review|--claude-md|--all]"
---

# Inspector Apply — Generate Artifacts

Transform scan findings into concrete, usable artifacts.

## Usage

```
/ei:apply             # Generate all artifact types (default)
/ei:apply --pick      # Interactive: choose which artifact types to generate
/ei:apply --credo     # Only Credo checks
/ei:apply --skills    # Only Claude Code skills
/ei:apply --ci        # Only CI/CD scripts
/ei:apply --review    # Only code review prompts
/ei:apply --claude-md # Only CLAUDE.md rules
```

## Prerequisites

Must have `.claude/inspector/report.md` from prior `/ei:scan`.

## Iron Laws

1. **NEVER write to project lib/ or .claude/skills/** — all output to `.claude/inspector/generated/`
2. **Validate Credo checks compile** — run `mix compile` on generated .ex files
3. **Report must exist** — refuse to run without prior scan
4. **One agent per artifact type** — parallel generation

## Workflow

### Step 1: Load Findings

Read `.claude/inspector/report.md` and `.claude/inspector/findings-merged.json`.
If not found: "No scan results. Run `/ei:scan` first."

Count findings by artifact_type to preview what will be generated.

### Step 2: Select Artifacts (if --pick)

If `--pick` flag, use AskUserQuestion:

```
"Your scan found findings suggesting these artifacts:
- 8 Credo checks (from 12 findings)
- 5 Claude Code skills (from 8 findings)
- 4 CI/CD scripts (from 6 findings)
- 3 CLAUDE.md rule sections (from 15 findings)
- Code review prompts in 3 formats (from all findings)

Which would you like to generate?"

Options: [All (recommended), Credo checks only, Skills only, Let me pick individually]
```

### Step 3: Spawn Generator Agents (Parallel)

For each selected artifact type, spawn a generator agent:

```
Agent(subagent_type="elixir-inspector:credo-generator", ...)
Agent(subagent_type="elixir-inspector:skill-generator", ...)
Agent(subagent_type="elixir-inspector:claudemd-generator", ...)
Agent(subagent_type="elixir-inspector:cicd-generator", ...)
Agent(subagent_type="elixir-inspector:review-prompt-generator", ...)
```

Each agent reads the merged findings JSON and generates its artifact type.
All run in background, wait for all to complete.

### Step 4: Validate Generated Artifacts

After all agents complete:

```bash
# Validate Credo checks compile (if generated)
if [ -d ".claude/inspector/generated/credo-checks" ]; then
  # Copy to temp location within project, try mix compile
  echo "Validating Credo checks..."
fi
```

### Step 5: Present Results

```markdown
## Generated Artifacts

| Type | Files | Location |
|------|-------|----------|
| Credo checks | 8 .ex files | .claude/inspector/generated/credo-checks/ |
| Skills | 5 SKILL.md files | .claude/inspector/generated/skills/ |
| CLAUDE.md rules | 1 file | .claude/inspector/generated/claude-md-rules.md |
| CI scripts | 4 scripts | .claude/inspector/generated/ci-scripts/ |
| Review prompts | 3 files | .claude/inspector/generated/review-prompts/ |

### How to Adopt

**Credo checks**: Copy .ex files to `lib/your_app/credo/` and update `.credo.exs`
**Skills**: Copy to `.claude/skills/`
**CLAUDE.md rules**: Append to your project's `CLAUDE.md`
**CI scripts**: Add to your CI/CD pipeline configuration
**Review prompts**: Use `checklist.md` for any tool, `claude-system.md` for Claude API
```

## Output Directory

```
.claude/inspector/generated/
├── credo-checks/
│   ├── enforce_gettext_in_heex.ex
│   ├── no_repo_calls_in_web.ex
│   └── ...
├── skills/
│   ├── domain-naming/SKILL.md
│   ├── test-conventions/SKILL.md
│   └── ...
├── ci-scripts/
│   ├── check-translations.sh
│   ├── check-boundaries.sh
│   └── ...
├── review-prompts/
│   ├── checklist.md
│   ├── claude-system.md
│   └── github-actions.yml
├── claude-md-rules.md
└── iron-laws.md
```

## References

- `references/credo-template.md` — Template for Credo check generation
- `references/skill-template.md` — Template for skill generation
