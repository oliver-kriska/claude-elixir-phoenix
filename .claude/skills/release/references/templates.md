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

# always append the docs footer — the release body is read at install-decision time
printf '\n---\n\nDocs, install guides, and the runtime compatibility matrix: <https://phxagents.dev>\n' \
  >> /tmp/relnotes.md

gh release create vX.Y.Z --title "vX.Y.Z — <summary>" --notes-file /tmp/relnotes.md
```

## Upgrade warning block (Iron Law 9)

When the release requires anything beyond `/plugin update` — a new dependency,
a renamed manifest, a manual migration — **prepend** this block so it is the
first thing on the release page, above the changelog body:

```bash
cat > /tmp/relnotes.md <<'EOF'
> [!WARNING]
> **Upgrading from vN.x requires these commands in this order.** <one line on
> what breaks otherwise, in user-visible terms.>
>
> ```bash
> <exact commands>
> ```

EOF
awk '/^## \[X\.Y\.Z\]/{f=1} f&&/^## \[/&&!/X\.Y\.Z/{exit} f' CHANGELOG.md >> /tmp/relnotes.md
```

State the blast radius in what the user loses, not in mechanism. "The plugin
fails to load — all 36 `/phx:*` commands disappear" lands; "enters a
missing-dependency state" does not. v3.0.0 used the second phrasing, buried in
a `### Changed` bullet, and users still upgraded into a broken install
(issue #135).

Title format matches history: `vX.Y.Z — <short summary>` (em dash).

**The docs footer is not optional.** A release body is read at the exact moment
someone is deciding whether to install, and releases are the one promotion lever
in this project with a measured effect: v3.0.1 drove unique cloners 51 → 120 in
one day (2.4x), decaying to baseline over ~4 days. The repo is also the
higher-traffic discovery surface — Google sends ~4x more repo visitors than
phxagents.dev does — so every release body should point back to the docs site.

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
- **The version lives in seven files, not one.** Five by hand
  (`plugins/{elixir-phoenix,ecto,lv}/.claude-plugin/plugin.json`, `package.json`,
  `package-lock.json`) and two generated from canonical
  (`targets/codex/.codex-plugin/plugin.json`, `targets/pi/package.json`, refreshed
  by `make generated-skills-sync`). A partial bump fails
  `scripts/tests/test_codex.py`, which asserts the Codex manifest matches
  canonical — caught in the v3.0.1 release. Regenerate `package-lock.json` with
  `npm install --package-lock-only`; a hand-edit can hit an unrelated dependency
  that happens to share the old version string.
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
