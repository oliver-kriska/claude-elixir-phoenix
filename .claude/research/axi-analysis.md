# AXI Library Analysis: Applicability to Elixir/Phoenix Plugin

**Source**: https://github.com/kunchenguid/axi
**Date**: 2026-04-09
**Status**: Research complete

## What AXI Is

AXI (Agent eXperience Interface) is a design methodology + TypeScript SDK for building
**agent-native CLI tools** — CLIs optimized for AI agent consumption rather than humans.

Core thesis: "Token budget is a first-class constraint." Traditional CLIs and MCP both
waste tokens — AXI's 10 principles reduce cost ~40% and interaction turns ~50%.

### The 10 Principles

| # | Principle | What it means |
|---|-----------|---------------|
| 1 | Token-efficient output | TOON format (~40% savings vs JSON) |
| 2 | Minimal schemas | 3-4 fields per list item, not 10 |
| 3 | Content truncation | Truncate large text + size hint + `--full` escape |
| 4 | Pre-computed aggregates | Include counts/statuses inline, eliminate follow-up queries |
| 5 | Definitive empty states | Explicit "0 results" vs silence |
| 6 | Structured errors | Idempotent mutations, no interactive prompts |
| 7 | Ambient context | Self-install SessionStart hooks for pre-invocation state |
| 8 | Content first | No-args = live data, not help text |
| 9 | Contextual disclosure | Append next-step command suggestions to every output |
| 10 | Consistent help | Concise per-subcommand reference |

### TOON Format (Token-Oriented Object Notation)

Line-oriented format where keys are declared once in a header row, not repeated per item:

```
# JSON (143 chars):
{"users":[{"id":1,"name":"Alice","role":"admin"},{"id":2,"name":"Bob","role":"dev"}]}

# TOON (72 chars):
users[2]{id,name,role}:
  1,Alice,admin
  2,Bob,dev
```

Savings come from: keys declared once, no braces/brackets/colons per field, no quoting
of unambiguous strings. Uses 2-space indentation, LF only.

### Benchmark Results (Published)

**GitHub operations (425 runs, Claude Sonnet 4.6):**
- `gh-axi`: 100% success, $0.050/task, 3 turns
- GitHub MCP: 87% success, $0.148/task, 6 turns
- Raw `gh` CLI: 86% success, $0.054/task, 3 turns

**Browser automation (490 runs):**
- `chrome-devtools-axi`: 100% success, $0.074/task, 4.5 turns
- MCP variants: $0.091-$0.120, 6-7.6 turns

## What the Plugin Already Does (AXI-Aligned)

| AXI Principle | Plugin Equivalent | Status |
|---------------|-------------------|--------|
| #7 Ambient context | SessionStart hooks inject dirs, Tidewave, resume state | Done |
| #9 Contextual disclosure | Workflow routing suggests next `/phx:` command | Done |
| #6 Structured errors | PostToolUseFailure hook, error-critic with escalation | Done |
| #8 Content first | Skills auto-load domain knowledge by file pattern | Done |
| #10 Consistent help | `/phx:help` with routing table | Done |

The plugin naturally implements 5 of 10 principles through Claude Code's native system.

## Gap Analysis: Where AXI Principles Could Help

### Principle #5: Definitive Empty States — LOW EFFORT, HIGH VALUE

**Current**: When hooks find nothing (no Iron Law violations, no format issues, no debug
statements), they exit silently (exit 0). Claude doesn't know if the check ran or skipped.

**AXI pattern**: Explicit "0 violations found" on success.

**Impact**: Removes ambiguity. Claude won't re-run checks "just to be sure." Saves ~1 turn
per hook that passes silently.

**Implementation**: Add `echo "0 violations" >&2` before `exit 0` in iron-law-verifier.sh
and similar hooks. Minimal change.

**Caveat**: PostToolUse stdout in verbose-mode only. Would need exit 2 + stderr to reach
Claude, which would block the tool — not appropriate for "all clear" messages. This principle
is actually better applied to **agent reports** than hooks.

### Principle #2: Minimal Schemas — MEDIUM EFFORT, MEDIUM VALUE

**Current**: Agent reports (review, research) produce full markdown with verbose sections.
Context-supervisor compresses these, but the initial output is unconstrained.

**AXI pattern**: Default to 3-4 fields per finding. Full details only on request.

**Impact**: Faster context-supervisor compression, lower token cost for multi-agent
orchestrations. A review agent producing tabular findings instead of prose paragraphs
would be cheaper to compress.

**Implementation**: Define "finding schemas" for each agent type:
```
findings[3]{file,line,severity,message}:
  lib/accounts/user.ex,42,BLOCKER,String.to_atom with user input
  lib/web/live/dashboard.ex,15,WARNING,Missing connected? check
  lib/workers/sync.ex,88,SUGGESTION,Consider Oban uniqueness
```

**Caveat**: Agents write to files, not stdout. TOON format would need manual formatting
in agent prompts (no SDK available). Markdown is more readable for humans reviewing
`.claude/reviews/` files.

### Principle #3: Content Truncation — MEDIUM EFFORT, HIGH VALUE

**Current**: Agent reports are uncapped. Context-supervisor compresses post-hoc.

**AXI pattern**: Truncate at source with size hints. "... (truncated, 4200 chars — full
details in reviews/correctness.md)"

**Impact**: Agents that self-truncate their responses reduce context-supervisor load.
The supervisor currently reads N full reports and compresses — if agents pre-truncated
their return values while writing full details to files, the orchestrator could skip
the supervisor step for simple cases.

**Implementation**: Add truncation guidance to agent prompts:
"Return a summary under 500 tokens. Write full details to the output file."

This is actually already partially implemented — agents write to files and return brief
summaries to orchestrators. Could be made more systematic.

### Principle #4: Pre-computed Aggregates — LOW EFFORT, HIGH VALUE

**Current**: Review agents list findings. Orchestrator must count them to decide severity.

**AXI pattern**: Include counts inline: "3 blockers, 5 warnings, 12 suggestions"

**Impact**: Orchestrator can make routing decisions from the summary line without
reading the full report. Faster triage.

**Implementation**: Add to agent prompt instructions:
"Begin your response with a counts line: `N blockers, N warnings, N suggestions`"

## What Doesn't Fit

### TOON Format Itself — NOT APPLICABLE

The TOON spec and SDK are TypeScript. The plugin operates through:
- **Bash hooks** — Would need manual TOON formatting (fragile, no encode/decode)
- **Agent prompts** — Agents write markdown to files read by humans + Claude
- **Skills** — Loaded as markdown into Claude's context

TOON makes sense for CLI tool output parsed by agents. Our output is already in Claude's
native context (skills, hooks, agent responses). Markdown is the right format for this
integration layer.

### AXI SDK / Self-Installing Hooks — ALREADY SOLVED DIFFERENTLY

AXI's hook self-installation is clever but solves a problem we don't have. The plugin's
hooks are declared in `hooks.json` and installed by Claude Code's plugin system. No
self-installation needed.

### CLI Wrapper Approach — WRONG ABSTRACTION LAYER

Building a `mix-axi` that wraps `mix test`, `mix compile`, `mix credo` with TOON output
is theoretically possible but:
- Requires maintaining a separate Node.js tool alongside the Elixir plugin
- `mix test` output is already parsed effectively by Claude
- The plugin's PostToolUseFailure hooks already add structured context to failures
- Token savings would be marginal (mix output is already reasonably compact)

## Recommendations

### Adopt (principles, not tooling)

1. **Definitive empty states** in agent reports — require agents to state "0 issues found
   in {category}" rather than omitting empty sections
2. **Pre-computed aggregates** in agent reports — require summary counts as first line
3. **Content truncation guidance** — formalize the "write details to file, return brief
   summary" pattern already partially used

### Defer

4. **Minimal finding schemas** — worth exploring if agent token costs become a problem,
   but markdown is better for the human-readable review files
5. **TOON-like hook output** — only if we build analysis hooks that produce structured
   data (e.g., a test results summary hook)

### Skip

6. **TOON format / SDK adoption** — wrong integration layer
7. **CLI wrapper tool** — over-engineering for marginal gain
8. **Self-installing hooks** — solved by plugin system

## Key Takeaway

AXI's **principles** are sound and 3 of the 5 we haven't adopted (#2, #3, #4, #5) could
improve agent token efficiency with minimal implementation effort — just prompt engineering
in agent definitions. The **tooling** (TOON format, SDK, CLI wrapping) doesn't fit because
the plugin operates at Claude Code's native skill/agent/hook layer, not as an external CLI.

The most impactful change would be adding pre-computed aggregates and definitive empty
states to agent prompts — perhaps 10 lines of prompt changes across 4-5 agents for
measurable token savings in multi-agent orchestrations.
