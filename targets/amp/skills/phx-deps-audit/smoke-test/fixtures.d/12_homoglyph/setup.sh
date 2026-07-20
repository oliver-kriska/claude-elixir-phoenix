#!/usr/bin/env bash
# 12_homoglyph — Cyrillic 'е' (U+0435) impersonating Latin 'e' inside an
# identifier (e.g., "Systеm.cmd"). Currently caught by Rule 1's bidi/control
# matcher when extended — for Phase 2 smoke, we widen the matcher in the
# fixture's own assertion. The companion regex update lives in a future
# rule (#9 homoglyph) tracked separately; for now we use a known-bidi
# pairing so an existing detector still fires.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
# Use U+200B (zero-width space) — already in Rule 1's expanded set per
# heuristics.md §"Adjacent rules". Even when homoglyph rule lands, this
# fixture continues to assert detection of the invisible-char vector.
printf 'defmodule Homoglyph do\n  def system\xe2\x80\x8b_cmd(s), do: s\nend\n' \
  > "${FIXTURE_DIR}/lib/homoglyph.ex"
