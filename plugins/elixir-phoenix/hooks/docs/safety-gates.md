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

Blocks four command shapes before they run, and reads the local scripts a
command runs for the last two.

| Pattern | Gated on `mix.exs`? | Why |
|---|---|---|
| `mix ecto.reset` / `mix ecto.drop` | Yes | Destroys all data |
| Force push (`--force` / `-f`) | **No — global** | Rewrites remote history |
| `MIX_ENV=prod` with a task that is not a build step | Yes | Runs the app or its code with production config |
| Pattern kill naming a BEAM process (`pkill -f beam`) | Yes | Stops every Erlang VM on the machine, not only yours |
| A local script the command runs that holds either of the last two | Yes | The same step, one file away |

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

### `MIX_ENV=prod`: build steps only

Until 2026-10-14 the hook denied every `MIX_ENV=prod … mix …` command, while
its own deny message said "If building a release, this is expected." The rule
and the message disagreed. In a headless rewrite trial on that date, a session
then put `MIX_ENV=prod mix release` inside `scripts/release_smoke.sh` and ran
the script, which the hook never opened. That step is a build and is allowed
now, but a denied one in the same place would have run unchecked too (see
[Scripts the command runs](#scripts-the-command-runs)).

The rule now matches what the message promises: building a release under
`MIX_ENV=prod` is allowed, running anything is not, and the message lists both.

| Under `MIX_ENV=prod` | Result |
|---|---|
| `mix release`, `mix compile`, `mix deps.compile`, `mix assets.deploy`, `mix phx.digest` | Allowed |
| `mix deps.get --only prod` | Allowed. Plain `mix deps.get` is denied |
| `mix do A, B` / `mix do A + B` | Allowed only when every task in it is |
| Every other mix task: `mix ecto.migrate`, `mix run`, `mix phx.server`, `mix test`, bare `mix` | Denied |
| `iex` (`iex -S mix`, `iex -S mix phx.server`) | Denied |
| Another program (`MIX_ENV=prod make release`) | Not inspected, as before |

The allowed list is the build sequence of a Phoenix release Dockerfile
(`deps.get --only`, `deps.compile`, `assets.deploy`, `compile`, `release`)
plus `phx.digest`. A production migration runs from the release
(`bin/migrate`, `bin/APP eval`), not from `MIX_ENV=prod mix ecto.migrate` on a
developer machine, which would run against whatever database the production
config points at.

What you see:

```text
BLOCKED: MIX_ENV=prod mix ecto.migrate.
MIX_ENV=prod is allowed only for build steps:
- mix release, mix compile, mix deps.compile
- mix assets.deploy, mix phx.digest, mix deps.get --only prod
Every other mix task under MIX_ENV=prod, and iex, is denied: it runs
the app or its code with production config (mix ecto.migrate,
mix run, mix phx.server, iex -S mix). If intentional, run it
manually outside Claude Code.
```

### Pattern kills of BEAM processes

In the same trial, a session stopped a Phoenix dev server it had started with
`pkill -f phx.server`, then `pkill -f beam`, and `/phx:work` ran
`pkill -f "mix phx.server"`. A pattern kill matches every process on the
machine: the developer's own Phoenix servers, IEx shells and ElixirLS, which
are all BEAM VMs. Nothing in the phx hooks stopped it.

Denied: `pkill` or `killall`, with any flags (`-f`, `-9`, `-u`), whose
arguments name `beam`, `beam.smp`, `erl`, `erlang`, `epmd`, `elixir`, `iex`,
`mix` or `phx.server`. Also denied: the two `pgrep` rewrites of the same kill,
`kill $(pgrep -f beam)` and `pgrep -f beam | xargs kill`, because they are what
a model reaches for once `pkill` is refused.

A name matches as a whole word, case-insensitively. `pkill perl` and
`pkill -f mix_tool` pass; `pkill -f Elixir.MyApp` and `killall beam.smp` are
denied.

Allowed: `kill PID`, `kill "$pid"`, `kill -0 PID`, `kill %1`, `pkill -P PID`,
and pattern kills of anything else (`pkill -f webpack`).

The deny message gives the safe form: stop only the process you started, by
the PID you recorded when you started it.

```bash
mix phx.server > /tmp/phx.log 2>&1 &
pid=$!
# ... later
kill "$pid"
```

The check is gated on `mix.exs` like every other Elixir-specific branch, so
the force-push block stays the only global one.

### Scripts the command runs

A deny on the command line is easy to sidestep by moving the step into a file.
When the command runs a local script — `bash FILE`, `sh FILE`, `zsh FILE`,
`source FILE`, `. FILE`, `./FILE`, `../FILE` or `DIR/FILE.sh` — the hook greps
that file for the `MIX_ENV=prod` and pattern-kill checks above, and denies with
the script path and line number:

```text
BLOCKED: MIX_ENV=prod mix ecto.migrate in scripts/release_smoke.sh, line 12.
```

Relative paths resolve against the hook input's `cwd`. A file that does not
exist or cannot be read is skipped and the command runs: the scan fails open.
Comment lines and quoted mentions inside the script do not match, for the same
anchor reason as on the command line. The `ecto.reset`/`ecto.drop` and
force-push checks do not read scripts.

### What it does not catch

These are known gaps, not oversights. Each one would need the hook to track
shell state or parse quoting, and a PreToolUse gate sits in the latency of
every Bash call.

- `export MIX_ENV=prod` followed by `mix ecto.migrate`, on the command line or
  in a script. Only a `MIX_ENV=prod` prefix on the same command counts, so
  `MIX_ENV=prod ./scripts/x.sh` running a plain `mix ecto.migrate` also passes.
- `bash -c "…"` and `sh -c "…"`. The inline command is quoted, and quoted text
  never matches.
- Release commands (`bin/APP eval`, `bin/APP rpc`). They do not use `MIX_ENV`.
- A PID looked up in one Bash call and killed in the next
  (`pid=$(pgrep -f beam)`, then `kill $pid`), and port-based kills
  (`lsof -ti :4000 | xargs kill`).
- Script paths in quotes, after a `cd` in the same command, or with neither a
  `./` prefix nor a `.sh` suffix (`bin/dev`). Scripts called from a script are
  not read either.

### Fail-open contract

Every intentional deny goes through `emit_block` — JSON output plus **exit 0**.
Claude Code blocks a tool call only when a PreToolUse hook exits **2**; any
other non-zero exit is a non-blocking error and the command runs. The trap is
that bash itself exits 2 on a syntax error. The script once got corrupted by
merge-conflict markers, and **every Bash call in the session was blocked**.

`hooks.json` used to append `|| exit 0` to the command to fail open. The
Anthropic plugin directory rejects shell operators in hook commands, so the
command is now the bare quoted script path, and the guard moved into CI:
`test_hook_scripts_parse` runs `bash -n` on every hook script and rejects
merge-conflict markers, and the pre-commit hook runs shellcheck, so a broken
copy cannot ship.

For a while the script also parsed itself first (`bash -n` on its own path)
and stepped aside if that failed. The plugin directory blocks a hook script
that runs another path, so that self-check is gone: a copy corrupted on a
user's disk after install is no longer caught at runtime. The same rule is why
the script probes for `jq` with `jq --version` rather than `command -v jq`.

If `jq` is missing, the hook prints a notice to stderr and exits 0.

The script path is quoted because, before v3.1.2, a user whose plugin cache
path contained a space got a shell looking for a script named after the first
word; the command failed, and the force-push and destructive-`mix` blocks were
silently off.

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
