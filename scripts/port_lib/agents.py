"""Per-target agent rendering.

Sources from `plugins/elixir-phoenix/agents/<name>.md` (Claude format).
Targets:
    codex    — TOML files in `targets/codex/agents-toml/<name>.toml`
    opencode — markdown files in `targets/opencode/.opencode/agent/<name>.md`
    pi       — prompt templates dispatched by Phase 2C extension

Claude-only frontmatter fields (memory, omitClaudeMd, allowed-tools, etc.)
are dropped or remapped per target.
"""

from __future__ import annotations

from pathlib import Path

from .frontmatter import parse_file


# ---- TOML emit (Codex) -------------------------------------------------


def _toml_escape_string(value: str) -> str:
    """Escape a string for inclusion as a TOML basic string literal."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _toml_render_kv(key: str, value) -> str:
    if isinstance(value, str):
        if "\n" in value:
            # Use TOML multi-line literal string for long developer_instructions.
            return f"{key} = '''\n{value}\n'''"
        return f'{key} = "{_toml_escape_string(value)}"'
    if isinstance(value, bool):
        return f"{key} = {'true' if value else 'false'}"
    if isinstance(value, (int, float)):
        return f"{key} = {value}"
    if isinstance(value, list):
        rendered = ", ".join(f'"{_toml_escape_string(str(v))}"' for v in value)
        return f"{key} = [{rendered}]"
    raise TypeError(f"Cannot render TOML for {key}: {type(value).__name__}")


def _agent_to_codex_toml(fm_data: dict, body: str) -> str:
    """Render an agent as a Codex `~/.codex/agents/<name>.toml` file.

    Spec (Phase 2A target): a top-level table with these keys:
        name, description, model, developer_instructions
    Claude-specific fields drop or remap:
        - tools / disallowedTools / permissionMode → not represented
        - skills → joined into developer_instructions header
        - effort → drop
        - maxTurns → drop
    """
    lines: list[str] = []

    name = fm_data.get("name", "unknown")
    description = fm_data.get("description", "")
    model = fm_data.get("model", "sonnet")

    lines.append(_toml_render_kv("name", name))
    lines.append(_toml_render_kv("description", description))
    lines.append(_toml_render_kv("model", model))

    skills = fm_data.get("skills") or []
    skill_header = ""
    if skills:
        joined = ", ".join(skills)
        skill_header = f"# Preloaded skills (from Claude source): {joined}\n\n"

    instructions = (skill_header + body).strip()
    lines.append(_toml_render_kv("developer_instructions", instructions))

    return "\n".join(lines) + "\n"


# ---- OpenCode markdown (Phase 2B) -------------------------------------


def _agent_to_opencode_md(fm_data: dict, body: str) -> str:
    """Render an agent as `.opencode/agent/<name>.md`.

    OpenCode reads the same agent shape as Claude with a couple of renames:
      - `disallowedTools` → not supported (omitted; tools list whitelist instead)
      - `permissionMode` → not supported
      - `mode: subagent` is the OpenCode default for orchestrator-spawned agents

    We keep the source body (which already references skills via `skills:`).
    """
    import yaml as _yaml

    out = {
        "name": fm_data.get("name"),
        "description": fm_data.get("description", ""),
        "model": fm_data.get("model", "sonnet"),
        "mode": "subagent",
    }
    skills = fm_data.get("skills") or []
    if skills:
        out["skills"] = skills

    head = _yaml.safe_dump(out, sort_keys=False, allow_unicode=True).rstrip()
    return f"---\n{head}\n---\n{body}"


def render_codex_agent(source_md: Path) -> tuple[str, str]:
    """Return `(toml_filename, toml_content)` for an agent source file."""
    fm = parse_file(source_md)
    name = fm.data.get("name") or source_md.stem
    return f"{name}.toml", _agent_to_codex_toml(fm.data, fm.body)


def render_opencode_agent(source_md: Path) -> tuple[str, str]:
    """Return `(md_filename, md_content)` for an agent source file."""
    fm = parse_file(source_md)
    name = fm.data.get("name") or source_md.stem
    return f"{name}.md", _agent_to_opencode_md(fm.data, fm.body)
