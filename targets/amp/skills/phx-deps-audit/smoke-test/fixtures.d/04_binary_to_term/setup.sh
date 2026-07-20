#!/usr/bin/env bash
# 04_binary_to_term — :erlang.binary_to_term/1 without :safe (CVE-2026-21619 class).
set -u
mkdir -p "${FIXTURE_DIR}/lib"
cat > "${FIXTURE_DIR}/lib/unsafe.ex" <<'EOF'
defmodule UnsafeTerm do
  def decode(blob), do: :erlang.binary_to_term(blob)
end
EOF
