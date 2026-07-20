# Auto-generated seed ledger for /phx:deps-vet --seed.
#
# Source: hand-curated representative set drawn from the top Hex packages
# by download count. Imported into a project's hex_vet.exs via:
#
#     /phx:deps-vet --seed
#
# Stale-warning kicks in at 90 days from generated_at. The plugin's CI
# regenerates this file monthly via .github/workflows/seed-regen.yml.
#
# Schema matches hex_vet.exs (see deps-vet/references/hex-vet.md).
%{
  generated_at: ~D[2026-05-12],
  source: "https://hex.pm/api/packages?sort=downloads",
  source_commit: "manual-curation-v0",
  audits: [
    %{
      package: "phoenix",
      version: "1.7.21",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Reviewed against rules 1-8; 100M+ downloads, active maintainer.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "phoenix_live_view",
      version: "1.0.5",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "1.0 release; long-running review history.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "phoenix_html",
      version: "4.1.1",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core Phoenix; trivial surface.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "phoenix_pubsub",
      version: "2.1.3",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core Phoenix; stable since 2.0.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "phoenix_ecto",
      version: "4.6.2",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core Phoenix; bridges Phoenix + Ecto.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "jason",
      version: "1.4.4",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Most-downloaded Elixir lib; very small surface.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "ecto",
      version: "3.12.4",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core; widely audited.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "ecto_sql",
      version: "3.12.1",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core; widely audited.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "postgrex",
      version: "0.19.3",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "PostgreSQL driver; core OTP integration.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "decimal",
      version: "2.1.1",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Pure-Elixir arbitrary-precision decimals; stable since 2.0.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "plug",
      version: "1.16.1",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Core; the Phoenix HTTP adapter spec.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "plug_crypto",
      version: "2.1.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Crypto helpers; constant-time comparisons; audited via Plug.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "telemetry",
      version: "1.3.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Erlang Ecosystem Foundation library; stable.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "telemetry_metrics",
      version: "1.1.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "EEF; companion to telemetry.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "telemetry_poller",
      version: "1.1.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "EEF; companion to telemetry.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "bcrypt_elixir",
      version: "3.2.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Crypto: bcrypt password hashing; uses NIF (audited upstream).",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "argon2_elixir",
      version: "4.0.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Crypto: Argon2 hashing; uses NIF (audited upstream).",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "oban",
      version: "2.18.3",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Background jobs; Postgres-backed; widely deployed.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "mox",
      version: "1.2.0",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Test-only library; concurrency-safe mocks. Run-only criteria.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "ex_machina",
      version: "2.8.0",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Test factories. Run-only criteria.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "stream_data",
      version: "1.1.1",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Property-based testing data generators. Run-only.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "credo",
      version: "1.7.10",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Static analysis; dev/test dep. Run-only.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "sobelow",
      version: "0.13.0",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Security-focused static analysis. Run-only.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "dialyxir",
      version: "1.4.4",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Dialyzer wrapper; dev/test dep. Run-only.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "mix_audit",
      version: "2.1.4",
      criteria: :safe_to_run,
      reviewer: "oliver@ideax.sk",
      notes: "Hex package CVE auditor. Run-only.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "castore",
      version: "1.0.10",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "CA certificate store; updates pinned via Mix.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "mint",
      version: "1.6.2",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Process-less HTTP client; EEF.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "finch",
      version: "0.19.0",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "HTTP client built on Mint; widely deployed.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "gettext",
      version: "0.26.2",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "i18n; PO file parsing.",
      reviewed_at: ~D[2026-05-12]
    },
    %{
      package: "swoosh",
      version: "1.17.4",
      criteria: :safe_to_deploy,
      reviewer: "oliver@ideax.sk",
      notes: "Email; widely deployed.",
      reviewed_at: ~D[2026-05-12]
    }
    # Add more entries via /phx:deps-vet <pkg> <version> or by running
    # the seed regen CI job (.github/workflows/seed-regen.yml).
  ],
  policy: %{
    criteria_required: :safe_to_deploy,
    block_on_unvetted: false
  }
}
