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
2. **EVIDENCE IS RECORDED BY `ev run`** — exit status, target and source identity before and after, redacted environment and log, written before anyone interprets them; identity that moved means `stale`
3. **THE OBLIGATIONS ARE THE DENOMINATOR** — from the slice seed, the analyses and a source completeness check, never from the tests that happen to exist
4. **NO PASS BY EXCLUSION** — skipped, excluded, stubbed or stale results never count; pre-existing findings are still findings
5. **NEVER RUN THE LEGACY APP** — evidence comes from the Elixir target only; the source is read and fingerprinted, never executed; suites hit the port, legacy tests are translated
6. **DONE MEANS THE GATE PASSED** — every obligation `pass`, or changed or retired by an accepted ADR or a user-approved AR record, and no BLOCKER

## Workflow

### 1. Resolve the slice

Find `.claude/plans/rewrite-{NN}-*/` (or the slug). Read its `interview.md`
(Acceptance Criteria, External Contracts, `## Oracle`, ledger IDs) and `progress.md` if present.
`TARGET` is the current directory and must contain `mix.exs`; `SOURCE` is the legacy path recorded in
`.claude/rewrite/status.md`. `EV=.claude/rewrite/verify/{NN}/evidence`.

Every record comes from the bundled script; define `ev` in every shell call (`EV_PATH` keeps PATH past a `python3` shim):

```bash
ev() { EV_PATH="$PATH" python3 "${CLAUDE_SKILL_DIR}/scripts/evidence.py" "$@"; }
```

- **Identity** — `scripts/fingerprint.py`, which `ev` calls: `head` and a `content_fingerprint`, SHA-256 over every dirty
  file (tracked changes plus untracked, non-ignored files), every file in each submodule work tree, or every file outside
  git or under a split index (`mode: tree`). Git runs with hooks, filters and fsmonitor disabled and never writes the index
- **Excludes** — `.claude/rewrite/verify/`, `_build/`, `deps/` and `node_modules/` by default; `ev init` fixes one list for
  the run, so add `--exclude cover/` there, and only for output the run itself writes
- **Capture failed** — DIR unreadable, git cannot list changes, or a file flagged `assume-unchanged`/`skip-worktree` (git
  hides its edits): `ev status` says `incomplete`. Ask the user to clear the flag; never clear it yourself

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
- **Config chain** — `config/config.exs`, `config/test.exs`, every file their `import_config` reaches, `config/runtime.exs` (runs under `MIX_ENV=test` too), and `config/prod.exs` for the release
- **In those files** — Repo `url:`, `hostname:`, `database:` and any `System.get_env`/`fetch_env!` feeding them; mailer, push, HTTP and webhook adapters or base URLs; Oban `testing:`; node connections

```bash
grep -nE 'aliases|compilers:|System\.cmd|ecto\.(drop|reset)|"cmd ' mix.exs
grep -nE 'import_config|url:|hostname:|database:|System\.(get_env|fetch_env)|adapter:|testing:|base_url|ip:' config/{config,test,runtime,prod}.exs
```

Stop with the preflight `blocked` when any of these holds:

- **Database** — not shown disposable (local host or tmp path, a test-only database, SQL sandbox pool); a `_test` name alone is not proof
- **Environment** — the database or an endpoint is configured from a variable that is `non-local` or unchecked
- **Side effects** — mail, push, webhooks or HTTP could reach real endpoints, or a black-box command targets a non-local host
- **Mix steps** — an alias or compiler step is destructive or networked

Never run a command to find out whether it was safe; ask the user with the redacted reason (`--no-run` skips straight to
the audits with evidence `blocked`). Record the release's endpoint `ip:` as read: a wildcard exposes it to the network.

### 3. Capture evidence

Start the run with `ev init {NN} --source "$SOURCE"`, which moves earlier records to `verify/{NN}/superseded/`. Then write
the run list, `$EV/commands.md`, before running anything, one line per command: `` - `NAME` — command — why ``. List
`MIX_ENV=test mix compile --warnings-as-errors` and `mix test` on the slice's test files (with `--full`, the whole suite and
`mix format --check-formatted`); every command an acceptance criterion names, with its arguments as named (the named seeds,
not a random one; `--force`, the full suite, a test outside the slice paths, a release smoke, a static check such as `rg` or
`git diff`); and every `## Oracle` command (one per black-box file, whole-file diagnostics, the load script as a short
smoke, with a `checks` threshold: k6 exits 0 when checks fail). Leave one out only when it cannot run here (a missing tool, a blocked preflight), and say so; a `/phx:work` log
never stands in.

Run each one as `ev run {NN} NAME [--cwd DIR] [--expect-exit N] -- CMD`: it captures both identities, runs the command
without a shell, captures them again, writes `$EV/{ts}-NAME.md` (exit, times, identities, env names, ExUnit counts) and its
`.log`, and exits with the command's status. Pass variables as `env NAME=value` (secret-like values are redacted); `{uid}`
becomes a value unique to the record. Never write a record by hand or copy a run script, this run's or another slice's:

```bash
ev run {NN} compile -- env MIX_ENV=test mix compile --warnings-as-errors
ev run {NN} ac17-rg --expect-exit 1 -- rg -n '^\s*([^#\s].*)?Repo\.' lib/{app}_web  # must find nothing; skips comment lines
```

For black-box files, start the port as it ships, never a dev server (its `debug_errors` page answers HTML where the release
answers the envelope), on a database this run creates and drops; never point a suite at the legacy app. `ev port start`
runs the release with `RELEASE_DISTRIBUTION=none` in its own process group, and `ev port stop` stops only that group;
`pkill` or `killall` by pattern stops the user's other BEAM processes:

```bash
ev run {NN} release -- env MIX_ENV=prod mix release --overwrite
ev port start {NN} --release _build/prod/rel/{app}/bin/{app} --ready-url http://localhost:{port}/  # export DATABASE_URL and secrets in this call
ev run {NN} oracle-auth --cwd "$ORACLE" -- hurl --test --variable host=http://localhost:{port} --variable uid={uid} hurl/auth.hurl
ev port stop {NN}
```

### 4. Audit in parallel

Run `ev status {NN}`, which checks each `commands.md` name against its newest record; run every `missing` name and re-run
every `incomplete` or `outdated` one (auditors score records, never a later re-run). Agents cannot run plugin scripts, so
pass `ev current {NN}` as `CURRENT_IDENTITY` and, errors included, `python3 "${CLAUDE_SKILL_DIR}/../architect/scripts/ledger.py"
obligations --slice .claude/plans/{slug}/interview.md` as `OBLIGATION_IDS`. Build `COMPLETENESS`: the slice's ledger IDs and
source anchors from `interview.md` and the ledger rows, nothing wider. Spawn both in ONE message with `run_in_background: true`
and wait for both completion notices; never schedule a wakeup or heartbeat while waiting (it re-enters a finished run):

- **`rewrite:idiom-auditor`** — `TARGET`, `SCOPE` (`git diff --name-only` from the slice's base commit in `progress.md`, else the slice's modules), `LEDGER`, `ARCHITECTURE`,
  `CONTRACTS=.claude/rewrite/analysis/contracts.md`, `KB=.claude/rewrite/kb/`, `OUTPUT=.claude/rewrite/verify/{NN}/idiom.md`
- **`rewrite:parity-auditor`** — `TARGET`, `SOURCE`, `COMPLETENESS`, `OBLIGATIONS` (the interview path plus the analyses),
  `LEDGER`, `EVIDENCE=$EV`, `CURRENT_IDENTITY`, `DECISIONS` (`.claude/rewrite/architecture/`,
  `.claude/rewrite/verify/accepted-risks.md`), `CLAIMS` (`progress.md`, `scratchpad.md`, PR text if any), `OBLIGATION_IDS`, `PREVIOUS` (this slice's
  `verify/{NN}/parity.md` renamed to `parity-previous.md`; none on a first round; never another slice's), `OUTPUT=.claude/rewrite/verify/{NN}/parity.md`

### 5. Apply ledger updates

Apply only the parity auditor's `Proposed Ledger Updates` that have a basis, editing the Impl and Evidence columns of
`.claude/rewrite/ledger.md`. Never write a Departure cell, an ADR status or an AR record yourself. Only the user creates
or approves an accepted risk, in `.claude/rewrite/verify/accepted-risks.md`:

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

A failing `check`, a nonzero `stats` (1 = malformed ledger, 2 = unreadable slice) or 0 selected rows fails the gate, unless the slice's `roadmap.md` row lists no ledger rows.

### 6. Report and gate

Report the parity auditor's states, quoting each row's obligation text from `parity.md` rather than describing it again. A
record made after the audits changes no state until a new audit scores it. Write
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
smoke that errors: quote the error from the server log; a bigger pool or a lighter load only hides the cause. A behavior
the user adds or changes after a round gets a new case ID in the seed's Acceptance Criteria (`obligations` must still
pass): a plan task alone is outside the denominator. The report ends the run: no wakeup or loop re-checks it.

## Arguments

- **`<slice>`** — slice number (`02`) or plan slug
- **`--no-run`** — audit existing evidence only (evidence for new code is `not-run`). Run `ev status {NN}` first; when a
  record is `outdated` (any commit, docs included), stop before the audits, which would only score `stale`, and suggest a full run
- **`--full`** — whole test suite plus format check
