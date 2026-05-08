"""Source-to-target transforms applied to each SKILL.md when porting.

Targets:
    codex    — `.codex-plugin/`, namespace stripped to `phx-`/`lv-`/`ecto-`
    pi       — `targets/pi/skills/<normalized>/SKILL.md`, agentskills.io spec
    opencode — `targets/opencode/.opencode/skill/<normalized>/SKILL.md`
"""

from __future__ import annotations

import re
from typing import Iterable

# Frontmatter fields recognized by the agentskills.io spec (portable across
# all non-Claude targets). Anything else is Claude-specific and gets shunted
# into a `metadata:` sub-block on non-Claude targets.
AGENTSKILLS_FIELDS = {"name", "description", "license"}

# Fields that are valid on Claude but must be moved to `metadata:` for
# strict agentskills.io targets.
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
    """`phx:plan` → `phx-plan`, `lv:assigns` → `lv-assigns`.

    Plain names (no namespace) pass through unchanged. Used for filesystem
    directories on Codex/Pi/OpenCode where `:` is awkward in paths and
    slash-command invocations differ per agent.
    """
    if not name:
        return name
    return name.replace(":", "-")


def transform_frontmatter(data: dict, target: str) -> dict:
    """Reshape frontmatter for a given target.

    - claude   : pass-through (the source format).
    - codex    : keep agentskills.io fields at top level, fold Claude
                 extensions into `metadata:`. Normalize name (strip `:`).
    - pi       : same shape as codex.
    - opencode : same shape, but `name` keeps the dash form too.
    """
    if target == "claude":
        return dict(data)

    if target not in ("codex", "pi", "opencode"):
        raise ValueError(f"Unknown target: {target}")

    out: dict = {}
    metadata: dict = {}

    for key, value in data.items():
        if key == "name":
            out["name"] = normalize_skill_name(value)
        elif key in AGENTSKILLS_FIELDS:
            out[key] = value
        elif key in CLAUDE_EXTENSION_FIELDS:
            metadata[key] = value
        else:
            # Unknown field — preserve in metadata to avoid silent loss.
            metadata[key] = value

    if metadata:
        out["metadata"] = metadata
    return out


# Matches `${CLAUDE_SKILL_DIR}/references/foo.md` and bare `references/foo.md`
_CLAUDE_REF_RE = re.compile(r"\$\{CLAUDE_SKILL_DIR\}/references/([\w./-]+)")

# Matches `/phx:foo`, `/lv:foo`, `/ecto:foo`. Captures namespace and name.
_SLASH_CMD_RE = re.compile(r"/(phx|lv|ecto):([a-z][a-z0-9-]*)")


def rewrite_reference_paths(body: str, target: str) -> str:
    """Rewrite `${CLAUDE_SKILL_DIR}/references/X.md` for the given target.

    All targets currently use a relative `references/X.md` path inside the
    skill directory — that's the agentskills.io convention. Codex, Pi, and
    OpenCode all expand this relative to the skill's own directory.
    """
    if target == "claude":
        return body
    return _CLAUDE_REF_RE.sub(r"references/\1", body)


def rewrite_slash_commands(body: str, target: str) -> str:
    """Rewrite `/phx:foo` references for the given target's invocation style.

    - claude   : pass-through (`/phx:foo` is the native form).
    - codex    : `/phx:foo` → `$phx-foo` (Codex slash-command convention).
    - opencode : `/phx:foo` → `/phx-foo` (`:` not allowed in command names).
    - pi       : `/phx:foo` → `/phx-foo` (Pi prompt names).
    """
    if target == "claude":
        return body
    if target == "codex":
        return _SLASH_CMD_RE.sub(r"$\1-\2", body)
    return _SLASH_CMD_RE.sub(r"/\1-\2", body)


_IRON_LAW_HEADER = "## Iron Laws (Inlined)"


def inline_iron_laws(body: str, laws: Iterable[str], target: str) -> str:
    """Append an inlined Iron Laws section to a skill body.

    Used for targets that don't have a `SubagentStart`-equivalent hook
    (Codex notably). The block is idempotent: re-running the transform
    replaces an existing inlined block instead of appending a second copy.
    """
    if target == "claude":
        return body

    laws_list = list(laws)
    if not laws_list:
        return body

    bullets = "\n".join(f"- {law}" for law in laws_list)
    block = f"\n\n{_IRON_LAW_HEADER}\n\n{bullets}\n"

    # Idempotent: strip any previous inlined block before appending.
    pattern = re.compile(
        rf"\n*{re.escape(_IRON_LAW_HEADER)}\n.*?(?=\n## |\Z)", re.DOTALL
    )
    cleaned = pattern.sub("", body).rstrip()
    return cleaned + block
