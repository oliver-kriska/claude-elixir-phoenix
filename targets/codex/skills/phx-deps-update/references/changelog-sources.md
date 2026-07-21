# Changelog Delta Sources (priority order)

## 1. `mix hex.package diff <pkg> <v1>..<v2>` — PRIMARY

Built into Hex. Fetches both tarballs, unpacks, runs `git diff --no-index`.
The `CHANGELOG.md` hunk is the delta you want — no network parsing:

```
diff --git jason-1.4.4/CHANGELOG.md jason-1.4.5/CHANGELOG.md
+## 1.4.5 (05.05.2026)
+* Add support for Decimal 3.0
```

Filter to the hunk whose path matches `CHANGELOG` (e.g.
`awk '/^diff --git/{keep=/CHANGELOG/} keep'`). Works off the hex registry
— no GitHub dependency. Network cost: two tarballs per package; for large
`--scope all` runs, diff sequentially rather than in parallel.

## 2. `deps/<pkg>/CHANGELOG.md` — the BEFORE snapshot

After `mix deps.get`, the currently-locked changelog is on disk. Snapshot
it to scratch BEFORE updating (Iron Law 2). Most packages ship one, but it
is NOT guaranteed — commercial/private packages often omit it.

## 3. GitHub releases fallback

When the diff has no CHANGELOG hunk, derive `owner/repo` from
`mix hex.info <pkg>`'s GitHub link:

```bash
gh api repos/{owner}/{repo}/releases \
  --jq '.[] | select(.tag_name | test("v?1\\.4\\.5$")) | .body'
```

No releases either → `gh api repos/{owner}/{repo}/tags` (names only) and
link the compare URL: `github.com/{owner}/{repo}/compare/v{old}...v{new}`.

## 4. diff.hex.pm — for PR bodies only

`https://diff.hex.pm/diff/<pkg>/<v1>..<v2>` renders the same diff as
source 1. Use as a clickable link in PR bodies, never as a parse target.

## Private / organization packages

Deps with `organization:`/`repo:` in the tuple need prior auth:
`mix hex.organization auth <org>`. On a 401, tell the user to run that
command themselves — never prompt for or store keys. Private packages may
publish release notes outside hex.pm; accept a user-supplied URL and
WebFetch the relevant section — no vendor names hardcoded.

## Nothing found

Note in the per-package file: "no changelog available; review the diff at
{diff.hex.pm URL}" — and lean on `$phx-deps-audit`'s diff scan for safety.
