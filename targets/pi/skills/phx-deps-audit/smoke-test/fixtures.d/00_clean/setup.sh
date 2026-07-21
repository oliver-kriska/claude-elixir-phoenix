#!/usr/bin/env bash
# 00_clean — benign Elixir package, zero findings across all native rules.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
cat > "${FIXTURE_DIR}/mix.exs" <<'EOF'
defmodule Clean.MixProject do
  use Mix.Project
  def project, do: [app: :clean, version: "0.1.0", deps: deps()]
  defp deps, do: [{:jason, "~> 1.4"}]
end
EOF
cat > "${FIXTURE_DIR}/lib/clean.ex" <<'EOF'
defmodule Clean do
  @moduledoc "Benign Elixir module — zero findings expected."
  def hello, do: "world"
end
EOF
