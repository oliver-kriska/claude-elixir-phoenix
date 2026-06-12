# Real-package corpus

Loader and cache for real Hex tarballs used in calibration runs (Component 8).

These fixtures are **not** part of the default `runner.sh` pass — that one
runs offline against synthetic fixtures in `fixtures.d/`. The corpus is
fetched on demand by `fetch.sh` and consumed by:

- The benign FP bench (~100 packages, target <2 % FP)
- Real-world CVE calibration (`hex_core`, `hex`, `rebar3` for CVE-2026-21619)

## Quick start

```bash
bash corpus.d/fetch.sh phoenix 1.7.21
bash corpus.d/fetch.sh --batch corpus.d/benign-100.txt
bash corpus.d/fetch.sh --prune   # drop tarballs >30 days old
```

## Cache location

Defaults to `~/.cache/phx-deps-audit/corpus/<pkg>/<version>/`.
Override with `HEX_AUDIT_CACHE` env var. Mirrors the cache layout used
by Phase 1 rule helpers in `references/tarball-fetcher.md`.

## Why not commit the tarballs?

Hex tarballs are 100KB-10MB each. Committing 100 of them bloats the
plugin distribution. The loader is reproducible — pin versions in
`benign-100.txt` and the corpus is regenerable from `repo.hex.pm`.
