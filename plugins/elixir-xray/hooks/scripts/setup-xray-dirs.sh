#!/usr/bin/env bash
# Create Inspector output directories and check prerequisites

mkdir -p .claude/xray/layers/sessions
mkdir -p .claude/xray/layers/{L1,L2,L3,L4,L5,L6}
mkdir -p .claude/xray/generated/credo-checks
mkdir -p .claude/xray/generated/skills
mkdir -p .claude/xray/generated/ci-scripts
mkdir -p .claude/xray/generated/review-prompts

# Check prerequisites (informational only)
PREREQS=""
if command -v gh >/dev/null 2>&1; then
  PREREQS="gh:OK"
else
  PREREQS="gh:missing(Layer 2 PR analysis unavailable)"
fi

echo "Elixir X-Ray plugin loaded"
