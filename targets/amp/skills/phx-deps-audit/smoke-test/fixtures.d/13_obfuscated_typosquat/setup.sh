#!/usr/bin/env bash
# 13_obfuscated_typosquat — bidi-rewritten function name to disguise a
# typosquat. Real attack vector: package "phoeniix" with bidi-reordered
# identifier looking like "phoenix" in editors with naive RTL handling.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
# U+202E RTL OVERRIDE inside an identifier-adjacent comment.
printf 'defmodule Phoeniix do\n  # \xe2\x80\xae normal-looking comment\n  def hello, do: :world\nend\n' \
  > "${FIXTURE_DIR}/lib/phoeniix.ex"
