---
name: verify
description: "Verify a rewrite slice against its obligations: preflight, capture fresh test evidence, audit translationese and parity, update the ledger. Use after /phx:work finishes a rewrite slice, or before claiming parity."
effort: medium
argument-hint: "<slice NN | slug> [--no-run] [--full]"
---

# Rewrite Verify — Evidence, Not Claims

Phase 5, run once per slice after `/phx:work`. It answers two questions with
evidence: is this slice **Elixir, or the legacy app transliterated** (idiom
audit), and which of its obligations are **proven** (parity audit). Generic
Elixir quality stays with `/phx:review`.

```text
/phx:work → /rewrite:verify NN  <-- YOU ARE HERE → /rewrite:roadmap --next
```

## Iron Laws

1. **PREFLIGHT BEFORE ANY COMMAND** — static proof of the target, a disposable database and no live side effects, printing no secret; a blocked preflight stays `blocked`, never a trial run
2. **EVIDENCE IS RECORDED** — exit status, target and source identity before and after, redacted environment and log, written before anyone interprets them; identity that moved means `stale`
3. **THE OBLIGATIONS ARE THE DENOMINATOR** — from the slice seed, the analyses and a source completeness check, never from the tests that happen to exist
4. **NO PASS BY EXCLUSION** — skipped, excluded, stubbed or stale results never count; pre-existing findings are still findings
5. **NEVER RUN THE LEGACY APP** — evidence comes from the Elixir target only; the source is read and fingerprinted, never executed; suites hit the port, legacy tests are translated
6. **DONE MEANS THE GATE PASSED** — every obligation `pass`, or changed or retired by an accepted ADR or a user-approved AR record, and no BLOCKER

## Workflow

### 1. Resolve the slice

Find `.claude/plans/rewrite-{NN}-*/` (or the slug). Read its `interview.md`
(Acceptance Criteria, External Contracts, `## Oracle`, ledger IDs) and `progress.md` if present.
`TARGET` is the current directory and must contain `mix.exs`; `SOURCE` is the legacy path recorded in
`.claude/rewrite/status.md`. `EV=.claude/rewrite/verify/{NN}/evidence` (create it).

Use the bundled script for identity; define `fp` in every shell call that uses it:

```bash
fp() { python3 "${CLAUDE_SKILL_DIR}/scripts/fingerprint.py" "$@"; }
```

- **Output** — `head` and a `content_fingerprint`: SHA-256 over the full bytes of every dirty file (tracked changes
  plus untracked, non-ignored files) and of every file in each submodule work tree, or of every file outside git.
  Git runs with the checkout's hooks, filters and fsmonitor disabled, and never writes the index
- **Split index** — when the git dir holds `sharedindex.*`, git would touch it on read, so the whole tree is hashed
  instead (`mode: tree`, `fallback: split-index`, no head). Compare only captures taken in the same mode
- **Excludes** — `.claude/rewrite/verify/`, `_build/`, `deps/` and `node_modules/` by default
- **Exit 2** — no identity: DIR is not a directory, a file cannot be read, an exclude leaves DIR, git cannot list
  changes, or a tracked file is flagged `assume-unchanged`/`skip-worktree` (git hides its edits). Ask the user to
  clear the flag; never clear it yourself
- **One list per run** — pass the same `--exclude` set to every capture; add a path only for output the run itself writes (`cover/`), and record it

### 2. Preflight (static, before running anything)

Write only redacted conclusions to `.claude/rewrite/verify/{NN}/preflight.md`:

```bash
test -f mix.exs && [ -n "$SOURCE" ] && case "$(realpath .)/" in "$(realpath "$SOURCE")"/*) false;; esac  # not in legacy
awk 'BEGIN { for (k in ENVIRON) print k }' | grep -E '^(DATABASE_URL|MIX_ENV|AWS_.*|.*(SECRET|TOKEN|KEY).*)$' | sort  # names only
u=${DATABASE_URL-}; h=${u#*://}; h=${h%%/*}; h=${h##*@}; h=${h%:*}
case "$u" in "") echo "DATABASE_URL unset";; *) case "$h" in localhost|127.0.0.1|"[::1]") echo "DATABASE_URL local";; *) echo "DATABASE_URL non-local";; esac;; esac
```

Read these without running Mix:

- **`mix.exs`** — `aliases` (what `test` and `compile` really run: `ecto.reset`, seeds, `cmd`, downloads), `compilers:` and any `System.cmd`
- **Config chain** — `config/config.exs`, `config/test.exs`, every file their `import_config` reaches, and `config/runtime.exs`, which also runs under `MIX_ENV=test`
- **In those files** — Repo `url:`, `hostname:`, `database:` and any `System.get_env`/`fetch_env!` feeding them; mailer, push, HTTP and webhook adapters or base URLs; Oban `testing:`; node connections

```bash
grep -nE 'aliases|compilers:|System\.cmd|ecto\.(drop|reset)|"cmd ' mix.exs
grep -nE 'import_config|url:|hostname:|database:|System\.(get_env|fetch_env)|adapter:|testing:|base_url' config/config.exs config/test.exs config/runtime.exs
```

Stop with the preflight `blocked` when any of these holds:

- **Database** — not shown disposable (local host or tmp path, a test-only database, SQL sandbox pool); a `_test` name alone is not proof
- **Environment** — the database or an endpoint is configured from a variable that is `non-local` or unchecked
- **Side effects** — mail, push, webhooks or HTTP could reach real endpoints, or a black-box command targets a non-local host
- **Mix steps** — an alias or compiler step is destructive or networked

Never run a command to find out whether it was safe; ask the user with the
redacted reason (`--no-run` skips straight to the audits with evidence `blocked`).

### 3. Capture evidence

First write the run list, `$EV/commands.md`, before running anything: `MIX_ENV=test mix compile --warnings-as-errors` (log
`$ts-compile.log`) and `mix test` on the slice's test files (with `--full`, the whole suite and `mix format --check-formatted`);
every command an acceptance criterion names, with its arguments as named (the named seeds, not a random one; `--force`, the
full suite, a test outside the slice paths, a release smoke, a static check such as `rg` or `git diff`); and every `## Oracle`
command (black-box files, whole-file diagnostics, the load script as a short smoke). Run each through this wrapper. Leave one
out only when it cannot run here (a missing tool, a blocked preflight), and say so; a `/phx:work` log never stands in. Write
this run's script from this step, never from a copy of another slice's or an earlier run's script:

```bash
fp() { python3 "${CLAUDE_SKILL_DIR}/scripts/fingerprint.py" "$@"; }
ts=$(date -u +%Y%m%dT%H%M%SZ); log="$EV/$ts-test.log"; started=$(date -u +%FT%TZ)
tb=$(fp .); sb=$(fp "$SOURCE")
MIX_ENV=test mix test {slice test paths} > "$log" 2>&1; t=$?
ta=$(fp .); sa=$(fp "$SOURCE")
[ -n "$tb" ] && [ -n "$sb" ] && [ "$tb" = "$ta" ] && [ "$sb" = "$sa" ] && id=fresh || id=stale
```

Write one `$EV/$ts-{name}.md` per command: the command and cwd; its exit status, which with the log outranks any summary; UTC
`started_at` and `finished_at`; the four `fp` outputs; `identity`, `fresh` only when all four captures succeeded and each
before equals its after, else `stale`; env variable names and redacted conclusions, never values; `N tests, F failures, E excluded`
and the log path. `git status` text is a diagnostic, never the freshness proof.

For black-box files, start the port as it ships, never a dev server (its `debug_errors` page answers HTML where the release
answers the envelope), on a database this run creates and drops; never point a suite at the legacy app:

```bash
MIX_ENV=prod mix release --overwrite > "$EV/$ts-release.log" 2>&1
RELEASE_DISTRIBUTION=none _build/prod/rel/{app}/bin/{app} start > "$EV/$ts-server.log" 2>&1 &  # no epmd outlives it
echo $! > "$EV/port.pid"  # then the suite: $ts-oracle.md names each file, the --oracle root, its own uid, the result
kill "$(cat "$EV/port.pid")"  # that PID only: pkill or killall by pattern stops the user's other BEAM processes
```

### 4. Audit in parallel

No `commands.md`? Write it now. Then run each listed command with no record through the wrapper, and re-run any record lacking
its four `fp` values: auditors score records, never a later re-run. Run `fp .` and `fp "$SOURCE"` (same excludes) before
spawning, passed as `CURRENT_IDENTITY`; agents cannot run plugin scripts. Build `COMPLETENESS`: the slice's ledger IDs and
source anchors from `interview.md` and the ledger rows, nothing wider. Spawn both in ONE message with `run_in_background: true`:

- **`rewrite:idiom-auditor`** — `TARGET`, `SCOPE` (`git diff --name-only` from the slice's base commit in `progress.md`, else the slice's modules), `LEDGER`, `ARCHITECTURE`,
  `CONTRACTS=.claude/rewrite/analysis/contracts.md`, `KB=.claude/rewrite/kb/`, `OUTPUT=.claude/rewrite/verify/{NN}/idiom.md`
- **`rewrite:parity-auditor`** — `TARGET`, `SOURCE`, `COMPLETENESS`, `OBLIGATIONS` (the interview path plus the analyses), `LEDGER`, `EVIDENCE=$EV`, `CURRENT_IDENTITY`,
  `DECISIONS` (`.claude/rewrite/architecture/`, `.claude/rewrite/verify/accepted-risks.md`), `CLAIMS` (`progress.md`, PR text if any), `OUTPUT=.claude/rewrite/verify/{NN}/parity.md`

### 5. Apply ledger updates

Apply only the parity auditor's `Proposed Ledger Updates` that have a
basis, editing the Impl and Evidence columns of `.claude/rewrite/ledger.md`.
Never write a Departure cell, an ADR status or an AR record yourself. Only
the user creates or approves an accepted risk, in
`.claude/rewrite/verify/accepted-risks.md`:

```markdown
## AR-NN — <title>
- Owner: …
- Scope: <ledger IDs>
- Rationale: …
- Review: <condition or date that reopens it>
- Approved: <who approved, when, where>
```

Run the ledger checks:

```bash
python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py" check --rewrite-dir .claude/rewrite
python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py" stats --rewrite-dir .claude/rewrite \
  --slice .claude/plans/{slug}/interview.md
```

A failing `check`, a nonzero `stats` (1 = malformed ledger, 2 = unreadable slice) or 0 selected rows fails the gate.

### 6. Report and gate

Report the parity auditor's states: a record made after the audits changes none until a new audit scores it. Write
`.claude/rewrite/verify/{NN}/report.md`: verified parity (`pass` of the counted obligations), accepted departures apart
(ADR or AR, never verified), source omissions, scope mistakes, idiom BLOCKERs, rejected and stale evidence, unsupported claims, the gate.

The gate passes only when no BLOCKER remains, every black-box file `## Oracle` assigns passed in a fresh record
(failing or not run fails the gate), and every counted obligation is one of:

- **Verified** — `pass`
- **Changed or retired** — by an ADR whose Status is `accepted`
- **Accepted risk** — in the Scope of an `AR-NN` record with all five fields filled and an `Approved` you can confirm came from the user

Never count a `proposed` or `ASSUMED` ADR, a bare `## AR-NN` heading or an unconfirmed approval; ask instead.
Omissions count until the ledger records them or the user moves them out of the slice. Mark the slice `done` in
`roadmap.md` only when the gate passes.
Otherwise list the fixes. Suggest `/phx:work` with the plan, or `/phx:investigate` for a failing witness or a load
smoke that errors: quote the error from the server log; a bigger pool or a lighter load only hides the cause.

## Arguments

- **`<slice>`** — slice number (`02`) or plan slug
- **`--no-run`** — audit existing evidence only (evidence for new code is `not-run`). Compare `fp .` with the newest
  record's target-after identity first; when they differ (any commit, docs included), stop before the audits, which would only score `stale`, and suggest a full run
- **`--full`** — whole test suite plus format check
