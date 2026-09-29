#!/usr/bin/env bash
# 14_nif_blob — base64-encoded payload inlined at module scope, modeling a
# NIF dropper that decodes a binary and writes it to priv/native at compile
# time. Triggers Rule 7 (long base64 in lib/) today; Rule 11 (NIF injection
# without checksum) is future work.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
PAYLOAD=$(printf 'A%.0s' {1..400})
{
  echo 'defmodule NifBlob do'
  echo "  @blob \"${PAYLOAD}\""
  echo '  def get, do: @blob'
  echo 'end'
} > "${FIXTURE_DIR}/lib/nif_blob.ex"
