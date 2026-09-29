# Safety Gates (`PreToolUse`)

Three hooks that run **before** a tool executes and can refuse it. These are the
only hooks in the plugin that stop an action outright — everything else advises
after the fact.

All three emit a deny as JSON `permissionDecision: "deny"` plus
`additionalContext`, never as a non-zero exit code. Claude Code 2.1.110+ keeps
`additionalContext` on a blocked tool call, so the reason and the safer
alternative survive into Claude's next turn instead of being lost — which is
what stops it from immediately retrying the same command.

| Script | Fires on | Can block? |
|---|---|---|
| `block-dangerous-ops.sh` | every `Bash` call | Yes — destructive commands |
| `deps-audit-gate.sh` | `Bash(*mix deps.*)` | Yes — unvetted dependency changes |
| `freeze-gate.sh` | `Edit` / `Write` / `NotebookEdit` | Yes — when a freeze is active |

---

## `block-dangerous-ops.sh`

Blocks three command shapes before they run.

| Pattern | Gated on `mix.exs`? | Why |
|---|---|---|
| `mix ecto.reset` / `mix ecto.drop` | Yes | Destroys all data |
| Force push (`--force` / `-f`) | **No — global** | Rewrites remote history |
| `MIX_ENV=prod mix …` | Yes | Runs in production mode |

What you see instead of the command running:

```text
BLOCKED: Destructive database operation detected.
mix ecto.reset/drop will destroy all data. If intentional, run manually
outside Claude Code. Safer alternatives:
- mix ecto.rollback --step 1 (undo last migration)
- mix ecto.migrate (apply pending migrations)
```

The force-push block is deliberately **not** gated on `mix.exs` — history
rewriting is dangerous in any repo, so this one fires in your Rust and Python
projects too. Everything Elixir-specific stays gated.

### What it does not block

`--force-with-lease` is explicitly allowed. It refuses to clobber commits you
have not seen, which makes it the safe form. An earlier pattern
(`git push.*(--force|-f)\b`) accidentally caught it: in ERE, `\b` matches
between `e` and `-`, so the trailing hyphen satisfied the word boundary and the
whole flag matched. Fixed in issue #61.

Quoted mentions are also safe. A force-push string inside an `echo` does not
trigger, because the pattern only anchors at start-of-line or after a real shell
separator (`;`, `&`, `|`) — never after arbitrary mid-line whitespace.

### Leading-whitespace evasion

The start-of-line anchor is `^[[:space:](]*`, not a bare `^`. With a bare `^`, a
command preceded by a tab, by two spaces, or wrapped in a subshell paren all
executed while evading every deny. Claude Code shipped a fix for the same
padding-hides-the-command class of hole in its own permission prompts in
2.1.223; this hook was fixed 2026-08-10.

`(` is deliberately **not** added to the separator class `[;&|]`. Doing so would
make a parenthesised mention inside a quoted string match again, reintroducing
the false positive issue #61 removed. Only the start-of-line branch is widened.

Invisible Unicode padding (U+00A0 and friends) is intentionally out of scope:
the shell would treat the padded word as a command name that does not exist, so
it is not an execution path.

### Fail-open contract

Every intentional deny goes through `emit_block` — JSON output plus **exit 0**.
A non-zero exit from this script is always a bug, so `hooks.json` appends
`|| exit 0`:

```json
"command": "\"${CLAUDE_PLUGIN_ROOT}/hooks/scripts/block-dangerous-ops.sh\" || exit 0"
```

This matters. The script once got corrupted by merge-conflict markers, and
because bash exited non-zero, **every Bash call in the session was blocked**.
Failing open turns that class of failure into "the guard is off" rather than
"the session is bricked". If `jq` is missing, the hook prints a notice to stderr
and exits 0 for the same reason.

The script path is quoted for the same reason. Before v3.1.2 it was not, and
for a user whose plugin cache path contains a space the shell looked for a
script named after the first word, failed, and `|| exit 0` turned that into an
allow — the force-push and destructive-`mix` blocks were silently off.

**Never add a deny path that relies on a non-zero exit code.**

---

## `deps-audit-gate.sh`

Guards `mix deps.get`, `mix deps.update`, and `mix deps.compile` against
supply-chain risk. It is the enforcement arm of the `/phx:deps-audit` skill —
the skill does the deep scan, the hook keeps you from silently pulling in
something the scan flagged.

It is built as a tiered fast path, because a `PreToolUse` hook sits directly in
the latency of a command you run often:

| Tier | Budget | What runs |
|---|---|---|
| Tier 0 | <200 ms | Cache hit — `mix.lock` SHA matches `.claude/deps-audit/last-run.json`, previous audit passed, policy unchanged → silent exit |
| Tier 1 | <2 s | Rule 1 (bidi/RLO control chars in `mix.lock`) + Rule 5 (new `:git` / `:path` deps vs `origin/main`). Zero false positives, no network, no LLM |
| Tier 2 | opt-in | The full audit pipeline. **Not** chained from the hook — the budget is already spent by Tier 1. `:full` mode runs it from the skill body instead |

### Policy modes

Read from `hex_vet.exs` → `policy.block_on_unvetted`:

| Value | Behavior |
|---|---|
| absent / `false` | Warn only, never blocks |
| `:new_only` | Blocks when the change *adds* an unvetted version (default once a ledger exists) |
| `:strict` | Blocks on any Tier 1 finding |
| `:full` | `:strict` rules, and Tier 2 runs via the skill |
| `true` | Deprecated — treated as `:strict`, with a notice |

The parser strips Elixir line comments before matching and takes the **last**
uncommented match, mirroring Elixir's last-assignment-wins map-literal
semantics. Before the v3.0.1 hotfix it took `head -1` of the raw file, so a
commented-out example line could silently downgrade enforcement — failing open
in the worst possible direction.

### Escape hatches

```bash
PHX_SKIP_DEPS_AUDIT=1 mix deps.get   # skip the gate entirely
PHX_DEPS_AUDIT_BASE=origin/develop   # change the git ref for the new-dep diff
```

Note this gate reports via **exit 2 + stderr**, not a JSON permission decision —
it predates the `emit_block` convention and surfaces findings as a message.

---

## `freeze-gate.sh`

An edit lock you switch on for a focused task. This is the on-demand,
skill-scoped hook pattern from Anthropic's "how we use skills": rather than a
permanent guard, it is one the `/phx:freeze` skill turns on and off.

Claude Code has no native skill-scoped hooks, so the state lives in a sentinel
file:

```text
$CLAUDE_PROJECT_DIR/.claude/.freeze
```

| Sentinel state | Effect |
|---|---|
| Missing | No-op. The hook is dormant, which is why it ships enabled |
| Present, empty | **All** `Edit` / `Write` / `NotebookEdit` denied — read-only investigation mode |
| Present, path lines | Only edits at or under a listed prefix are allowed |

Blank lines and `#` comments in the sentinel are ignored. Relative paths resolve
against the project root, and the edit target is normalized to an absolute path
before the prefix comparison, so a relative and an absolute reference to the
same file behave identically.

The deny text tells Claude not to retry, and that only the user can lift it:

```text
Edit freeze is active (edits limited to: lib/accounts test/accounts).
Do not retry this edit. The user must run '/phx:freeze off' to lift the lock,
or '/phx:freeze <dir>' to allow a directory.
```

The `/phx:freeze` skill writes the sentinel through **Bash**, never `Edit` or
`Write` — otherwise the gate would block the skill from turning itself off.

## Related

- [Code Quality](code-quality.md) — the advisory `PostToolUse` checks
- [Workflow State](workflow-state.md) — plan and compaction state hooks
- `/phx:deps-audit`, `/phx:deps-vet`, `/phx:freeze`
