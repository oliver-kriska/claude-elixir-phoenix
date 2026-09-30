# Hooks — Contributor Guide

Implementation notes for the 23 hook scripts in this directory. For the
user-facing explanation of what the hooks *do*, see
[`HOOKS.md`](../../../HOOKS.md) at the repo root.

```text
hooks/
├── hooks.json          # Registration: event → matcher → script
├── scripts/            # 23 bash scripts
├── tests/              # Shell test suites
└── docs/               # Per-group reference (linked below)
```

## Reference by group

| Group | Events | Scripts |
|---|---|---|
| [Safety Gates](docs/safety-gates.md) | `PreToolUse` | `block-dangerous-ops`, `deps-audit-gate`, `freeze-gate` |
| [Code Quality](docs/code-quality.md) | `PostToolUse` | `format-elixir`, `iron-law-verifier`, `debug-statement-warning`, `security-reminder` |
| [Failure Recovery](docs/failure-recovery.md) | `PostToolUseFailure`, `PostToolUse` (reset) | `elixir-failure-hints`, `error-critic` |
| [Context Injection](docs/context-injection.md) | `UserPromptSubmit`, `SubagentStart` | `route-intent`, `inject-iron-laws` |
| [Session Lifecycle](docs/session-lifecycle.md) | `SessionStart` | `setup-dirs`, `detect-tidewave`, `detect-ash`, `check-scratchpad`, `check-resume`, `check-branch-freshness` |
| [Workflow State](docs/workflow-state.md) | `PostToolUse`, `SessionStart` (`compact`), `StopFailure`, `Stop` | `plan-stop-reminder`, `log-progress`, `compact-rules`, `compact-verify`, `stop-failure-log`, `check-pending-plans` |

## Output rules per event

**This is the table to check before writing any hook.** Each event has a
different channel that actually reaches somebody, and picking the wrong one
produces a hook that runs correctly and is read by nobody.

| Event | How to reach Claude | How to reach the user | Notes |
|---|---|---|---|
| `PreToolUse` | `permissionDecision` + `additionalContext` (JSON) | `permissionDecisionReason` | `additionalContext` survives a blocked call (CC 2.1.110+) |
| `PostToolUse` | **exit 2 + stderr** | — | Plain stdout is **verbose-mode only** |
| `PostToolUseFailure` | `hookSpecificOutput.additionalContext` | — | |
| `UserPromptSubmit` | **stdout** (injected) or `additionalContext` | — | **Never exit 2** — it erases the user's prompt |
| `SubagentStart` | `hookSpecificOutput.additionalContext` | — | |
| `SessionStart` | **stdout** (injected) | stdout | One of only two events whose stdout reaches Claude. Matcher `compact` fires after compaction — the re-injection channel |
| `PreCompact` | **nothing** | `systemMessage`; stderr on manual `/compact` | Can only block compaction. Re-inject via `SessionStart` `compact` |
| `PostCompact` | **nothing** | `systemMessage`; exit 2 stderr | No decision control. Re-inject via `SessionStart` `compact` |
| `StopFailure` | **nothing** | **nothing** | CC ignores exit code *and* output. Persist to a file instead |
| `Stop` | `additionalContext` / exit 2 — but this **continues the turn** | JSON `systemMessage` | stdout is debug-log only |

## Conventions

### 1. Gate on `mix.exs`

Every Elixir-specific hook starts with:

```bash
proj="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$proj/mix.exs" ] || exit 0
```

Without it the plugin bleeds into every repo the user opens — creating
`.claude/plans/` in Rust projects, injecting Phoenix Iron Laws into Python
subagents (issue #55). The **only** deliberate exception is the force-push block
in `block-dangerous-ops.sh`, which is dangerous everywhere.

### 2. Fail open

No `set -e` in hook scripts. A hook that errors must degrade to "guard is off",
never to "session is broken". Denials are expressed as **data** (JSON
`permissionDecision`), never as an exit code: Claude Code blocks only on exit 2,
and bash exits 2 on a syntax error, so `test_hook_scripts_parse` keeps every
hook script parseable, and a blocking gate (`block-dangerous-ops.sh`) starts
by running `bash -n` on its own literal `${CLAUDE_PLUGIN_ROOT}` path so a copy
corrupted on disk steps aside. See the fail-open contract in
[Safety Gates](docs/safety-gates.md#fail-open-contract) for the incident that
established this rule.

### 3. Use `if` conditions to avoid shell spawns

Register file-type-specific hooks with an `if` so they never spawn on unrelated
files:

```json
{
  "type": "command",
  "if": "Edit(*.ex)",
  "command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/format-elixir.sh\"",
  "timeout": 30
}
```

The scripts re-check anyway (defense in depth), but the `if` avoids the process
spawn entirely.

### 4. `grep -c` needs `${VAR:-0}`, not `|| echo 0`

`grep -c` prints `0` **and** exits 1 on no match, so `|| echo 0` appends a
second line and the two-line value breaks any numeric comparison downstream:

```bash
COUNT=$(grep -c '^\- \[ \]' "$file" 2>/dev/null)
COUNT=${COUNT:-0}
```

### 5. Anchor command patterns

Match at start-of-line or after a real shell separator, absorbing leading
whitespace and subshell parens:

```text
(^[[:space:](]*|[;&|]+[[:space:]]*)
```

A bare `^` lets a leading tab or two spaces evade the guard. Plain mid-line
whitespace must **not** be an anchor, or quoted mentions inside `echo` start
matching.

### 6. Blame awareness

Content scanners read `tool_input.new_string` (Edit) or `tool_input.content`
(Write) — **not** the file on disk. Flagging pre-existing violations in
untouched regions pushes Claude into unrequested refactors.

### 7. State goes in `/tmp` or `$CLAUDE_PLUGIN_DATA`

Per-session counters use `/tmp/.claude-elixir-*/` keyed by session or command.
Durable metrics use `$CLAUDE_PLUGIN_DATA` (CC v2.1.78+), which survives plugin
updates. Never write scratch state into the user's project.

### 8. Quote `${CLAUDE_PLUGIN_ROOT}` in every command

Wrap the placeholder and script path in escaped double quotes:
`"\"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/x.sh\""`. Unquoted, a plugin cache
under a path with a space (`/Users/John Doe/...`) splits into two words and the
script never runs, so the guard silently fails open. The command must be
that one quoted path and nothing else — no `|| exit 0`, pipes or arguments:
the Anthropic plugin directory blocks a submission whose hook command it
cannot follow. `claude plugin validate --strict` (run by `make validate`) and
`test_hook_commands_are_one_literal_script` reject anything else.

### 9. Plain bash inside the scripts

The plugin directory also follows each script and blocks the submission on
anything it cannot read: an inline program (`awk '…'`, `sed '…'`, `perl -e`,
`python3 -c`, `node -e`), `eval`, sourcing another file, or a path built from a
variable other than `${CLAUDE_PLUGIN_ROOT}` (`$0` and `BASH_SOURCE` included).
Use bash parameter expansion, `[[ =~ ]]` with `BASH_REMATCH`, `grep` and `jq`
instead, and write any script path as literal
`"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/<file>"`. Remember that `/bin/bash` on
macOS is 3.2. `test_hook_scripts_run_only_paths_the_directory_can_follow`
enforces this.

## Adding or changing a hook

1. Write the script in `scripts/`, `chmod +x`, following the conventions above.
2. Register it in `hooks.json` with a `timeout` and, where applicable, an `if`.
3. **Update the docs.** Add it to the matching file in `docs/`, to the table in
   the root [`HOOKS.md`](../../../HOOKS.md), and to the hook list in
   `CLAUDE.md`. This is a required step, not a nicety — the docs are the only
   place the *reasoning* is recorded.
4. Add a case to `tests/` if the hook has non-trivial matching (see
   `tests/block-dangerous-ops_test.sh`).
5. Run `make lint` and `make ci`.
6. Add a `CHANGELOG.md` entry under `[Unreleased]`.

Hook edits are picked up by `/reload-plugins` (CC v2.1.98+) without restarting.

## Testing a hook by hand

Hooks read a JSON event on stdin:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"mix ecto.drop"}}' \
  | ./scripts/block-dangerous-ops.sh

echo '{"tool_input":{"file_path":"lib/a.ex","new_string":"String.to_atom(x)"}}' \
  | ./scripts/iron-law-verifier.sh; echo "exit=$?"
```

Run the shell suite:

```bash
bash tests/block-dangerous-ops_test.sh
```

## MCP tool hooks

Claude Code 2.1.118+ supports `type: "mcp_tool"` hooks (`server`, `tool`,
optional `input` with `${tool_input.field}` substitution).

Caveat: `SessionStart` and `Setup` fire **before** MCP servers finish
connecting, so service detection must use a direct probe — see
`detect-tidewave.sh`. Reserve `mcp_tool` hooks for `PreToolUse`, `PostToolUse`,
and `Stop`, where the connection is already live.

## Other targets

`targets/codex/hooks/hooks.json` ships **one** synchronous native hook — the
`block-dangerous-ops.sh` `PreToolUse` gate — using `${PLUGIN_ROOT}` rather than
`${CLAUDE_PLUGIN_ROOT}`. Codex requires users to review and trust plugin hooks
before they run. Amp, Pi, and OpenCode targets do not carry lifecycle hooks; the
canonical set here is Claude Code only.
