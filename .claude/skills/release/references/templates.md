# Release Templates & Gotchas

## CHANGELOG: before → after

**Before** (work accumulates here):

```markdown
## [Unreleased]

### Added

- Feature X ...

### Fixed

- Bug Y ...
```

**After** (finalize for release `X.Y.Z` on date `YYYY-MM-DD`):

```markdown
## [Unreleased]

### Added

### Changed

### Fixed

## [X.Y.Z] - YYYY-MM-DD

<optional one-line summary of the release>

### Added

- Feature X ...

### Fixed

- Bug Y ...
```

Keep the empty `## [Unreleased]` scaffold on top so the next cycle has a home.

## Release notes for `gh`

Use the new version's CHANGELOG section verbatim. Extract it to a temp file:

```bash
# pull the section between "## [X.Y.Z]" and the next "## ["
awk '/^## \[X\.Y\.Z\]/{f=1} f&&/^## \[/&&!/X\.Y\.Z/{exit} f' CHANGELOG.md > /tmp/relnotes.md
gh release create vX.Y.Z --title "vX.Y.Z — <summary>" --notes-file /tmp/relnotes.md
```

Title format matches history: `vX.Y.Z — <short summary>` (em dash).

## Commit message shape (matches `git log`)

```
Release vX.Y.Z — <short summary>

<optional body: what changed, why it's this bump level>

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
```

Release commits historically touch only `CHANGELOG.md` + `plugin.json`
(+ `README.md` when counts/banners change). Keep unrelated files out.

## `make ci` gate notes

`make ci` = `lint test validate eval-all`. The lint glob is `**/*.md` minus a
fixed `--ignore` list. Untracked non-source dirs (`social/`, `.rtk/`, scratch)
are NOT plugin docs — if they trip lint, add them to the `--ignore` list in the
`lint` / `lint-fix` Makefile targets rather than editing the promo/cache files
or shipping with a red gate. That fix is a standalone `chore(lint)` commit, not
part of the release commit.

If only specific changed files matter, lint them directly to confirm clean:

```bash
npx markdownlint CHANGELOG.md README.md plugins/.../changed.md
```

## Gotchas

- **`claude plugin tag` does not work here.** Marketplace layout puts
  `plugin.json` under `plugins/elixir-phoenix/.claude-plugin/`, not repo root.
  Tagging is always manual: `git tag vX.Y.Z && git push origin vX.Y.Z`.
- **Users only get updates when `plugin.json` version changes** (install cache).
  CHANGELOG/code changes alone are invisible to installed users.
- **Version consolidation**: phased per-branch bumps that never released should
  collapse into ONE bump measured from the last released tag — don't release a
  chain of intermediate patch versions.
- **Force-push is hook-blocked.** `block-dangerous-ops.sh` rejects
  `git push --force`. If you truly need it, the user runs it via `!`.
- **Three-way match**: `plugin.json` version, the CHANGELOG `## [X.Y.Z]`
  heading, and the `vX.Y.Z` tag must all agree. A mismatch ships a confusing
  release.
- **Tag the release commit**, not an earlier one: create the tag AFTER the
  `Release vX.Y.Z` commit so `git describe` resolves correctly.
