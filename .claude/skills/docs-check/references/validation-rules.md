# Validation Rules

Per-component checklists for validation workers.
Each section is passed ONLY to the subagent responsible for that component type.

## Agent Validation Rules

### Frontmatter Fields

Check each agent `.md` YAML frontmatter against `sub-agents.md` docs.

**Required fields:**

- `name` — lowercase, hyphens only, no spaces
- `description` — must include when to use/delegate guidance

**Optional fields (check valid values if present):**

| Field | Valid Values | Notes |
|-------|-------------|-------|
| `model` | `sonnet`, `opus`, `haiku`, `inherit` | Default: inherit |
| `permissionMode` | `default`, `acceptEdits`, `delegate`, `dontAsk`, `bypassPermissions`, `plan` | |
| `tools` | `Read`, `Write`, `Edit`, `Bash`, `Grep`, `Glob`, `Task`, `WebFetch`, `WebSearch`, `NotebookEdit` | Check docs for new tools |
| `disallowedTools` | Same tool names as `tools` | |
| `maxTurns` | Positive integer | |
| `skills` | List of skill names | Verify referenced skills exist |
| `mcpServers` | Object or list | |
| `hooks` | Object | |
| `memory` | `user`, `project`, `local` | Auto-enables Read/Write/Edit |

**Cross-checks:**

- If `memory` set, agent should have Write access (auto-enabled by memory)
- Review-only agents: `disallowedTools: Write, Edit, NotebookEdit`
- `tools` and `disallowedTools` must not overlap
- Skills in `skills:` must exist in `plugins/elixir-phoenix/skills/`

**Detect changes:**

- Compare field list in docs against fields above
- Flag new fields the plugin doesn't use yet
- Flag fields the plugin uses that docs don't document (potential removal)

### Structural

- Valid markdown with YAML frontmatter (between `---` delimiters)
- Specialist agents: ≤365 lines
- Orchestrator agents (has `Task` in tools): ≤535 lines

## Skill Validation Rules

### Structure

Check each `skills/*/` directory against `skills.md` docs.

**Required:**

- `SKILL.md` exists with `name` in frontmatter

**Frontmatter fields:**

| Field | Required | Notes |
|-------|----------|-------|
| `name` | Yes | Pattern: `phx:{name}` or `{domain}:{name}` |
| `description` | No | Used for auto-loading |
| `argument-hint` | No | Shown in command help |
| `disable-model-invocation` | No | Boolean |

**Forbidden:** `triggers:` — MUST NOT be present.

**Detect changes:** New frontmatter fields, changed structure conventions.

### Structural

- SKILL.md: ≤185 lines
- references/*.md: ≤350 lines each

## Hook Validation Rules

### Schema

Check `hooks/hooks.json` against `hooks.md` docs.

**Structure:**

```json
{ "hooks": { "EventName": [{ "matcher": "", "hooks": [{ "type": "command", "command": "..." }] }] } }
```

**Valid event names:**

`PreToolUse`, `PostToolUse`, `PostToolUseFailure`, `PermissionRequest`,
`UserPromptSubmit`, `Notification`, `Stop`, `SubagentStart`, `SubagentStop`,
`SessionStart`, `SessionEnd`, `TeammateIdle`, `TaskCompleted`, `PreCompact`

**Valid hook types:**

| Type | Required Fields | Optional Fields |
|------|----------------|-----------------|
| `command` | `command` | `timeout`, `environment` |
| `prompt` | `prompt` | `model`, `tools` |
| `agent` | `prompt` | `model`, `tools`, `maxTurns` |

**Cross-checks:**

- Event names not in valid set = **BLOCKER** (silently ignored by Claude Code)
- `command` paths with `${CLAUDE_PLUGIN_ROOT}` should resolve to existing scripts
- Check docs for new event names, hook types, or fields

## Plugin Config Validation Rules

### plugin.json

**Required:** `name` (kebab-case, no spaces)

**Valid optional fields:**

`version`, `description`, `author` (`{name, email?, url?}`), `homepage`,
`repository`, `license`, `keywords`, `commands`, `agents`, `skills`,
`hooks`, `mcpServers`, `outputStyles`, `lspServers`

**Cross-checks:** All path fields resolve to existing files/directories.

### marketplace.json

**Required:** `name`, `owner` (object with `name`), `plugins` (array)

**Each plugin entry:** `name` (required), `source` (required — path to plugin dir).
Optional: `description`, `version`, `author`, `category`.

**Cross-checks:** `source` paths exist, each has `.claude-plugin/plugin.json`,
names are unique.

## Priority Classification

Workers MUST classify every finding:

| Level | Meaning | Example |
|-------|---------|---------|
| **BLOCKER** | Breaks with current Claude Code | Invalid event name, removed field |
| **WARNING** | Deprecated/discouraged | Old field name, deprecated pattern |
| **INFO** | New capability available | New hook event, new frontmatter field |
| **PASS** | Validates correctly | Field values match docs |

## Output Template

```markdown
# {Type} Validation Report

**Files checked**: {count}
**Documentation version**: {date fetched}

## Breaking Changes (BLOCKER)
- **{file}:{line}** — {description}
  - Current: `{what plugin has}`
  - Expected: `{what docs say}`

## Deprecations (WARNING)
- **{file}** — {description}
  - Replacement: `{recommended alternative}`

## New Features Available (INFO)
- **{feature}** — {description}
  - Docs reference: {section}

## Validation Passed
- {count} files checked, {count} fields validated
```
