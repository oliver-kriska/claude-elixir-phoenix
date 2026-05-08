---
name: hexdocs-fetcher
description: Fetch HexDocs for Elixir libraries with HTML-to-markdown conversion.
  Use when looking up docs on hexdocs.pm — modules, functions, guides, changelogs.
metadata:
  effort: low
---

# HexDocs Fetcher

Efficiently fetch Elixir library documentation from hexdocs.pm using Claude Code's native `WebFetch` tool.

## Usage

When researching libraries, use `WebFetch`:

```
# Fetch library overview
WebFetch(
  url: "https://hexdocs.pm/oban",
  prompt: "Extract the main documentation, including module overview, installation instructions, and key functions. Format as clean markdown."
)

# Fetch specific module docs
WebFetch(
  url: "https://hexdocs.pm/phoenix_live_view/Phoenix.LiveView.html",
  prompt: "Extract the module documentation including all public functions, their specs, and examples."
)

# Fetch getting started guide
WebFetch(
  url: "https://hexdocs.pm/ecto/getting-started.html",
  prompt: "Extract the complete getting started guide content."
)
```

## Token Efficiency

WebFetch automatically converts HTML to markdown and extracts relevant content:

| Source | Raw HTML | With WebFetch | Benefit |
|--------|----------|---------------|---------|
| HexDocs page | ~80k tokens | ~15k tokens | **80% reduction** |
| Phoenix docs | ~120k tokens | ~25k tokens | **79% reduction** |
| README | ~20k tokens | ~8k tokens | **60% reduction** |

## Integration with hex-library-researcher

When evaluating libraries, fetch docs efficiently:

```
# Get library overview with focused extraction
WebFetch(
  url: "https://hexdocs.pm/oban",
  prompt: "Extract: 1) Installation instructions 2) Main features 3) Basic usage example"
)
```

## Common HexDocs URLs

```
# Library overview
https://hexdocs.pm/{library}

# Module documentation
https://hexdocs.pm/{library}/{Module}.html
https://hexdocs.pm/{library}/{Module.Submodule}.html

# Guides
https://hexdocs.pm/{library}/guides.html
https://hexdocs.pm/{library}/{guide-name}.html

# API reference
https://hexdocs.pm/{library}/api-reference.html
```

## Prompt Strategies

Use focused prompts for better extraction:

```
# For API docs
prompt: "Extract all public function docs with @spec and examples"

# For guides
prompt: "Extract the complete guide content preserving code examples"

# For troubleshooting
prompt: "Extract any troubleshooting sections, common errors, and FAQs"

# For configuration
prompt: "Extract configuration options and their defaults"
```

## Caching

WebFetch includes automatic 15-minute caching. When fetching the same URL multiple times in a session, results are cached automatically.

For longer persistence, save to planning directory:

```
# After fetching, write the result to a file
Write(
  file_path: ".claude/plans/{slug}/research/docs/oban.md",
  content: "{extracted content}"
)
```

## Tidewave Alternative

If Tidewave MCP is available, prefer `mcp__tidewave__get_docs` for exact version-matched documentation:

```
mcp__tidewave__get_docs(module: "Oban.Worker")
```

This fetches docs for the exact version in your `mix.lock`.

## Iron Laws

1. **NEVER fetch entire HexDocs sites** — always target specific modules or guides
2. **Use focused prompts** — generic fetches waste tokens; specify what to extract
3. **Prefer Tidewave when available** — exact version match beats generic hexdocs.pm

## Iron Laws (Inlined)

- **NO unconditional DB queries in mount** — Mount runs twice. Default: `assign_async`. SEO routes: `connected?` + cache-backed disconnected branch (dead-render IS the crawler-indexed HTML)
- **ALWAYS use streams for lists >100 items** — Regular assigns = O(n) memory per user
- **CHECK `connected?/1` before PubSub subscribe** — Prevents double subscriptions
- **NEVER use `:float` for money** — Use `:decimal` or `:integer` (cents)
- **ALWAYS pin values with `^` in queries** — Never interpolate user input
- **SEPARATE QUERIES for `has_many`, JOIN for `belongs_to`** — Avoids row multiplication
- **Jobs MUST be idempotent** — Safe to retry
- **Args use STRING keys, not atoms** — Pattern match `%{"user_id" => id}`
- **NEVER store structs in args** — Store IDs, not `%User{}`
- **NO `String.to_atom` with user input** — Atom exhaustion DoS
- **AUTHORIZE in EVERY LiveView `handle_event`** — Don't trust mount authorization
- **NEVER use `raw/1` with untrusted content** — XSS vulnerability
- **NO process without runtime reason** — Processes model concurrency/state/isolation, NOT code structure
- **SUPERVISE ALL LONG-LIVED PROCESSES** — Never bare `GenServer.start_link`/`Agent.start_link` in production. Use supervision trees
- **NO IMPLICIT CROSS JOINS** — `from(a in A, b in B)` without `on:` creates Cartesian product
- **@external_resource FOR COMPILE-TIME FILES** — Modules reading files at compile time MUST declare `@external_resource`
- **DEDUP BEFORE `cast_assoc` WITH SHARED DATA** — Deduplicate shared child records before building changesets, not inside them
- **CHECK CHANGESET ERRORS BEFORE UI DEBUGGING** — When a form save produces no visible error but no expected side effect, check `{:error, changeset}` first
- **HIDDEN INPUTS FOR ALL REQUIRED EMBEDDED FIELDS** — Every required field in an embedded schema MUST have a `hidden_input` if not directly editable
- **WRAP THIRD-PARTY LIBRARY APIs** — Always facade external dependency APIs behind a project-owned module. Enables swapping libraries without touching callers
- **NEVER use `assign_new` for values refreshed every mount** — `assign_new` skips the function if the key exists. Use `assign/3` for locale, current user, or any value that must be set on every mount
- **VERIFY BEFORE CLAIMING DONE** — Never say "should work" or "this fixes it." Run `mix compile && mix test` and show the result. If you can't verify, explicitly state what remains unverified
