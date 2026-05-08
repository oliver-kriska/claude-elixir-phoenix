#!/usr/bin/env bash
# SessionStart hook: Create core workflow directories (other dirs created by skills on demand)
mkdir -p .claude/plans .claude/reviews .claude/solutions .claude/audit .claude/skill-metrics .claude/research 2>/dev/null || true

# Create persistent plugin data directory (survives plugin updates)
# ${CLAUDE_PLUGIN_DATA} is provided by Claude Code v2.1.78+
if [ -n "${CLAUDE_PLUGIN_DATA}" ]; then
  mkdir -p "${CLAUDE_PLUGIN_DATA}/skill-metrics" 2>/dev/null || true
fi
