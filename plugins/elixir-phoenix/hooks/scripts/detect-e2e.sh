#!/usr/bin/env bash
# Detect Wallaby or Playwright E2E test framework.
# Called during verification to determine if E2E tests are available.

[ -f "mix.exs" ] || exit 0

E2E_FRAMEWORK=""

if grep -q "wallaby" mix.exs 2>/dev/null; then
  E2E_FRAMEWORK="wallaby"

  # Check for int_test env
  if [ -f "config/int_test.exs" ]; then
    echo "E2E: Wallaby detected (MIX_ENV=int_test)"
  else
    echo "E2E: Wallaby detected (MIX_ENV=test)"
  fi
fi

if grep -q "playwright" mix.exs 2>/dev/null; then
  E2E_FRAMEWORK="playwright"
  echo "E2E: Playwright detected"
fi

if [ -z "$E2E_FRAMEWORK" ]; then
  exit 0
fi
