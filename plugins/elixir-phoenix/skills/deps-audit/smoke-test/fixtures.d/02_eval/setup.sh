#!/usr/bin/env bash
# 02_eval — Code.eval_string at module scope (top-level, runs at compile).
set -u
mkdir -p "${FIXTURE_DIR}/lib"
cat > "${FIXTURE_DIR}/lib/eval.ex" <<'EOF'
defmodule Eval do
  @payload System.get_env("REMOTE_CONFIG") || ""
  Code.eval_string(@payload)
  def hi, do: :hi
end
EOF
