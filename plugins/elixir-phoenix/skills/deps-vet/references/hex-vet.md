# `hex_vet.exs` — schema, parser, and lookup

The audit ledger. Lives at **project root**, alongside `mix.exs` and
`mix.lock`. Modeled on cargo-vet's `audits.toml` — same trust-chain
intent, idiomatic Elixir surface.

## Why project root, not `.claude/`

`hex_vet.exs` is a **deliverable security artifact**, not an ephemeral
sidecar. Three properties of root placement that `.claude/` doesn't
give us:

1. **Visible in PR review.** Adding a vetted dep shows up as a diff
   line on the same file as `mix.lock`, prompting the reviewer to
   look at both.
2. **CI-discoverable without configuration.** The triple
   `mix.lock` / `mix.exs` / `hex_vet.exs` is recognizable —
   security tooling can find the ledger without project-specific
   config.
3. **Survives `.claude/` deletion.** Some teams treat `.claude/` as
   per-developer state and gitignore it. The audit ledger has to be
   shared.

Phase 1's `last-run.json` stays under `.claude/deps-audit/`
intentionally — that file is ephemeral run state, not durable trust.

## Schema

```elixir
# hex_vet.exs
%{
  imports: %{
    # Phase 3+ feature — distributed audit imports. Ignored in Phase 2.
    # mozilla: "https://hg.mozilla.org/.../audits.toml"
  },
  audits: [
    %{
      package: "phoenix",
      version: "1.7.21",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Reviewed against rules 1-8; diff.hex.pm checked clean.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "jason",
      version: "1.4.4",
      criteria: :safe_to_deploy,
      reviewer: "team@example.com",
      notes: "No findings; widely-used (>50M downloads).",
      reviewed_at: ~D[2026-05-10]
    }
  ],
  policy: %{
    criteria_required: :safe_to_deploy,
    block_on_unvetted: false  # Phase 2 default; Phase 3 promotes to true
  }
}
```

### Criteria atoms

Following cargo-vet's vocabulary, three Phase 2 criteria are
recognized:

| Atom | Meaning |
|------|---------|
| `:safe_to_deploy` | Reviewed; safe in production. Highest trust. |
| `:safe_to_run` | Safe in non-production envs (test/dev deps). |
| `:does_not_implement_crypto` | Sub-criterion; package contains no cryptographic implementation, so transitive crypto-review obligations don't apply. |

Other atoms are valid but unrecognized — Phase 2 treats them as a
softer match (logged, never trusted).

### Empty ledger stub

Used when `hex_vet.exs` doesn't exist:

```elixir
%{
  imports: %{},
  audits: [],
  policy: %{criteria_required: :safe_to_deploy, block_on_unvetted: false}
}
```

## Parser

Use `Code.eval_file/1` — Elixir's own parser, no Sourceror needed:

```bash
# One-line read:
mix run --no-mix-exs -e '
  {ledger, _} = Code.eval_file("hex_vet.exs")
  IO.inspect(ledger.audits, limit: :infinity)
'
```

Inside a skill script the same call works via `mix run -e`. For lookup
performance, the ledger is small (target: <2,000 entries; 50K LOC
file). No streaming parser needed.

### Lookup function

```elixir
def vetted?(ledger, pkg, version, required \\ :safe_to_deploy) do
  Enum.any?(ledger.audits, fn audit ->
    audit.package == pkg and
      audit.version == version and
      meets_criteria?(audit.criteria, required)
  end)
end

defp meets_criteria?(:safe_to_deploy, _required), do: true
defp meets_criteria?(:safe_to_run, :safe_to_run), do: true
defp meets_criteria?(other, other), do: true
defp meets_criteria?(_, _), do: false
```

`:safe_to_deploy` satisfies every requirement (deploy implies run).
`:safe_to_run` only satisfies `:safe_to_run`.

## Lock-vs-ledger disagreement (Day-1 decision: lock wins)

When `mix.lock` says `phoenix 1.7.21` and the ledger has an entry for
`phoenix 1.7.20`:

- The unmatched lock version (1.7.21) is **unvetted**.
- The orphaned ledger entry (1.7.20) is **informational** — emit an
  INFO finding "ledger entry exists for older version 1.7.20; treating
  1.7.21 as unvetted."
- The audit runs the full Phase 1 rule pass on 1.7.21 with normal
  severities.

This is the conservative call. The alternative ("lock-version-or-higher
trust") would let attackers exploit version-bump attacks where the
ledger entry was approved on a safe version.

## Append flow

Round-trip through `inspect/2` to preserve Elixir term semantics:

```bash
mix run --no-mix-exs -e '
  {ledger, _} = Code.eval_file("hex_vet.exs")
  new_audit = %{
    package: "<pkg>",
    version: "<ver>",
    criteria: :safe_to_deploy,
    reviewer: System.cmd("git", ["config", "user.email"]) |> elem(0) |> String.trim(),
    notes: "<notes>",
    reviewed_at: Date.utc_today()
  }
  updated = Map.update!(ledger, :audits, &[new_audit | &1])
  formatted = updated
              |> inspect(pretty: true, limit: :infinity, width: 80)
              |> Code.format_string!()
              |> IO.iodata_to_binary()
  File.write!("hex_vet.exs", formatted <> "\n")
'
```

`Code.format_string!/1` ensures the output matches the project's
formatter config (incl. `.formatter.exs` overrides). Test the
round-trip on a fixture before relying on it — version pinning matters.

## Migration from existing trust artifacts

For projects using ad-hoc trust mechanisms (a comment in `mix.exs`,
README sections, internal wiki pages), the seed-import flow
(`/phx:deps-vet --seed`) lets a team bootstrap a real ledger from
the top-100 list and then layer in project-specific audits.

The seed is regenerated monthly; entries older than 90 days emit a
stale-warning. See `seed.md` for the regeneration job.
