# Amp Support

Amp support is a generated Agent Skills projection of the canonical Claude Code
plugin. The source of truth remains `plugins/elixir-phoenix/`; Amp constraints
never flow back into those files.

## Install

Clone this repository, then choose a project-local or global installation.

```bash
# Project-local: commit the installed skills with the project if desired
amp skill add ./targets/amp/skills --target /path/to/project/.agents/skills

# Global: make the skills available in every Amp workspace
amp skill add ./targets/amp/skills --global
```

Add `--overwrite` when updating an existing installation.

Amp discovers the 51 generated skills by their hyphenated names. For example:

| Claude Code | Amp |
| --- | --- |
| `phx:plan` | `phx-plan` |
| `ecto:n1-check` | `ecto-n1-check` |
| `lv:assigns` | `lv-assigns` |
| `liveview-patterns` | `liveview-patterns` |

Ask Amp to use a named skill, or let Amp activate one from its description.

## Current scope

This first target deliberately supports skills only:

- all 51 `SKILL.md` files;
- every nested reference, script, template, fixture, and asset in each skill;
- Amp-compatible names and conservative `name`/`description` frontmatter;
- rewritten cross-skill resource paths and Claude command references.

It does **not** install Claude Code hooks, the 26 custom subagents, Claude
permission settings, or MCP configuration. Domain and reference skills work
directly. Workflow skills such as `phx-plan`, `phx-review`, and `phx-full` are a
preview: their knowledge is available, but instructions that rely on named
Claude subagents or Claude-only lifecycle hooks may need Amp-native execution.

Unsupported Claude hook paths are marked explicitly in generated references;
the generator never leaves unresolved `${CLAUDE_SKILL_DIR}` or
`${CLAUDE_PLUGIN_ROOT}` variables behind.

## Generate and validate

Never edit `targets/amp/skills` manually. Change the canonical Claude skill,
then regenerate:

```bash
make amp-skills
make amp-skills-validate
```

The builder:

1. validates all normalized names and detects collisions before writing;
2. copies complete skill subtrees, transforming Markdown only;
3. validates frontmatter, resource paths, and unresolved Claude tokens;
4. replaces the generated target only after the staged build passes;
5. supports a read-only drift check used by CI.

The canonical Claude plugin can be verified independently:

```bash
make validate
make eval-all
```
