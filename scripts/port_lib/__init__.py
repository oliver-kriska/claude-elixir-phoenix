"""Shared paths and pure transforms for generated plugin targets."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT: Path = Path(__file__).resolve().parents[2]
SOURCE_PLUGIN_DIR: Path = REPO_ROOT / "plugins" / "elixir-phoenix"
TARGETS_DIR: Path = REPO_ROOT / "targets"
