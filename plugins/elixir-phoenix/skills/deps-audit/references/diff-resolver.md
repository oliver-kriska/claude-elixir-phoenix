# Diff Resolver — Lock File Comparison

Resolves `(pkg, old_version, new_version)` tuples for each mode.

The plugin has no `lib/` directory, so this lives as shell + `mix run -e`
snippets invoked from the skill body. Pseudocode is the spec; the snippets
below are the runtime.

## Lock file format

`mix.lock` is an Erlang term map:

```elixir
%{
  "phoenix" => {:hex, :phoenix, "1.7.14", "checksum", :mix, [...], "hexpm", "hash"},
  "ecto" => {:hex, :ecto, "3.13.2", ...},
  ...
}
```

Position 3 (zero-indexed: 2) is the version string. The Erlang term format
has been stable since Hex 0.20 (2019).

## Parsing — Elixir route (authoritative)

Use `Code.eval_file/1` to get a proper map:

```bash
mix run --no-deps-check --no-compile -e '
  lock = Code.eval_file("mix.lock") |> elem(0)
  for {pkg, tup} <- lock, do: IO.puts("#{pkg}\t#{elem(tup, 2)}")
'
```

Output: tab-separated `pkg<TAB>version` lines. Reliable across all Hex
versions. Requires the project to compile; for very early/broken states use
the shell fallback below.

## Parsing — Shell fallback (when Mix won't run)

```bash
# Extract pkg + version pairs from raw mix.lock without mix
awk -F'"' '/^  "/ {pkg=$2; getline; getline; if (match($0,/"[0-9][^"]+"/)) {print pkg"\t"substr($0,RSTART+1,RLENGTH-2)}}' mix.lock
```

Approximate — works for vanilla `:hex` entries, may misparse `:git` /
`:path` deps (which is fine, they're flagged by Rule 5 anyway).

## Mode B — working vs HEAD

```bash
mkdir -p .claude/deps-audit/cache

git show HEAD:mix.lock > .claude/deps-audit/cache/lock.old 2>/dev/null \
  || echo '%{}' > .claude/deps-audit/cache/lock.old

cp mix.lock .claude/deps-audit/cache/lock.new
```

Then run the parser on both files and diff in Elixir:

```bash
mix run --no-deps-check --no-compile -e '
  parse = fn path ->
    {map, _} = Code.eval_file(path)
    Map.new(map, fn {k, v} -> {k, elem(v, 2)} end)
  end

  old_map = parse.(".claude/deps-audit/cache/lock.old")
  new_map = parse.(".claude/deps-audit/cache/lock.new")

  changed = for {pkg, nv} <- new_map, ov = old_map[pkg], nv != ov, do: {pkg, ov, nv}
  added   = for {pkg, nv} <- new_map, !Map.has_key?(old_map, pkg), do: {pkg, nil, nv}
  removed = for {pkg, ov} <- old_map, !Map.has_key?(new_map, pkg), do: {pkg, ov, nil}

  IO.puts(Jason.encode!(%{changed: changed, added: added, removed: removed}))
' > .claude/deps-audit/cache/diff.json
```

If `Jason` isn't available (some early-stage projects), substitute
`:erlang.term_to_binary` + Base64, or fall back to `inspect/2` and parse
text.

## Mode C — `--base <ref>`

Identical to Mode B but substitute the HEAD source:

```bash
git show "${BASE_REF}:mix.lock" > .claude/deps-audit/cache/lock.old 2>/dev/null \
  || { echo "ERROR: ${BASE_REF}:mix.lock not found"; exit 2; }
```

Validate `<ref>` before use:

```bash
git rev-parse --verify "${BASE_REF}^{commit}" >/dev/null 2>&1 \
  || { echo "ERROR: ${BASE_REF} is not a valid git ref"; exit 2; }
```

## Mode A — `--preview [pkg...]`

Locked version = position 3 of the entry. Latest version = Hex API.

```bash
# Locked side
mix run --no-deps-check --no-compile -e '
  {map, _} = Code.eval_file("mix.lock")
  Map.new(map, fn {k, v} -> {k, elem(v, 2)} end)
  |> Jason.encode!()
  |> IO.puts()
' > .claude/deps-audit/cache/lock.locked.json

# Latest side — query Hex API for each requested package
for pkg in "$@"; do
  curl -fsSL \
    -H "Accept: application/vnd.hex+json" \
    "https://hex.pm/api/packages/${pkg}" \
  | jq -r '.releases[0].version' \
  > ".claude/deps-audit/cache/${pkg}.latest"
done
```

Cap at 50 packages — warn and exit if `$#` > 50:

```bash
if [ "$#" -gt 50 ]; then
  echo "WARN: --preview capped at 50 packages, got $#. Specify a subset."
  exit 2
fi
```

If no packages specified, expand to all keys from `mix.lock` (still capped).

## Output contract

The resolver emits one JSON object to
`.claude/deps-audit/cache/diff.json`:

```json
{
  "mode": "B" | "C" | "A",
  "base": "HEAD" | "<ref>" | null,
  "changed": [["phoenix", "1.7.14", "1.7.20"], ...],
  "added":   [["new_pkg", null, "0.1.0"], ...],
  "removed": [["old_pkg", "1.2.3", null], ...]
}
```

Downstream steps (fetch, rule run, render) read this single file.

## Edge cases

| Case | Behavior |
|------|----------|
| No `mix.lock` in HEAD (initial commit) | Treat all working entries as `added` |
| Working `mix.lock` missing | ERROR — bail with `mix deps.get` suggestion |
| `:git` entry in lock | Version is the SHA. Rule 5 flags it; diff still emits the tuple |
| `:path` entry | Same as `:git` — flagged by Rule 5 |
| Lockfile in conflict (`<<<<<<< HEAD`) | ERROR — refuse to audit, suggest resolving first |
| Working ≡ HEAD (no changes) | Empty `changed/added/removed` arrays → renderer prints "No dep changes since HEAD" |

## Test fixtures

`test/fixtures/deps-audit/lockfiles/` (created in Component 8):

- `clean.lock` — no changes vs `clean.lock` (baseline)
- `bump.lock` — single minor bump (`phoenix 1.7.14 → 1.7.20`)
- `added.lock` — new package added
- `git-dep.lock` — `:git` entry (triggers Rule 5)
- `conflict.lock` — merge conflict markers (resolver should refuse)
