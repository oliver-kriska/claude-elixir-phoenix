"""Pure source-to-target transforms for Agent Skills."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

AGENTSKILLS_FIELDS = {"name", "description", "license"}

CLAUDE_EXTENSION_FIELDS = {
    "effort",
    "allowed-tools",
    "disallowed-tools",
    "model",
    "memory",
    "skills",
    "permissionMode",
    "omitClaudeMd",
}


def normalize_skill_name(name: str) -> str:
    """Normalize namespaced skill names for targets that disallow colons."""
    if not name:
        return name
    return name.replace(":", "-")


def transform_frontmatter(data: dict, target: str) -> dict:
    """Preserve Claude frontmatter or project it to Agent Skills fields."""
    if target == "claude":
        return dict(data)

    if target not in ("amp", "codex", "pi", "opencode"):
        raise ValueError(f"Unknown target: {target}")

    output: dict = {}
    metadata: dict = {}

    for key, value in data.items():
        if key == "name":
            output["name"] = normalize_skill_name(value)
        elif key in AGENTSKILLS_FIELDS:
            output[key] = value
        else:
            metadata[key] = value

    if isinstance(output.get("description"), str):
        output["description"] = rewrite_slash_commands(
            output["description"],
            target,
        )

    # Amp supports Agent Skills frontmatter directly. Keep its projection
    # deliberately conservative rather than leaking Claude-only extensions.
    if metadata and target != "amp":
        output["metadata"] = metadata
    return output


_CLAUDE_REF_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/references/([\w./-]+)")
_SLASH_CMD_RE = re.compile(r"/(phx|lv|ecto):([a-z][a-z0-9-]*)")
_SLASH_NAMESPACE_RE = re.compile(r"/(phx|lv|ecto):\*?")


def rewrite_reference_paths(body: str, target: str) -> str:
    """Rewrite Claude skill reference paths to skill-relative paths."""
    if target == "claude":
        return body
    return _CLAUDE_REF_RE.sub(r"references/\1", body)


def port_references(
    refs_src: str | Path,
    refs_dst: str | Path,
    target: str,
) -> None:
    """Copy references, transforming Markdown and preserving other files."""
    source = Path(refs_src)
    destination = Path(refs_dst)

    if destination.exists():
        shutil.rmtree(destination)
    destination.mkdir(parents=True)

    for src in source.rglob("*"):
        if src.is_dir():
            continue

        output = destination / src.relative_to(source)
        output.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix == ".md":
            text = src.read_text(encoding="utf-8")
            text = rewrite_reference_paths(text, target)
            text = rewrite_slash_commands(text, target)
            output.write_text(text, encoding="utf-8")
        else:
            output.write_bytes(src.read_bytes())


def rewrite_slash_commands(body: str, target: str) -> str:
    """Rewrite Claude namespaced command references for a target."""
    if target == "claude":
        return body
    if target in ("amp", "codex"):
        body = _SLASH_CMD_RE.sub(r"\1-\2", body)
        return _SLASH_NAMESPACE_RE.sub(r"\1-*", body)
    if target in ("pi", "opencode"):
        return _SLASH_CMD_RE.sub(r"/\1-\2", body)
    raise ValueError(f"Unknown target: {target}")


_IRON_LAW_HEADER = "## Iron Laws (Inlined)"


def inline_iron_laws(body: str, laws: Iterable[str], target: str) -> str:
    """Append or replace an inlined Iron Laws section."""
    if target == "claude":
        return body

    laws_list = list(laws)
    if not laws_list:
        return body

    bullets = "\n".join(f"- {law}" for law in laws_list)
    block = f"\n\n{_IRON_LAW_HEADER}\n\n{bullets}\n"
    pattern = re.compile(
        rf"\n*{re.escape(_IRON_LAW_HEADER)}\n.*?(?=\n## |\Z)",
        re.DOTALL,
    )
    cleaned = pattern.sub("", body).rstrip()
    return cleaned + block
