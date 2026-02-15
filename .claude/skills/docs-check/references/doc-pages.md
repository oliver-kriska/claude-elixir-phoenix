# Documentation Pages

Maps plugin component types to the Claude Code doc pages that validate them.
Used by the orchestrator to fetch only relevant pages.

## Source

All docs available at `https://code.claude.com/docs/en/{page}.md`
Index at `https://code.claude.com/docs/llms.txt` (71 pages total).

## Component-to-Page Mapping

| Component | Doc Pages | Why |
|-----------|-----------|-----|
| Agents | `sub-agents.md` | Frontmatter schema, tool names, model/permission values |
| Skills | `skills.md` | SKILL.md format, frontmatter fields, directory structure |
| Hooks | `hooks.md` | Event names, hook types, schema, matcher syntax |
| Plugin config | `plugins-reference.md` | plugin.json schema, field inventory |
| Marketplace | `plugin-marketplaces.md` | marketplace.json schema, plugin entries |

## Optional (Deep Mode)

These pages add context but are not required for basic validation:

| Page | When to Fetch |
|------|---------------|
| `plugins.md` | General plugin creation guidance |
| `hooks-guide.md` | Deep hook pattern validation |
| `settings.md` | Permission mode semantics |
| `mcp.md` | MCP server config validation |

## Fetch Strategy

### --quick Mode

No docs fetched. Structural checks only.

### Default Mode

Fetch only pages matching existing components (see Phase 2 in orchestrator).

### --full Mode

Fetch all pages from the Component-to-Page Mapping table plus optional pages.

## Cache Location

Downloaded docs go to `.claude/docs-check/docs-cache/` (gitignored).
The `scripts/fetch-claude-docs.sh` script handles downloading with
freshness checks. The orchestrator reads from cache, not from the network.

## Size Expectations

Individual pages are typically 5-30KB each.
Total for core 5 pages: ~50-100KB (well within subagent context limits).
The full `llms-full.txt` is ~500KB+ — NEVER fetch this.
