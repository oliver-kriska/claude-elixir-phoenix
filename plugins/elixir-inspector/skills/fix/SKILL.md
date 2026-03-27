---
name: ei:fix
description: >
  Implement the highest-ROI Inspector finding directly in your Elixir project — creates Credo
  checks in lib/, adds CI steps, appends Ecto and architecture rules to CLAUDE.md. Use after
  /ei:scan when the user says fix the top issue, implement the finding, apply the quick win,
  fix it, or wants to go from scan analysis to action immediately.
effort: medium
argument-hint: "[finding-id]"
---

# Inspector Fix — Apply Highest-ROI Finding

Generate AND apply fixes directly to your project from scan findings.

Unlike `/ei:apply` (which stages artifacts in `.claude/inspector/generated/`),
`/ei:fix` writes directly to project files — Credo checks into `lib/`,
CI steps into workflows, rules into `CLAUDE.md`.

## Usage

```
/ei:fix              # Interactive menu — pick findings to fix
/ei:fix L3-001       # Fix a specific finding by ID
/ei:fix --top 3      # Fix the top 3 by ROI score
/ei:fix --all        # Fix all automatable findings (batch)
```

## Iron Laws

1. **ALWAYS show what will be changed before doing it** — present the plan, wait for confirmation
2. **ALWAYS verify changes compile** — `mix compile` for .ex files, syntax check for .sh
3. **NEVER delete existing code** — only add new files or append to existing ones
4. **Reference the finding ID** — in generated `@moduledoc`, comments, and commit message

## Workflow

### Step 1: Load Findings

Read `.claude/inspector/report.md` and `.claude/inspector/findings-merged.json`.
If not found: "No scan results. Run `/ei:scan` first."

Sort findings by `roi_score` (fallback to `priority_score` if `roi_score` absent).

### Step 2: Select Findings (Interactive)

Parse `$ARGUMENTS`:

- **Finding ID** (e.g., `L3-001`): fix that specific finding.
- **`--top N`**: fix top N findings by ROI.
- **`--all`**: fix all automatable findings (batch mode).
- **No arguments**: show interactive menu.

**Interactive menu (default — no arguments)**:

Present the top 10 findings grouped by category with ROI scores:

```
Inspector found {N} automatable findings. What would you like to fix?

## Security (3 findings, ROI: 172 combined)
  1. [L4-01] Unguarded handle_event — 60 violations (ROI: 27)
  2. [L3-02] No CSRF in API endpoints — 8 routes (ROI: 18)
  3. [L6-05] Repo calls in web layer — 30 violations (ROI: 15)

## Code Quality (4 findings, ROI: 89 combined)
  4. [L1-03] Commit-lint enforcement — 91% unstructured (ROI: 127)
  5. [L3-07] Missing @moduledoc — 11 modules (ROI: 22)
  6. [L3-09] Hardcoded strings — 50 instances (ROI: 16)
  7. [L4-05] Logger.error → ErrorReporter — 339 calls (ROI: 12)

## Architecture (2 findings, ROI: 45 combined)
  8. [L6-01] God module split — 1317 lines (ROI: 25)
  9. [L6-03] Circular dependency — 96 nodes (ROI: 20)

Options:
  a) Fix ALL automatable findings (9 artifacts)
  b) Fix top 3 by ROI (#4, #1, #8)
  c) Fix a category (e.g., "security")
  d) Pick specific numbers (e.g., "1, 4, 5")
  e) Fix just the #1 finding
```

Use AskUserQuestion for the selection. Then proceed to Step 3 for each selected finding.

### Step 3: Present Fix Plan

For each selected finding, show a preview:

```markdown
## Fixing: L3-001 — Unguarded handle_event callbacks [HIGH, ROI: 69]

This will:
1. Create Credo check: lib/{app}/credo/authorize_handle_event.ex
2. Update .credo.exs to include the new check
3. Verify it compiles (mix compile)

Proceed? [Y/n]
```

Wait for user confirmation before writing any files.

### Step 4: Implement Based on Artifact Type

Read finding `artifact_types` array. For each type:

**credo-check**:

1. Determine target directory:
   - If `lib/{app}/credo/` exists, use that
   - Else if `lib/mix/credo/` exists, use that
   - Else create `lib/{app}/credo/` (where `{app}` is from `mix.exs` `:app`)
2. Generate the `.ex` file with `@moduledoc` referencing finding ID
3. If `.credo.exs` exists, add the check to its `checks:` list
4. Run `mix compile` — if it fails, fix and retry once
5. Run `mix credo --files-included={generated_file}` to show what it catches

**ci-step**:

1. Generate the script content
2. Determine target:
   - If `.github/workflows/` exists: suggest adding step to existing CI workflow
   - If `scripts/` exists: write to `scripts/{script_name}.sh`
   - Else create `scripts/{script_name}.sh`
3. Make executable: `chmod +x`
4. Run `bash -n {script}` to syntax-check

**claude-md-rule**:

1. Generate the rule text with finding ID reference
2. Target: project `CLAUDE.md` (or `AGENTS.md` if project uses that)
3. Append under an `## Inspector Rules` section (create section if missing)
4. Show the appended content

**skill**:

1. Generate `SKILL.md` content
2. Write to `.claude/skills/{skill-name}/SKILL.md`
3. Create `references/` if the skill needs detailed patterns

### Step 5: Verify and Report

Run `mix compile` for .ex files, `bash -n` for .sh files.

Present completion summary with table of created/updated files and status.
Include cross-references to other findings this fix helps resolve.
Suggest a commit message referencing the finding ID.

### Error Recovery

If `mix compile` fails after generating a Credo check:

1. Read the error, fix the generated file (common: missing imports, wrong module path)
2. Retry compilation once
3. If still failing: revert the file, report failure, suggest `/ei:apply` for manual review

## References

- `${CLAUDE_SKILL_DIR}/../apply/references/credo-template.md` — Template for Credo check generation
- `${CLAUDE_SKILL_DIR}/../scan/references/finding-schema.md` — Finding YAML frontmatter format
