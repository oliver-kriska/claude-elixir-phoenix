"""Port library: per-target transforms for the multi-agent plugin pipeline.

Builds `targets/<agent>/` from `plugins/elixir-phoenix/` by applying
target-specific transforms (frontmatter shape, reference paths, namespace
normalization, Iron Law inlining).
"""

from __future__ import annotations

from pathlib import Path

# Single source of truth for the repo root. Resolved at import time, used
# by every module in this package and by `scripts/port.py` /
# `scripts/inject_claude_md.py`. Previously each module computed its own
# variant of `Path(__file__).resolve().parent.parent` (or `parents[2]`)
# — a footgun if `scripts/` ever gains a sub-package.
REPO_ROOT: Path = Path(__file__).resolve().parents[2]

SOURCE_PLUGIN_DIR: Path = REPO_ROOT / "plugins" / "elixir-phoenix"
TARGETS_DIR: Path = REPO_ROOT / "targets"
LAWS_YAML: Path = REPO_ROOT / "iron-laws" / "laws.yaml"
CLAUDE_MD: Path = REPO_ROOT / "CLAUDE.md"
