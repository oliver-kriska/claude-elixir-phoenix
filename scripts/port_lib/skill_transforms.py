"""Shared source-to-target transforms for Agent Skills."""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Iterable

AGENTSKILLS_FIELDS = {"name", "description", "license", "compatibility", "metadata"}
CANONICAL_PORTABLE_NAMES = {
    "assigns-audit": "lv-assigns",
    "audit": "phx-audit",
    "boundaries": "phx-boundaries",
    "brainstorm": "phx-brainstorm",
    "brief": "phx-brief",
    "challenge": "phx-challenge",
    "codex-loop": "phx-codex-loop",
    "compound": "phx-compound",
    "deps-audit": "phx-deps-audit",
    "deps-update": "phx-deps-update",
    "deps-vet": "phx-deps-vet",
    "document": "phx-document",
    "ecto-constraint-debug": "ecto-constraint-debug",
    "examples": "phx-examples",
    "freeze": "phx-freeze",
    "full": "phx-full",
    "help": "phx-help",
    "init": "phx-init",
    "intro": "phx-intro",
    "investigate": "phx-investigate",
    "learn-from-fix": "phx-learn-from-fix",
    "mix-compression": "phx-mix-compression",
    "n1-check": "ecto-n1-check",
    "perf": "phx-perf",
    "permissions": "phx-permissions",
    "plan": "phx-plan",
    "pr-review": "phx-pr-review",
    "quick": "phx-quick",
    "recall": "phx-recall",
    "research": "phx-research",
    "review": "phx-review",
    "techdebt": "phx-techdebt",
    "trace": "phx-trace",
    "triage": "phx-triage",
    "verify": "phx-verify",
    "watch-pr": "phx-watch-pr",
    "work": "phx-work",
}


def portable_skill_name(directory_name: str, command_name: str) -> str:
    """Return the stable generated-runtime name for a canonical Claude skill."""
    return CANONICAL_PORTABLE_NAMES.get(
        directory_name,
        normalize_skill_name(command_name),
    )


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

    for key, value in data.items():
        if key == "name":
            output["name"] = normalize_skill_name(value)
        elif key in AGENTSKILLS_FIELDS:
            output[key] = value

    metadata = output.get("metadata")
    if metadata is not None and (
        not isinstance(metadata, dict)
        or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in metadata.items()
        )
    ):
        raise ValueError("Agent Skills metadata must be a string-to-string mapping")

    if isinstance(output.get("description"), str):
        output["description"] = rewrite_slash_commands(
            output["description"],
            target,
        )

    return output


_CLAUDE_REF_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/references/([\w./-]+)")
_SLASH_CMD_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])/(phx|lv|ecto):"
    r"([a-z][a-z0-9-]*)(?![A-Za-z0-9_:-])"
)
_SLASH_NAMESPACE_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])/(phx|lv|ecto):"
    r"(?:\*(?![A-Za-z0-9_:-])|(?![A-Za-z0-9_*:-]))"
)


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
            shutil.copy2(src, output)


def rewrite_slash_commands(body: str, target: str) -> str:
    """Rewrite Claude namespaced command references for a target."""
    if target == "claude":
        return body
    if target == "amp":
        body = _SLASH_CMD_RE.sub(r"\1-\2", body)
        return _SLASH_NAMESPACE_RE.sub(r"\1-*", body)
    if target == "codex":
        body = _SLASH_CMD_RE.sub(r"$\1-\2", body)
        return _SLASH_NAMESPACE_RE.sub(r"$\1-*", body)
    if target == "pi":
        body = _SLASH_CMD_RE.sub(r"/skill:\1-\2", body)
        return _SLASH_NAMESPACE_RE.sub(r"/skill:\1-*", body)
    if target == "opencode":
        body = _SLASH_CMD_RE.sub(r"/\1-\2", body)
        return _SLASH_NAMESPACE_RE.sub(r"/\1-*", body)
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
