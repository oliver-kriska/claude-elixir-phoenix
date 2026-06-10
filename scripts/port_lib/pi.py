"""Pi target builder.

Pi is agentskills.io-native — `targets/pi/skills/<name>/SKILL.md` is read
directly. Slash commands need `targets/pi/prompts/<name>.md` Pi prompt
templates. CLAUDE.md is aliased as AGENTS.md (Pi convention).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import CLAUDE_MD
from .frontmatter import Frontmatter, parse_file
from .hooks import render_pi_extensions
from .skill_transforms import (
    normalize_skill_name,
    port_references,
    rewrite_reference_paths,
    rewrite_slash_commands,
    transform_frontmatter,
)

TARGET = "pi"


def _port_skill(src: Path, dst_root: Path) -> None:
    fm = parse_file(src)
    new_fm_data = transform_frontmatter(fm.data, TARGET)
    body = rewrite_reference_paths(fm.body, TARGET)
    body = rewrite_slash_commands(body, TARGET)

    name = normalize_skill_name(fm.data["name"])
    out_dir = dst_root / "skills" / name
    out_dir.mkdir(parents=True, exist_ok=True)

    new_fm = Frontmatter(data=new_fm_data, body=body)
    (out_dir / "SKILL.md").write_text(new_fm.dump(), encoding="utf-8")

    refs_src = src.parent / "references"
    if refs_src.is_dir():
        port_references(refs_src, out_dir / "references", TARGET)


def _is_command_skill(fm_data: dict) -> bool:
    """Skills whose name contains `:` map to user-invokable slash commands."""
    name = fm_data.get("name") or ""
    return ":" in name


def _generate_prompt(fm_data: dict, body: str, dst_root: Path) -> None:
    """Convert a command skill body into a Pi prompt template (`prompts/<name>.md`)."""
    name = normalize_skill_name(fm_data["name"])
    prompts_dir = dst_root / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)

    # Pi prompts use `$1`/`$@` for argument interpolation. The body of a
    # command skill is already a procedural template; we just prepend
    # frontmatter indicating the prompt's expected args. Use Frontmatter.dump
    # (yaml.safe_dump) rather than an f-string so descriptions containing `: `
    # (e.g. "/phx:" or "domains:") are quoted and stay valid YAML.
    fm = Frontmatter(
        data={
            "name": name,
            "description": fm_data.get("description", ""),
            "args": "$@",
        },
        body="\n" + body.lstrip(),
    )
    (prompts_dir / f"{name}.md").write_text(fm.dump(), encoding="utf-8")


def _generate_package_json(source_manifest: dict) -> dict:
    return {
        "name": f"pi-{source_manifest['name']}",
        "version": source_manifest["version"],
        "description": source_manifest["description"],
        "keywords": source_manifest.get("keywords", []) + ["pi-package"],
        "author": source_manifest.get("author", {}),
        "homepage": source_manifest.get("homepage"),
        "repository": source_manifest.get("repository"),
        # Pi >=0.75.0 requires Node >=22.19.0 (the legacy-node20 dist-tag
        # stays pinned at 0.74.2). Declared so npm/bun warn early.
        "engines": {"pi": ">=0.1.0", "node": ">=22.19.0"},
        "devDependencies": {
            # Type-only import in extensions/*.ts. The Pi runtime supplies
            # the API at load time; this pins the typings to the API the
            # extensions were verified against (0.79.1 type declarations —
            # toolName/input event shape, {block, reason} tool_call result,
            # pi.sendUserMessage). See docs/multi-agent/pi.md.
            "@earendil-works/pi-coding-agent": ">=0.79.1",
        },
        "pi": {
            "skills": "skills/",
            "prompts": "prompts/",
            "extensions": ["./extensions/iron-laws.ts", "./extensions/orchestration.ts"],
        },
    }


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
    prompt_count = 0
    for skill_md in sorted(skills_dir.glob("*/SKILL.md")):
        fm = parse_file(skill_md)
        _port_skill(skill_md, out_dir)
        skill_count += 1
        if _is_command_skill(fm.data):
            body = rewrite_slash_commands(
                rewrite_reference_paths(fm.body, TARGET), TARGET
            )
            _generate_prompt(fm.data, body, out_dir)
            prompt_count += 1

    (out_dir / "package.json").write_text(
        json.dumps(_generate_package_json(source_manifest), indent=2) + "\n",
        encoding="utf-8",
    )

    # Phase 2C: extensions (iron-laws.ts + orchestration.ts)
    ext_info = render_pi_extensions(out_dir)

    if CLAUDE_MD.exists():
        shutil.copyfile(CLAUDE_MD, out_dir / "CLAUDE.md")
        shutil.copyfile(CLAUDE_MD, out_dir / "AGENTS.md")

    # README placeholder (Phase 1B will overwrite with full docs).
    readme = out_dir / "README.md"
    if not readme.exists():
        readme.write_text(
            f"# pi-{source_manifest['name']}\n\n"
            f"{source_manifest['description']}\n\n"
            f"## Install\n\n"
            f"```bash\n"
            f"# From a local checkout of this generated tree:\n"
            f"pi install ./targets/pi      # add -l for project-local scope\n"
            f"```\n\n"
            f"See `docs/multi-agent/pi.md` in the source repo for the mirror\n"
            f"install path and tradeoffs.\n",
            encoding="utf-8",
        )

    return {
        "target": TARGET,
        "skills": skill_count,
        "prompts": prompt_count,
        "extensions": ext_info["extensions"],
        "out_dir": str(out_dir),
    }
