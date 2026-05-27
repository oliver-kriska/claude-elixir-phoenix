# Hooks per target

Claude Code defines 9 hook events. Per-target support varies; the port
pipeline handles the mapping.

## Event support matrix

| Source event           | Claude | Codex | OpenCode                             | Pi                              |
|------------------------|:------:|:-----:|:------------------------------------:|:-------------------------------:|
| PreToolUse             | yes    | yes   | `tool.execute.before`                | `tool_call` (block)             |
| PostToolUse            | yes    | yes   | `tool.execute.after`                 | `tool_call` (post)              |
| PostToolUseFailure     | yes    | drop  | `tool.execute.after` (with error)    | `tool_call_error`               |
| SubagentStart          | yes    | drop  | `experimental.chat.system.transform` | `session_start` (subagent_init) |
| SessionStart           | yes    | yes   | `event` filter (`session.start`)     | `session_start`                 |
| PreCompact             | yes    | yes   | not supported                        | not supported                   |
| PostCompact            | yes    | yes   | not supported                        | not supported                   |
| StopFailure            | yes    | drop  | not supported                        | not supported                   |
| Stop                   | yes    | yes   | `event` filter (`session.stop`)      | `session_end`                   |

## Codex (`targets/codex/hooks/`)

`hooks.json` lists supported events with `${CODEX_PLUGIN_ROOT}` env-var
substitution for script paths. Dropped events are listed in the support
matrix above and emitted in the `make port` build log — they are kept out
of `hooks.json` to avoid a non-standard `_meta` key that strict validators
may reject. Source shell scripts referenced by the kept events copy verbatim
(they take env-var input and don't reference Claude-internal state); scripts
orphaned by a dropped event are skipped.

The generated `install-codex-agents.sh` runs at SessionStart and copies
sub-agent TOMLs into `~/.codex/agents/`.

## OpenCode (`targets/opencode/server.ts`)

A single TS module exports a `Plugin` typed with `@opencode-ai/plugin`.
Each Claude hook has a counterpart:

```ts
export const Hooks: Plugin = {
  "tool.execute.before": async ({ tool, args }) => {
    if (tool === "Bash") {
      const cmd = args.command as string;
      if (/mix\s+ecto\.(reset|drop)/.test(cmd)) {
        throw new Error("BLOCKED: destructive ecto operation.");
      }
    }
  },
  // ... full impl in generated server.ts
};
```

Iron Laws are injected via `experimental.chat.system.transform` —
cleaner than Claude's PostToolUse-based injection, since the system
prompt itself is mutated.

PostToolUse Elixir-specific scripts (format, iron-law-verifier,
debug-statement-warning) are spawned as bash subprocesses to keep parity
with the source pipeline. Bun's `child_process` makes this trivial.

## Pi (`targets/pi/extensions/iron-laws.ts`)

Pi exposes hooks via TypeScript extensions. Two are shipped:

- `iron-laws.ts` — `session_start` injects laws.yaml shortforms into the
  system prompt; `tool_call` blocks dangerous bash patterns
- `orchestration.ts` — registers `phx-plan` / `phx-work` / `phx-review`
  command handlers that invoke prompt templates

Pi doesn't have a Compact event today, so PreCompact / PostCompact /
StopFailure are simply dropped.

## Why drop events?

Each dropped event represents Claude-specific UX (subagent isolation
boundary, plan-state-survival-after-compaction, API-failure resume
detection). The behavioural goals are achieved differently per target:

- **SubagentStart** → Codex inlines Iron Laws per skill; OpenCode and Pi
  inject via system-prompt transform.
- **PostToolUseFailure** → Codex doesn't auto-refit on bash failures
  (no equivalent UX); OpenCode chains `tool.execute.after` to inspect
  the result for failure markers.
- **StopFailure** → Codex/OpenCode/Pi don't have CC's API-resume
  semantics; users restart sessions instead.

These are documented per-target in `codex.md`, `opencode.md`, `pi.md`.
