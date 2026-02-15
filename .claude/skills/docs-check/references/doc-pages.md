# Documentation Pages

Maps plugin component types to Claude Code doc pages used for validation.

## Source

All docs available at `https://code.claude.com/docs/en/{page}.md`
Index at `https://code.claude.com/docs/llms.txt`.

## Pages Fetched (All, Always)

| Page | Component | Why |
|------|-----------|-----|
| `sub-agents.md` | Agents | Frontmatter schema, tool names, model/permission values |
| `skills.md` | Skills | SKILL.md format, frontmatter fields, directory structure |
| `hooks.md` | Hooks | Event names, hook types, schema, matcher syntax |
| `hooks-guide.md` | Hooks | Hook patterns, examples, best practices |
| `plugins-reference.md` | Plugin config | plugin.json schema, field inventory |
| `plugin-marketplaces.md` | Marketplace | marketplace.json schema, plugin entries |
| `plugins.md` | General | Plugin creation guidance, directory conventions |
| `settings.md` | Config | Permission mode semantics, global settings |
| `mcp.md` | MCP | MCP server configuration in plugins |

Total: 9 pages, ~420KB. All fetched on every run. Cached for 24h.

## Fetch Strategy

The `scripts/fetch-claude-docs.sh` script handles everything:

- **Default**: Fetch all 9 pages, skip if cached within 24h
- **`--force`**: Re-download regardless of cache age
- **`--quick` mode**: Skill skips fetching entirely (structural checks only)

No conditional fetching. No partial downloads. Always all pages.

## Cache Location

`.claude/docs-check/docs-cache/` (gitignored). The orchestrator reads
from cache and crashes if files are missing.

## Size

Individual pages: 5-80KB each. Total: ~420KB.
Each validation worker gets 1-2 pages (~8-20K tokens) — well within
the 200K context limit. No indexing or compression needed for docs.

**NEVER fetch `llms-full.txt`** (~500KB+ single file with all 57+ pages).
