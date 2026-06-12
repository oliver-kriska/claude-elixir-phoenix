# CC Changelog Analysis Rules

## Plugin Component Mapping

When analyzing CC changelog entries, map them to specific plugin components:

### Hooks System

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| Hook events (new/changed/removed) | `plugins/elixir-phoenix/hooks/hooks.json` |
| Hook `if` conditions | All hooks with `"if":` patterns |
| Hook output behavior | `plugins/elixir-phoenix/hooks/scripts/*.sh` |
| `asyncRewake`, `once`, `timeout` | hooks.json hook definitions |
| `additionalContext` changes | SubagentStart, PostToolUseFailure hooks |
| `hookSpecificOutput` changes | All hooks using exit 2 + stderr |
| New hook types (agent, prompt, http) | Consider new hook opportunities |

### Agent Frontmatter

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| New frontmatter fields | All 20 agents in `plugins/elixir-phoenix/agents/*.md` |
| `model:` value changes | Agents using specific model values |
| `permissionMode:` changes | All agents (all use `bypassPermissions`) |
| `effort:` level changes | All agents with effort levels |
| `tools:` / `disallowedTools:` | Review agents (read-only enforcement) |
| `omitClaudeMd:` behavior | Agents with `omitClaudeMd: true` |
| `skills:` preloading | Agents with preloaded skills |
| `isolation:` / `background:` | Orchestrator agents |
| `maxTurns:` behavior | All agents with maxTurns set |

### Skill System

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| Skill format changes | All 38 skills in `plugins/elixir-phoenix/skills/` |
| `description` length limits | All SKILL.md frontmatter (CC cap 1,536 since v2.1.105; plugin targets 250) |
| `paths:` field behavior | Skills with `paths:` for auto-loading |
| Skill listing/truncation | Skill descriptions and ordering |
| Lazy loading behavior | Skills with large references |
| `argument-hint:` | Command skills with argument hints |

### Plugin Config

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| `plugin.json` schema | `plugins/elixir-phoenix/.claude-plugin/plugin.json` |
| `marketplace.json` schema | `.claude-plugin/marketplace.json` |
| `${CLAUDE_PLUGIN_DATA}` | `hooks/scripts/setup-dirs.sh`, `log-progress.sh` |
| `${CLAUDE_PLUGIN_ROOT}` | All hooks.json paths |
| `userConfig` / `sensitive` | plugin.json (if we use settings) |
| Plugin validation (`claude plugin validate`) | CI workflow |

### Tool System

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| Tool parameter changes | Hooks checking tool inputs |
| New tools added | Agent `tools:` lists |
| Tool deprecation | Agent `tools:` lists, skill instructions |
| Permission mode changes | Agent `permissionMode:` |
| `SendMessage` / `TaskCreate` / etc. | Orchestrator agents using these tools |

### Compaction & Memory

| CC Change Pattern | Plugin Files to Check |
|-------------------|-----------------------|
| Compaction behavior | `PreCompact` / `PostCompact` hooks |
| Context window changes | Agent token budgets, skill sizes |
| Memory system changes | Agents with `memory: project` |

## Impact Classification Rules

### BREAKING — Requires Immediate Action

Flag as BREAKING when CC changelog says:
- "Breaking change" explicitly
- "Removed" a feature/parameter we use
- "Changed" behavior of a hook event we rely on
- "Renamed" an API/tool/parameter we reference
- Tool parameter schema changed (affects hook `if` patterns)

**Verification**: grep the plugin for the affected term/pattern.

### OPPORTUNITY — New Feature We Could Use

Flag as OPPORTUNITY when:
- New hook event added (check "Available but NOT used" list in memory)
- New agent frontmatter field that could improve our agents
- New plugin capability (`userConfig`, new `${}` variables)
- New tool that agents could benefit from
- Performance improvement that changes best practices

**Prioritization**: Score 1-3 based on how many plugin components benefit.

### RELEVANT FIX — CC Fixed Something We Workaround

Flag as RELEVANT FIX when:
- CC fixed a bug we documented in memory or CLAUDE.md
- CC fixed a behavior our hooks explicitly handle
- Error mentioned in our compound solutions

**Verification**: search memory file and hooks for the bug pattern.

### DEPRECATION — Migration Needed

Flag as DEPRECATION when:
- CC deprecated a tool/parameter we use
- CC will remove something in a future version
- CC recommends migrating from X to Y (and we use X)

**Urgency**: immediate if removal announced, low if just deprecated.

### INFO — Log Only

Everything else: performance improvements, unrelated bug fixes, new features
for capabilities we don't use (e.g., Codex CLI, Windows-specific).

## Cross-Reference Checklist

For each BREAKING or DEPRECATION item, always:

1. `grep -r "PATTERN" plugins/elixir-phoenix/` — find all usages
2. Check `hooks/hooks.json` — any hook referencing the feature
3. Check memory file — any documented behavior about this
4. Check CLAUDE.md — any instructions referencing this

## Memory Update Template

After analysis, update `reference_cc_source_internals.md` with:

```markdown
**Last changelog audit: CC v{LATEST} (checked {DATE}, down to v{PREVIOUS})**
```

Add new sections for:
- New hook events → "Available but NOT used" list
- New agent frontmatter → Agent Frontmatter section
- New plugin capabilities → Plugin Capabilities section
- Breaking changes → Breaking Changes section
- Bug fixes affecting plugin → Bug Fixes section
