from __future__ import annotations

import json
import re
from pathlib import Path

from scripts.port_lib.frontmatter import parse_file

ROOT = Path(__file__).resolve().parents[2]
MARKETPLACE_FILE = ROOT / ".claude-plugin" / "marketplace.json"
CANONICAL_PLUGIN = ROOT / "plugins" / "elixir-phoenix"
V2_PUBLIC_COMMANDS = {
    "ecto:constraint-debug",
    "ecto:n1-check",
    "lv:assigns",
    "phx:audit",
    "phx:boundaries",
    "phx:brainstorm",
    "phx:brief",
    "phx:challenge",
    "phx:codex-loop",
    "phx:compound",
    "phx:deps-audit",
    "phx:deps-update",
    "phx:deps-vet",
    "phx:document",
    "phx:examples",
    "phx:freeze",
    "phx:full",
    "phx:help",
    "phx:init",
    "phx:intro",
    "phx:investigate",
    "phx:learn-from-fix",
    "phx:mix-compression",
    "phx:perf",
    "phx:permissions",
    "phx:plan",
    "phx:pr-review",
    "phx:quick",
    "phx:recall",
    "phx:research",
    "phx:review",
    "phx:techdebt",
    "phx:trace",
    "phx:triage",
    "phx:verify",
    "phx:watch-pr",
    "phx:work",
}
SUBAGENT_TYPE_RE = re.compile(r'subagent_type\s*:\s*["\']([^"\']+)["\']')
CLAUDE_BUILTIN_AGENT_TOOLS = {
    "Agent",
    "Bash",
    "Glob",
    "Grep",
    "Read",
    "WebFetch",
    "WebSearch",
    "Write",
}


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _effective_commands(plugin: Path) -> set[str]:
    manifest = _json(plugin / ".claude-plugin" / "plugin.json")
    namespace = manifest["name"]
    commands = set()

    for skill_file in sorted((plugin / "skills").glob("*/SKILL.md")):
        frontmatter = parse_file(skill_file).data
        if frontmatter.get("user-invocable", True):
            command_name = frontmatter.get("name", skill_file.parent.name)
            assert ":" not in command_name, skill_file
            commands.add(f"{namespace}:{command_name}")

    return commands


def test_marketplace_install_preserves_public_claude_command_names() -> None:
    marketplace = _json(MARKETPLACE_FILE)
    entries = {entry["name"]: entry for entry in marketplace["plugins"]}
    main_manifest = _json(CANONICAL_PLUGIN / ".claude-plugin" / "plugin.json")

    assert entries["elixir-phoenix"]["source"] == "./plugins/elixir-phoenix"
    assert main_manifest["name"] == "phx"
    assert set(main_manifest["dependencies"]) == {"ecto", "lv"}

    installed_plugins = [CANONICAL_PLUGIN]
    for dependency in main_manifest["dependencies"]:
        source = entries[dependency]["source"].removeprefix("./")
        plugin = ROOT / source
        dependency_manifest = _json(plugin / ".claude-plugin" / "plugin.json")
        assert dependency_manifest["version"] == main_manifest["version"]
        installed_plugins.append(plugin)

    effective = set().union(*map(_effective_commands, installed_plugins))
    assert V2_PUBLIC_COMMANDS <= effective

    canonical_commands = _effective_commands(CANONICAL_PLUGIN)
    for compatibility_plugin in installed_plugins[1:]:
        for skill_file in (compatibility_plugin / "skills").glob("*/SKILL.md"):
            body = parse_file(skill_file).body
            target = re.search(r"invoke `([^`]+)`", body)
            assert target is not None, f"missing delegation target in {skill_file}"
            assert target.group(1) in canonical_commands


def test_canonical_claude_agent_references_use_runtime_namespace() -> None:
    stale_references = []
    search_roots = (
        CANONICAL_PLUGIN,
        ROOT / ".claude" / "agents",
        ROOT / ".claude" / "skills",
    )
    for search_root in search_roots:
        for markdown in search_root.rglob("*.md"):
            if "elixir-phoenix:" in markdown.read_text(encoding="utf-8"):
                stale_references.append(markdown.relative_to(ROOT))

    assert stale_references == []


def test_concrete_custom_agent_invocations_are_qualified_and_resolve() -> None:
    available_agents = {
        agent_file.stem for agent_file in (CANONICAL_PLUGIN / "agents").glob("*.md")
    }
    unresolved = []

    for search_root in (CANONICAL_PLUGIN / "skills", CANONICAL_PLUGIN / "agents"):
        for markdown in search_root.rglob("*.md"):
            for agent_type in SUBAGENT_TYPE_RE.findall(
                markdown.read_text(encoding="utf-8")
            ):
                if agent_type == "general-purpose":
                    continue
                if not agent_type.startswith("phx:"):
                    unresolved.append((markdown.relative_to(ROOT), agent_type))
                    continue
                if agent_type.removeprefix("phx:") not in available_agents:
                    unresolved.append((markdown.relative_to(ROOT), agent_type))

    assert unresolved == []


def test_claude_agent_contract_matches_current_runtime() -> None:
    deprecated_mode_uses = []
    invalid_agents = []
    undeclared_agent_tool_uses = []

    for markdown in CANONICAL_PLUGIN.rglob("*.md"):
        text = markdown.read_text(encoding="utf-8")
        if re.search(r'\bmode\s*:\s*["\']bypassPermissions["\']', text):
            deprecated_mode_uses.append(markdown.relative_to(ROOT))

    for agent_file in sorted((CANONICAL_PLUGIN / "agents").glob("*.md")):
        frontmatter = parse_file(agent_file).data
        name = frontmatter["name"]
        tools = {
            tool.strip()
            for tool in str(frontmatter.get("tools", "")).split(",")
            if tool.strip()
        }
        if ":" in name or not tools <= CLAUDE_BUILTIN_AGENT_TOOLS:
            invalid_agents.append(
                (
                    agent_file.relative_to(ROOT),
                    name,
                    sorted(tools - CLAUDE_BUILTIN_AGENT_TOOLS),
                )
            )
        if "Agent(" in parse_file(agent_file).body and "Agent" not in tools:
            undeclared_agent_tool_uses.append(agent_file.relative_to(ROOT))

    assert deprecated_mode_uses == []
    assert invalid_agents == []
    assert undeclared_agent_tool_uses == []


def test_nested_orchestrator_workflows_have_depth_one_fallbacks() -> None:
    required_fallbacks = {
        "full": "spawn leaf research/review specialists directly",
        "investigate": "spawn the four",
        "plan": "spawn the selected specialist agents directly",
        "trace": "spawn the applicable controller",
    }

    for skill, fallback in required_fallbacks.items():
        text = (CANONICAL_PLUGIN / "skills" / skill / "SKILL.md").read_text(
            encoding="utf-8"
        )
        assert "CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH" in text
        assert fallback in text


def test_session_start_continuity_includes_forked_sessions() -> None:
    hooks = _json(CANONICAL_PLUGIN / "hooks" / "hooks.json")["hooks"]
    continuity_hook = next(
        entry
        for entry in hooks["SessionStart"]
        if any(
            hook.get("command", "").endswith("/check-resume.sh")
            for hook in entry["hooks"]
        )
    )

    assert set(continuity_hook["matcher"].split("|")) == {
        "startup",
        "resume",
        "fork",
    }
