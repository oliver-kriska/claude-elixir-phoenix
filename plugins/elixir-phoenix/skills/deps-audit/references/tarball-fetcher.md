# Tarball Fetcher — Cached `mix hex.package fetch`

Fetches and unpacks Hex tarballs for both old and new versions of each
changed package. Caches under `.claude/deps-audit/cache/<pkg>/<version>/`.

## Cache layout

```
.claude/deps-audit/
├── cache/
│   ├── lock.old              # diff-resolver: HEAD/base mix.lock
│   ├── lock.new              # diff-resolver: working mix.lock
│   ├── diff.json             # diff-resolver: {changed, added, removed}
│   ├── hex-api/
│   │   ├── packages/<pkg>.json        # Hex API cache (7-day TTL)
│   │   └── top-500.json                # daily TTL
│   ├── phoenix/
│   │   ├── 1.7.14/                     # unpacked tarball — old
│   │   └── 1.7.20/                     # unpacked tarball — new
│   └── <pkg>/<version>/
└── last-run.json             # renderer: structured findings sidecar
```

## Single-version fetch

```bash
fetch_version() {
  local pkg="$1" version="$2"
  local dest=".claude/deps-audit/cache/${pkg}/${version}"

  # Cache hit: directory exists and has `hex_metadata.config` (always present
  # in a valid Hex tarball)
  if [ -f "${dest}/hex_metadata.config" ]; then
    return 0
  fi

  mkdir -p "$(dirname "${dest}")"
  mix hex.package fetch "${pkg}" "${version}" --unpack -o "${dest}" 2>&1 \
    | grep -v "Fetching\|Unpacked\|^$" || true

  if [ ! -f "${dest}/hex_metadata.config" ]; then
    echo "ERROR: fetch failed for ${pkg} ${version}" >&2
    return 2
  fi
}
```

`mix hex.package fetch` exit code is 0 on success and 1 on network/checksum
failure. Always verify `hex_metadata.config` exists before reporting success
— `mix` is occasionally non-zero on success and zero on transient failure.

## Bulk fetch from `diff.json`

Reads the resolver's output and fetches every `(pkg, old?, new?)` pair:

```bash
fetch_from_diff() {
  jq -c '
    (.changed[] | [.[0], .[1], .[2]]),
    (.added[]   | [.[0], "_skip_old_", .[2]]),
    (.removed[] | [.[0], .[1], "_skip_new_"])
  ' .claude/deps-audit/cache/diff.json \
  | while IFS= read -r row; do
      pkg=$(echo "$row" | jq -r '.[0]')
      old=$(echo "$row" | jq -r '.[1]')
      new=$(echo "$row" | jq -r '.[2]')

      [ "$old" != "_skip_old_" ] && [ "$old" != "null" ] && fetch_version "$pkg" "$old"
      [ "$new" != "_skip_new_" ] && [ "$new" != "null" ] && fetch_version "$pkg" "$new"
    done
}
```

`added` packages have no old to fetch. `removed` packages have no new to
fetch. Both forms produce a single tarball; rules that need both versions
(Rule 5 dep diff, Rule 6 maintainer diff) skip these entries.

## Parallelism

Wrap the inner loop with `xargs -P 4`:

```bash
jq -r '...' .claude/deps-audit/cache/diff.json \
  | xargs -P 4 -I{} bash -c 'fetch_version $@' _ {}
```

Cap at 4 parallel fetches — `hex.pm` is fine with this and avoids
rate-limit headers (`X-Ratelimit-Remaining`).

## Cache pruning

Prune cache entries older than 30 days. Run lazily — once per audit, before
fetching:

```bash
prune_cache() {
  find .claude/deps-audit/cache \
    -mindepth 2 -maxdepth 2 -type d -mtime +30 \
    -print -exec rm -rf {} +
}
```

`-mtime +30` is access-time on macOS by default; use `-amin` or set
`COPYFILE_DISABLE` if needed for cross-platform. Cache files are
content-addressable (pkg@version) so re-fetch on cache miss is cheap.

## `.gitignore` rule

`.claude/deps-audit/cache/` is generated, never committed. Add to
project `.gitignore` if not already covered by `.claude/` wildcard:

```
.claude/deps-audit/cache/
```

Keep `.claude/deps-audit/last-run.json` tracked? **Default: ignore.**
It's a snapshot that becomes stale; the next audit regenerates it. Phase 3
PreToolUse hook reads it to detect "recently audited" but the file is
expected to be local.

## Failure modes

| Failure | Behavior |
|---------|----------|
| Network timeout to `hex.pm` | Print warning, retry once, then BLOCK with exit 2 |
| Package not on `hex.pm` (e.g., `:git` dep) | Skip with note, audit proceeds |
| Disk full | Bail immediately — `mix hex.package fetch` will fail loudly |
| Concurrent audit on same project | Cache writes are idempotent; safe to run twice |
| Cache directory unwritable | Fall back to `${TMPDIR}/phx-deps-audit` |

## Hex API alternative (transport-only)

For Mode A `--preview` we already hit `GET /api/packages/:name` for the
latest version. The tarball is also at:

```
https://repo.hex.pm/tarballs/<pkg>-<version>.tar
```

But that needs manual `tar -xf` + checksum verification. Using
`mix hex.package fetch` is one line and handles signature checking. Stick
with mix.
