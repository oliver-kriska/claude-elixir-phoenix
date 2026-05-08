# Sub-agents per target

The plugin ships 21 specialist agents (orchestrators, reviewers,
analysts) that Claude invokes via the `Agent` tool. Per target, the
generation strategy differs:

| Source                                       | Codex                              | OpenCode                              | Pi                              |
|----------------------------------------------|------------------------------------|---------------------------------------|---------------------------------|
| `plugins/elixir-phoenix/agents/<name>.md`    | `targets/codex/agents-toml/<name>.toml` | `targets/opencode/.opencode/agent/<name>.md` | dispatched by extension from `prompts/<name>.md` |
| Format                                       | TOML                               | Markdown + YAML frontmatter           | Pi prompt template               |
| Loading mechanism                            | SessionStart bash drops into `~/.codex/agents/` | OpenCode native auto-discovery        | `extensions/orchestration.ts`    |
| Body source                                  | Source `.md` body verbatim         | Source `.md` body verbatim            | Source skill body (Phase 1B)     |

## Codex TOML shape

```toml
name = "elixir-reviewer"
description = "Expert Elixir/Phoenix code reviewer..."
model = "sonnet"
developer_instructions = '''
# Preloaded skills (from Claude source): elixir-idioms, phoenix-contexts

# Elixir Code Reviewer

You are a strict Elixir/Phoenix code reviewer...
'''
```

Codex sub-agents are loaded from `~/.codex/agents/<name>.toml` at session
start. The plugin ships a SessionStart hook
(`hooks/scripts/install-codex-agents.sh`) that copies the bundled TOMLs
into the user's home directory.

## OpenCode markdown shape

```markdown
---
name: elixir-reviewer
description: Expert Elixir/Phoenix code reviewer...
model: sonnet
mode: subagent
skills:
  - elixir-idioms
  - phoenix-contexts
---

# Elixir Code Reviewer

You are a strict Elixir/Phoenix code reviewer...
```

OpenCode auto-discovers anything under `.opencode/agent/`. The `mode:
subagent` field makes them spawnable from orchestrators rather than user
invocation.

## Pi dispatch via extension

Pi doesn't have a first-class sub-agent primitive in v0.1. The
`extensions/orchestration.ts` registers command handlers
(`phx-plan`, `phx-work`, `phx-review`) that invoke Pi prompt templates
directly. Specialist agents are not exposed as separate Pi entities —
the workflow phases run sequentially.

If Pi v0.2 (or `@tintinweb/pi-subagents`) gains a sub-agent primitive,
the extension switches to native dispatch in v3.0.0+.

## Field-mapping reference

| Claude field        | Codex                       | OpenCode                  | Pi                  |
|---------------------|-----------------------------|---------------------------|---------------------|
| `name`              | `name`                      | `name`                    | template filename   |
| `description`       | `description`               | `description`             | template `description` |
| `model`             | `model`                     | `model`                   | dropped             |
| `tools`             | dropped                     | dropped                   | dropped             |
| `disallowedTools`   | dropped                     | dropped                   | dropped             |
| `permissionMode`    | dropped                     | dropped                   | dropped             |
| `effort`            | dropped                     | dropped                   | dropped             |
| `maxTurns`          | dropped                     | dropped                   | dropped             |
| `memory`            | dropped                     | dropped                   | dropped             |
| `omitClaudeMd`      | dropped                     | dropped                   | dropped             |
| `skills`            | inlined into instructions   | `skills` field (preserved)| dropped             |
| body                | `developer_instructions`    | body                      | template body       |

Claude-only fields dropped from non-Claude targets are intentional — they
encode CC-specific concerns (permission system, sub-agent isolation, memory
features). The behavioral content lives in the body, which ports verbatim.
