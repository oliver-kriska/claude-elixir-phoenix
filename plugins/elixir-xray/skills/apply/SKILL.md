---
name: xray:apply
description: >
  Generate Credo checks, Claude Code skills, CLAUDE.md rules, CI scripts, and
  review prompts from Elixir X-Ray scan findings. Use when asked to generate
  artifacts or turn audit findings into rules. Requires a prior /xray:scan.
effort: medium
argument-hint: "[--pick|--credo|--skills|--ci|--review|--claude-md|--all]"
---

# X-Ray Apply — Generate Artifacts

Transform scan findings into concrete, usable artifacts.

## Usage

```
/xray:apply             # Generate all artifact types (default)
/xray:apply --pick      # Interactive: choose which artifact types to generate
/xray:apply --credo     # Only Credo checks
/xray:apply --skills    # Only Claude Code skills
/xray:apply --ci        # Only CI/CD scripts
/xray:apply --review    # Only code review prompts
/xray:apply --claude-md # Only CLAUDE.md rules
```

## Iron Laws

1. **NEVER write to project lib/ or .claude/skills/** — all output to `.claude/xray/generated/`
2. **Validate Credo checks compile** — run `mix compile` on generated .ex files
3. **Report must exist** — refuse to run without prior scan
4. **One agent per artifact type** — parallel generation

## Workflow

### Step 1: Load Findings

Read `.claude/xray/report.md` and `.claude/xray/findings-merged.json`.
If not found: "No scan results. Run `/xray:scan` first."

Count findings by artifact_type to preview what will be generated.

### Step 2: Select Artifacts (if --pick)

If `--pick` flag, use AskUserQuestion showing count per type: "{N} Credo checks, {M} skills, {K} CI scripts, {J} rules, review prompts". Options: All, Credo only, Skills only, Let me pick.

### Step 3: Spawn Generator Agents (Parallel)

For each selected artifact type, spawn a generator agent:

```
Agent(subagent_type="elixir-xray:credo-generator", ...)
Agent(subagent_type="elixir-xray:skill-generator", ...)
Agent(subagent_type="elixir-xray:claudemd-generator", ...)
Agent(subagent_type="elixir-xray:cicd-generator", ...)
Agent(subagent_type="elixir-xray:review-prompt-generator", ...)
```

Each agent reads the merged findings JSON and generates its artifact type.
Pass `credo-generator` the path to `layers/claude-config.json` too — its
`credo.custom_checks` lists existing checks so duplicates are skipped and
reported as "already enforced by {Module}".
All run in background, wait for all to complete.

### Step 4: Validate and Present Results

Run `mix compile` on generated Credo .ex files. Run `bash -n` on generated CI scripts.

Show summary table with artifact type, file count, and output location.
Include adoption instructions: copy Credo checks to `lib/{app}/credo/`, skills to `.claude/skills/`,
append CLAUDE.md rules, add CI scripts to pipeline, use review prompts with Claude or GitHub Actions.

All output goes to `.claude/xray/generated/` (credo-checks/, skills/, ci-scripts/, review-prompts/, claude-md-rules.md).

## References

- `${CLAUDE_SKILL_DIR}/references/credo-template.md` — Template for Credo check generation
- `${CLAUDE_SKILL_DIR}/references/skill-template.md` — Template for skill generation
