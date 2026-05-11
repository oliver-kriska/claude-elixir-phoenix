"""OpenCode target builder.

OpenCode reads `.opencode/skill/<name>/SKILL.md` (singular `skill/`),
`.opencode/command/<name>.md` for slash commands, and `.opencode/agent/<name>.md`
for sub-agents. Hooks are TS modules (Bun runtime) — Phase 2B generates
`server.ts`. MCP config lives in `opencode.json` (`mcp` block).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import CLAUDE_MD
from .agents import render_opencode_agent
from .frontmatter import Frontmatter, parse_file
from .hooks import render_opencode_mcp_block, render_opencode_server_ts
from .skill_transforms import (
    normalize_skill_name,
    port_references,
    rewrite_reference_paths,
    rewrite_slash_commands,
    transform_frontmatter,
)

TARGET = "opencode"


def _port_skill(src: Path, dst_root: Path) -> None:
    fm = parse_file(src)
    new_fm_data = transform_frontmatter(fm.data, TARGET)
    body = rewrite_reference_paths(fm.body, TARGET)
    body = rewrite_slash_commands(body, TARGET)

    name = normalize_skill_name(fm.data["name"])
    out_dir = dst_root / ".opencode" / "skill" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    new_fm = Frontmatter(data=new_fm_data, body=body)
    (out_dir / "SKILL.md").write_text(new_fm.dump(), encoding="utf-8")

    refs_src = src.parent / "references"
    if refs_src.is_dir():
        port_references(refs_src, out_dir / "references", TARGET)


def _generate_command(fm_data: dict, body: str, dst_root: Path) -> None:
    """Generate `.opencode/command/<name>.md` for command skills."""
    name = normalize_skill_name(fm_data["name"])
    cmd_dir = dst_root / ".opencode" / "command"
    cmd_dir.mkdir(parents=True, exist_ok=True)

    fm_out = {
        "name": name,
        "description": fm_data.get("description", ""),
    }
    new_fm = Frontmatter(data=fm_out, body=body)
    (cmd_dir / f"{name}.md").write_text(new_fm.dump(), encoding="utf-8")


def _generate_package_json(source_manifest: dict) -> dict:
    return {
        "name": f"opencode-{source_manifest['name']}",
        "version": source_manifest["version"],
        "description": source_manifest["description"],
        "keywords": source_manifest.get("keywords", []),
        "author": source_manifest.get("author", {}),
        "homepage": source_manifest.get("homepage"),
        "repository": source_manifest.get("repository"),
        "engines": {"opencode": ">=0.1.0"},
        "exports": {"./server": "./server.ts"},
        "type": "module",
    }


_SERVER_STUB = '''/**
 * OpenCode server hooks (Phase 2B will fill these in).
 *
 * Implements:
 *   - tool.execute.before — block-dangerous-ops port
 *   - tool.execute.after  — format / iron-law / debug ports
 *   - experimental.chat.system.transform — Iron Law injection
 *   - event filter — SessionStart-equivalent
 */

export const Hooks = {
  // Phase 2B: implement
};
'''

_BUNFIG = '''[install]
exact = true
'''


def _is_command_skill(fm_data: dict) -> bool:
    return ":" in (fm_data.get("name") or "")


def build(source_dir: Path, out_dir: Path) -> dict:
    source_dir = Path(source_dir)
    out_dir = Path(out_dir)

    if out_dir.exists():
        for child in out_dir.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)

    source_manifest = json.loads(
        (source_dir / ".claude-plugin" / "plugin.json").read_text()
    )

    skills_dir = source_dir / "skills"
    skill_count = 0
    command_count = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = parse_file(skill_md)
        _port_skill(skill_md, out_dir)
        skill_count += 1
        if _is_command_skill(fm.data):
            body = rewrite_slash_commands(
                rewrite_reference_paths(fm.body, TARGET), TARGET
            )
            _generate_command(fm.data, body, out_dir)
            command_count += 1

    (out_dir / "package.json").write_text(
        json.dumps(_generate_package_json(source_manifest), indent=2) + "\n",
        encoding="utf-8",
    )
    # Phase 2B: full hooks module + Tidewave MCP snippet
    render_opencode_server_ts(out_dir)
    render_opencode_mcp_block(out_dir)
    (out_dir / "bunfig.toml").write_text(_BUNFIG, encoding="utf-8")

    # Phase 2B: agents
    agents_out = out_dir / ".opencode" / "agent"
    agents_out.mkdir(parents=True, exist_ok=True)
    agent_count = 0
    for agent_md in sorted((source_dir / "agents").glob("*.md")):
        filename, content = render_opencode_agent(agent_md)
        (agents_out / filename).write_text(content, encoding="utf-8")
        agent_count += 1

    if CLAUDE_MD.exists():
        shutil.copyfile(CLAUDE_MD, out_dir / "AGENTS.md")

    return {
        "target": TARGET,
        "skills": skill_count,
        "commands": command_count,
        "agents": agent_count,
        "out_dir": str(out_dir),
    }
