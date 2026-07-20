#!/usr/bin/env bash
# 01_bidi — Trojan Source (CVE-2021-42574). U+202E (RIGHT-TO-LEFT OVERRIDE)
# inserted via printf so the file actually contains the control character.
set -u
mkdir -p "${FIXTURE_DIR}/lib"
printf 'defmodule Bidi do\n  def check(s), do: s == "admin\xe2\x80\xae unsafe"\nend\n' \
  > "${FIXTURE_DIR}/lib/bidi.ex"
