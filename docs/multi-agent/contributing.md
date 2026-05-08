# Contributing to the multi-agent plugin

## File issues here, not in the mirrors

Bug reports, feature requests, and PRs go to:

> `oliver-kriska/claude-elixir-phoenix`

The Pi and OpenCode mirror repos (`pi-elixir-phoenix`,
`opencode-elixir-phoenix`) are **force-pushed** at release time and have
no meaningful git history. Anything you push there will be wiped on the
next release.

## Editing skills, agents, hooks

Edit canonical files only:

- `plugins/elixir-phoenix/skills/<name>/SKILL.md`
- `plugins/elixir-phoenix/agents/<name>.md`
- `plugins/elixir-phoenix/hooks/scripts/*.sh`
- `plugins/elixir-phoenix/hooks/hooks.json`

Then run:

```bash
make port           # regenerate targets/
make port-validate  # confirm no drift
make eval           # score changed skills/agents
```

Commit both the source change and the regenerated `targets/`. CI will
fail on drift if the two get out of sync.

## Editing target-specific transforms

Per-target divergence belongs in `scripts/port_lib/<target>.py`. If
Codex needs a special header in `interface{}`, that goes in
`port_lib/codex.py` — not in 43 SKILL.md files.

If you add a new transform that applies to multiple targets, put it in
`scripts/port_lib/skill_transforms.py` and call it from each target's
`_port_skill()`.

## Editing CI

`.github/workflows/lint.yml` runs all checks (lint, python, shell,
security, test, eval, port-validate). Add new jobs there.

`.github/workflows/publish-mirrors.yml` is release-only and should rarely
need editing.

## Releases

1. Edit canonical files; run `make port`.
2. Bump `plugins/elixir-phoenix/.claude-plugin/plugin.json` `version`.
3. Update `CHANGELOG.md` under `[Unreleased]` → rename to `[X.Y.Z]`.
4. Commit + push.
5. Tag `vX.Y.Z` — `publish-mirrors.yml` fires and pushes to mirrors.

## Adding a new target

1. Create `targets/<new-target>/.gitkeep`.
2. Add `scripts/port_lib/<new-target>.py` with `build(source_dir, out_dir)`.
3. Register in `scripts/port.py`'s `BUILDERS` dict.
4. (If mirror is needed) add to `MIRROR_REMOTES` in `scripts/publish.py`
   and to the matrix in `publish-mirrors.yml`.
5. Add `docs/multi-agent/<new-target>.md`.
6. Run `make port` and commit the generated tree.

## Don't

- Don't hand-edit `targets/`. CI fails on drift.
- Don't push to the mirrors directly.
- Don't bump the version without running `make port` first — stale
  `targets/plugin.json` files cause version mismatches in mirrors.
