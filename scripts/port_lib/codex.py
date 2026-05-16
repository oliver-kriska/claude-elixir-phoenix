"""Codex target builder.

Codex CLI reads `.codex-plugin/plugin.json` natively. The repo-root
`.agents/plugins/marketplace.json` (Codex's native manifest, codex-only —
NOT `.claude-plugin/marketplace.json`) points Codex at this `targets/codex`
subtree via a `git-subdir` source:

    codex plugin marketplace add <owner/repo> --ref <branch|tag|sha>
    codex plugin add elixir-phoenix-codex --marketplace oliver-kriska

(`--sparse targets/codex` is an optional git checkout optimization, not a
plugin filter, and is not required.) Skill auto-loading, `$skill-name`
slash commands, and SessionStart-TOML agents are all native Codex features.

Mapping decisions (see docs/multi-agent/codex.md):
  - skills: copied + transformed (namespaces stripped, refs rewritten,
    Iron Laws inlined into auto-load skills since Codex has no SubagentStart)
  - commands: skills work as-is via `$skill-name` invocation
  - agents: TOML drop into `~/.codex/agents/` via SessionStart hook (Phase 2A)
  - hooks: 6/9 events supported; PostToolUseFailure / SubagentStart /
    StopFailure are dropped, others ported
  - mcp: stdio transport only (no SSE) → `targets/codex/.mcp.json`
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import yaml

from . import CLAUDE_MD
from .agents import render_codex_agent
from .frontmatter import Frontmatter, parse_file
from .hooks import render_codex_hooks
from .iron_laws import load_laws, render_bullets
from .skill_transforms import (
    inline_iron_laws,
    normalize_skill_name,
    port_references,
    rewrite_reference_paths,
    rewrite_slash_commands,
    transform_frontmatter,
)

TARGET = "codex"

DESCRIPTIONS_SHORT = "descriptions_short.yaml"


def _load_overrides(out_dir: Path) -> dict[str, str]:
    """Load optional `descriptions_short.yaml` overrides from out_dir."""
    path = out_dir / DESCRIPTIONS_SHORT
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {k: v for k, v in data.items() if isinstance(v, str)}

# Skills that auto-load (vs. user-invoked command skills) and therefore need
# Iron Laws inlined since Codex has no SubagentStart hook. Distinction:
# command skills have a `:` namespace in their name (`phx:plan`); reference
# skills have bare names (`testing`, `oban`, `liveview-patterns`) and
# auto-trigger on file context.
def _is_auto_load(source_name: str) -> bool:
    return ":" not in (source_name or "")


def _generate_plugin_json(source_manifest: dict) -> dict:
    """Build `.codex-plugin/plugin.json` from the source plugin manifest."""
    return {
        "name": f"{source_manifest['name']}-codex",
        "version": source_manifest["version"],
        "description": source_manifest["description"],
        "keywords": source_manifest.get("keywords", []),
        "author": source_manifest.get("author", {}),
        "homepage": source_manifest.get("homepage"),
        "repository": source_manifest.get("repository"),
        "interface": {
            "skills": "skills/",
            "commands": "skills/",
            "agents": "agents-toml/",
            "hooks": "hooks/hooks.json",
            "mcp": ".mcp.json",
        },
    }


def _port_skill(
    src: Path, dst_root: Path, laws_bullets: list[str], overrides: dict[str, str]
) -> int:
    fm = parse_file(src)
    new_fm_data = transform_frontmatter(fm.data, TARGET)

    name = normalize_skill_name(fm.data["name"])
    if name in overrides:
        new_fm_data["description"] = overrides[name]

    body = rewrite_reference_paths(fm.body, TARGET)
    body = rewrite_slash_commands(body, TARGET)
    if _is_auto_load(fm.data.get("name", "")):
        body = inline_iron_laws(body, laws_bullets, TARGET)

    out_dir = dst_root / "skills" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    new_fm = Frontmatter(data=new_fm_data, body=body)
    (out_dir / "SKILL.md").write_text(new_fm.dump(), encoding="utf-8")

    # Port references/ — markdown files go through the same transforms
    # as the SKILL.md body (refs paths + slash commands), non-md verbatim.
    refs_src = src.parent / "references"
    if refs_src.is_dir():
        port_references(refs_src, out_dir / "references", TARGET)

    return len((new_fm_data.get("description") or "").encode("utf-8"))


def _generate_mcp_config() -> dict:
    """Tidewave MCP via stdio (Codex doesn't support SSE)."""
    return {
        "mcpServers": {
            "tidewave": {
                "command": "npx",
                "args": ["-y", "@tidewave/mcp"],
                "env": {},
            }
        }
    }


def build(source_dir: Path, out_dir: Path) -> dict:
    """Generate `targets/codex/` from `plugins/elixir-phoenix/`."""
    source_dir = Path(source_dir)
    out_dir = Path(out_dir)

    # Reset output (preserve .gitkeep + descriptions_short.yaml).
    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.name in (".gitkeep", DESCRIPTIONS_SHORT):
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    overrides = _load_overrides(out_dir)

    # Read source plugin.json
    source_manifest = json.loads(
        (source_dir / ".claude-plugin" / "plugin.json").read_text()
    )

    # Generate `.codex-plugin/plugin.json`
    plugin_dir = out_dir / ".codex-plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_json = _generate_plugin_json(source_manifest)
    (plugin_dir / "plugin.json").write_text(
        json.dumps(plugin_json, indent=2) + "\n", encoding="utf-8"
    )

    # Iron Laws bullets for inlining
    laws_bullets = render_bullets(load_laws())

    # Port all skills
    skills_dir = source_dir / "skills"
    skill_count = 0
    desc_total = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        desc_total += _port_skill(skill_md, out_dir, laws_bullets, overrides)
        skill_count += 1

    # Generate MCP config
    (out_dir / ".mcp.json").write_text(
        json.dumps(_generate_mcp_config(), indent=2) + "\n", encoding="utf-8"
    )

    # CLAUDE.md / AGENTS.md companion files (informational; Codex reads AGENTS.md)
    if CLAUDE_MD.exists():
        shutil.copyfile(CLAUDE_MD, out_dir / "CLAUDE.md")
        shutil.copyfile(CLAUDE_MD, out_dir / "AGENTS.md")

    # ---- Phase 2A: agents (TOML) and hooks ----
    agents_src = source_dir / "agents"
    agents_out = out_dir / "agents-toml"
    agents_out.mkdir(parents=True, exist_ok=True)
    agent_count = 0
    for agent_md in sorted(agents_src.glob("*.md")):
        filename, content = render_codex_agent(agent_md)
        (agents_out / filename).write_text(content, encoding="utf-8")
        agent_count += 1

    hooks_src_dir = source_dir / "hooks" / "scripts"
    hooks_src_json = source_dir / "hooks" / "hooks.json"
    hook_info = render_codex_hooks(hooks_src_dir, hooks_src_json, out_dir)

    return {
        "target": TARGET,
        "skills": skill_count,
        "agents": agent_count,
        "hook_scripts": hook_info["scripts_copied"],
        "hook_events_kept": hook_info["events_kept"],
        "hook_events_dropped": hook_info["events_dropped"],
        "description_bytes": desc_total,
        "out_dir": str(out_dir),
    }
