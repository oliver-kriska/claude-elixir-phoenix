from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from scripts.port_lib.frontmatter import parse_file

REPO = Path(__file__).resolve().parents[2]
PLUGIN = REPO / "plugins/rewrite"
PHX = REPO / "plugins/elixir-phoenix"
SKILLS = sorted(PLUGIN.glob("skills/*/SKILL.md"))
AGENTS = sorted(PLUGIN.glob("agents/*.md"))
KB = PLUGIN / "skills/elixir-way/references"


def names(directory: Path, kind: str) -> set[str]:
    if kind == "agents":
        return {p.stem for p in directory.glob("agents/*.md")}
    return {p.parent.name for p in directory.glob("skills/*/SKILL.md")}


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_dir_paths_resolve(skill: Path) -> None:
    text = skill.read_text(encoding="utf-8")
    paths = re.findall(r"\$\{CLAUDE_SKILL_DIR\}/([\w./-]+)", text)

    missing = [p for p in paths if not (skill.parent / p.rstrip(".")).exists()]

    assert missing == []


@pytest.mark.parametrize("path", SKILLS + AGENTS, ids=lambda p: f"{p.parent.name}/{p.name}")
def test_namespaced_references_exist(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    roots = {"rewrite": PLUGIN, "phx": PHX}
    missing = []
    for ns, name in re.findall(r"`(rewrite|phx):([\w-]+)`", text):
        if name not in names(roots[ns], "agents") | names(roots[ns], "skills"):
            missing.append(f"{ns}:{name}")
    for ns, name in re.findall(r"/(rewrite|phx):([\w-]+)", text):
        if name not in names(roots[ns], "skills"):
            missing.append(f"/{ns}:{name}")

    assert missing == []


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.stem)
def test_agent_kb_files_exist(agent: Path) -> None:
    text = agent.read_text(encoding="utf-8")
    refs = set(re.findall(r"KB/([\w./{}-]+\.md)", text))
    refs |= {f for group in re.findall(r"`KB` — `\.claude/rewrite/kb/` \(([^)]*)\)", text)
             for f in re.findall(r"`([\w./{}-]+\.md)`", group)}

    missing = [r for r in refs if "{" not in r and not (KB / r).exists()]

    assert missing == []


@pytest.mark.parametrize("agent", AGENTS, ids=lambda p: p.stem)
def test_agent_frontmatter_follows_plugin_rules(agent: Path) -> None:
    fm = parse_file(agent).data

    assert fm["name"] == agent.stem
    assert len(fm["description"]) <= 250
    assert "permissionMode" not in fm
    assert {"Edit", "NotebookEdit"} <= {t.strip() for t in fm["disallowedTools"].split(",")}
    assert fm["omitClaudeMd"] is True
    assert fm["skills"] == ["elixir-way"]
    assert fm["model"] in {"sonnet", "opus"}


@pytest.mark.parametrize("skill", SKILLS, ids=lambda p: p.parent.name)
def test_skill_frontmatter_follows_plugin_rules(skill: Path) -> None:
    fm = parse_file(skill).data

    assert fm["name"] == skill.parent.name
    assert len(fm["description"]) <= 250
    assert "allowed-tools" not in fm
    assert "triggers" not in fm
    assert fm["effort"] in {"low", "medium", "high"}
    assert len(skill.read_text(encoding="utf-8").splitlines()) <= 185


def test_manifest_and_marketplace_entry_agree() -> None:
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((REPO / ".claude-plugin/marketplace.json").read_text(encoding="utf-8"))
    entry = next(p for p in marketplace["plugins"] if p["name"] == "rewrite")
    phx_entry = next(p for p in marketplace["plugins"] if p["source"] == "./plugins/elixir-phoenix")

    assert entry["source"] == "./plugins/rewrite"
    assert manifest["name"] == "rewrite"
    # phx's manifest name (`phx`) differs from its marketplace name, so a
    # manifest dependency cannot resolve both on install and under --plugin-dir.
    assert "dependencies" not in manifest
    assert entry["dependencies"] == [phx_entry["name"]]


def test_ledger_vocabulary_matches_script() -> None:
    from importlib.util import module_from_spec, spec_from_file_location

    spec = spec_from_file_location("ledger", PLUGIN / "skills/architect/scripts/ledger.py")
    ledger = module_from_spec(spec)
    spec.loader.exec_module(ledger)
    skill = (PLUGIN / "skills/elixir-way/SKILL.md").read_text(encoding="utf-8")

    for verdict in ledger.VERDICTS:
        assert f"`{verdict}`" in skill
    for state in ledger.IMPL_STATES | ledger.EVIDENCE_STATES:
        assert f"`{state}`" in skill


def test_no_stale_vocabulary_in_plugin() -> None:
    stale = []
    for path in PLUGIN.rglob("*.md"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for n, line in enumerate(lines):
            # The pre-2.24 cron module may be named only next to its replacement.
            old_cron = "Oban.Plugins.Cron`" in line and "Oban.Cron`" not in " ".join(lines[max(n - 1, 0):n + 1])
            if re.search(r"\| (runtime|accident) \|", line) or old_cron:
                stale.append(f"{path.relative_to(REPO)}:{n + 1}")

    assert stale == []
