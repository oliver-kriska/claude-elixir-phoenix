#!/usr/bin/env bash
# SessionStart hook: copy bundled sub-agent TOMLs into ~/.codex/agents/.
set -eu
TARGET_DIR="${HOME}/.codex/agents"
PLUGIN_ROOT="${CODEX_PLUGIN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
SOURCE_DIR="${PLUGIN_ROOT}/agents-toml"
[ -d "$SOURCE_DIR" ] || exit 0
mkdir -p "$TARGET_DIR"
cp -f "$SOURCE_DIR"/*.toml "$TARGET_DIR/" 2>/dev/null || true
echo "[install-codex-agents] copied $(ls "$SOURCE_DIR"/*.toml 2>/dev/null | wc -l) agents"
