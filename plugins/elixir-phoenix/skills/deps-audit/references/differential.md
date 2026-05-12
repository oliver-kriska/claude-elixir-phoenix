# Differential mode — NDJSON set-subtract

Phase 2 reduces the false-positive baseline by running each rule pass
on the **OLD tarball** as well as the **NEW tarball**, then subtracting
the findings that already existed in the dependency. Only the truly
new signals reach the renderer at full severity.

This isn't a function refactor — Phase 1's rules emit NDJSON to
`findings.jsonl`. Differential mode runs them twice and diffs the
output stream.

## Iron Laws

1. **Set-subtract on findings, not source.** Diffing files would
   require AST normalization and is fragile. Diffing on finding keys
   is rule-aware and stable across reformatting.
2. **Polymorphic keys, not a single tuple.** Three keying shapes
   covering all 8 rules — picking one universal key would have to
   degrade to "rule_id + everything," which is no key at all.
3. **Carried-over signals are INFO, not silenced.** A finding that
   existed before AND still exists IS still real — it's just not
   the news. Downgrade severity, emit with `differential: carried`.
4. **Cache invalidates on rule change.** The cache key MUST include a
   rules-checksum (`sha256` of `rules-impl.md` mtime + commit SHA).
   Otherwise a rule-semantics change leaves stale findings around.

## Architecture

```
Phase 1 engine:    bash rules → findings.jsonl  on NEW

Phase 2 engine:    bash rules → findings.jsonl       on NEW
                   bash rules → findings.old.jsonl   on OLD   ← new pass
                                       ↓
                   scripts/diff_findings.py
                                       ↓
                   new_signals.jsonl     (in NEW, not OLD)
                   info_signals.jsonl    (in both — downgraded)
                   dropped_signals.jsonl (in OLD, not NEW)
```

## Polymorphic keying

Single-tuple keys are fragile because Phase 1 emits **two finding
shapes** (file-scoped and package-scoped) and Rule 5 is its own
thing. The differ keys per rule_id:

| Rule kind | Rules | Key shape |
|-----------|-------|-----------|
| File-scoped | 1, 2, 3, 4, 7 | `(rule_id, file, fn_name, sha256(snippet)[:12])` |
| Mix-deps diff | 5 | `(rule_id, dep_name, kind)` where kind ∈ {git, path} |
| Package-scoped | 6, 8 | `(rule_id, pkg)` |

### `fn_name` extraction — AST walk, with a regex fallback

For file-scoped rules, the snippet alone is insufficient because two
identical snippets in different functions are different findings. The
extraction walks the source upward from the finding's `line` to the
nearest enclosing `def` / `defp` / `defmacro` / `defmacrop`:

- **Preferred** — rule emitters call `Code.string_to_quoted/2` and
  attach `fn_name` to the JSON object before writing it. Phase 2's
  emit helper extends Phase 1's:

  ```bash
  fn_name_from_ast() {
    # $1 = file, $2 = line
    mix run --no-mix-exs -e "
      {:ok, ast} = File.read!(\"$1\") |> Code.string_to_quoted()
      # Walk AST collecting {fn_name, start_line, end_line}; return
      # the innermost named def enclosing line ${2}, or 'module_scope'.
      IO.write(MyDifferential.fn_name_for_line(ast, ${2}))
    "
  }
  ```

- **Fallback** — `diff_findings.py` does a regex walk upward when
  `fn_name` is missing. Less accurate (won't see `defmacro` inside a
  `quote do`), but sufficient for first-pass stability.

### Why include `sha256(snippet)` in file-scoped keys?

Functions get reformatted between releases — line numbers move, but
the snippet text shifts less. Hashing 12 chars of the snippet gives
us a stable identity even when the file is reformatted, while still
distinguishing two `:erlang.binary_to_term(blob)` calls in different
spots.

## Master-runner extension

`run_all_rules` in `rules-impl.md` accepts an optional `OLD_DIR`
environment variable. When set, every per-tarball rule (1, 2, 3, 4, 7)
runs **twice** — once on `${new_dir}` writing `findings.jsonl`, once on
`${old_dir}` writing `findings.old.jsonl`. Rule 5 already takes both
dirs natively. Rules 6 and 8 (Hex API) are package-scoped and do not
benefit from differential mode (the package itself is the unit).

Once both NDJSON streams exist, the skill body invokes:

```bash
python3 ${CLAUDE_SKILL_DIR}/scripts/diff_findings.py \
    --new  .claude/deps-audit/cache/findings.jsonl \
    --old  .claude/deps-audit/cache/findings.old.jsonl \
    --new-out     .claude/deps-audit/cache/new_signals.jsonl \
    --info-out    .claude/deps-audit/cache/info_signals.jsonl \
    --dropped-out .claude/deps-audit/cache/dropped_signals.jsonl
```

The renderer (see `output-renderer.md`) consumes `new_signals.jsonl`
for the primary report. `info_signals.jsonl` is appended to a
collapsible "carried-over risks" section. `dropped_signals.jsonl`
informs the changelog-style "X risks resolved since previous version"
line — useful as positive signal in PR review.

## Added-package mode

A net-new dependency has no OLD tarball. The differ accepts
`--added-package-mode emit-all` (default) and writes every finding to
`new_signals.jsonl`. This matches Phase 1 behavior — a brand-new
package gets the full audit.

The alternative (`--added-package-mode skip`) is intentionally
available but discouraged: skipping is the correct call only when the
caller already knows the package was vetted at this version via
`hex_vet.exs` (see `hex-vet.md`), and even then the ledger applies a
downgrade rather than full skip.

## Cache invalidation

The Phase 1 cache stores tarballs under
`.claude/deps-audit/cache/<pkg>/<version>/` and prunes after 30 days.
Phase 2 adds findings caching:

```
.claude/deps-audit/cache/findings/
└── <rules-checksum>/
    └── <pkg>/<old>-<new>/
        ├── findings.jsonl
        ├── findings.old.jsonl
        └── diff/
            ├── new_signals.jsonl
            ├── info_signals.jsonl
            └── dropped_signals.jsonl
```

`<rules-checksum>` is the first 12 hex chars of
`sha256(<rules-impl.md mtime> || <git commit SHA>)`. When rules change,
the cache namespace changes too — stale findings can't bleed into a
post-update run. Older `<rules-checksum>` directories are GC'd by
`fetch.sh --prune` together with tarballs.

### Plugin-version skew (Phase 3 hardening)

`<rules-checksum>` alone catches rule-body changes but not changes in
the **runner** (scoring weights, severity mapping, post-processing).
A plugin upgrade that ships a new scorer with the same rules will
silently reuse stale verdicts.

Phase 3 writes `.claude/deps-audit/cache/cache_signature.json` at
audit start:

```json
{
  "plugin_version": "3.0.0",
  "rules_checksum": "a1b2c3d4e5f6",
  "generated_at": "2026-05-15T10:23:00Z"
}
```

On cache read, the audit verifies both `plugin_version` and
`rules_checksum` match the current run. On mismatch:

1. Drop the entire `.claude/deps-audit/cache/findings/` tree
2. Drop `last-run.json` (Phase 1 sidecar — also runner-versioned)
3. Write a fresh `cache_signature.json`
4. Log `cache invalidated: plugin upgraded from X.Y.Z to A.B.C` to stderr

No migration is attempted — cold rebuild is bounded (a 20-pkg PR
re-audits in ~60s on a warm tarball cache) and migration logic is too
fragile to maintain across major bumps. The tarball cache
(`<pkg>/<version>/contents/`) is preserved across signature drops —
tarballs are content-addressed and version-independent.

## When the differ is NOT used

- `--no-differential` — debugging mode; emits Phase 1 findings.jsonl
  unchanged.
- Single-version audit (no OLD ref, no `mix.lock` change). Differ
  falls back to added-package emit-all.

## Performance

The differ is O(n + m) where n = NEW findings, m = OLD findings. With
8 rules × ~5 findings per package per rule × 20 packages in a typical
`mix.lock` PR, a deps PR is ~800 findings. Differ runs in <200 ms.

Cost dominator is the **rule pass on OLD** — running rules 1-4 + 7
twice per package roughly doubles the audit's wall time. Mitigation
options noted in `performance.md` (Phase 3 follow-up): keep OLD
findings cached, only re-run when OLD tarball mtime changes.
