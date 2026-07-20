#!/usr/bin/env bash
# 05_git_dep — new :git dep introduced in NEW mix.exs (Rule 5: diff fixture).
set -u
mkdir -p "${FIXTURE_DIR}/old" "${FIXTURE_DIR}/new"

cat > "${FIXTURE_DIR}/old/mix.exs" <<'EOF'
defmodule Squat.MixProject do
  use Mix.Project
  def project, do: [app: :squat, version: "0.1.0", deps: deps()]
  defp deps, do: [{:jason, "~> 1.4"}]
end
EOF

cat > "${FIXTURE_DIR}/new/mix.exs" <<'EOF'
defmodule Squat.MixProject do
  use Mix.Project
  def project, do: [app: :squat, version: "0.2.0", deps: deps()]
  defp deps do
    [
      {:jason, "~> 1.4"},
      {:phoenix_extras, git: "https://github.com/attacker/phoenix_extras.git", ref: "deadbeef"}
    ]
  end
end
EOF
