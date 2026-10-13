"""Tests for multi-plugin support in the structural eval."""

import os
import subprocess
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from lab.eval import plugins
from lab.eval.matchers import valid_agent_refs, valid_skill_refs
from lab.eval.scorer import default_eval, find_all_skills, find_eval

PHX = plugins.plugin_dir("elixir-phoenix")
REWRITE = plugins.plugin_dir("rewrite")


def test_plugin_root_is_inferred_from_path():
    assert plugins.plugin_root_for(os.path.join(REWRITE, "skills", "analyze", "SKILL.md")) == REWRITE
    assert plugins.plugin_root_for(os.path.join(PHX, "agents", "elixir-reviewer.md")) == PHX
    assert plugins.plugin_root_for("/tmp/elsewhere/SKILL.md") == PHX


def test_namespace_map_uses_manifest_names():
    mapping = plugins.namespace_map()

    assert mapping["phx"] == PHX
    assert mapping["rewrite"] == REWRITE
    assert {"ecto", "lv"} <= set(mapping)


def test_result_keys_are_bare_for_phx_and_namespaced_otherwise():
    assert plugins.result_key(os.path.join(PHX, "skills", "plan", "SKILL.md"), "plan") == "plan"
    assert plugins.result_key(os.path.join(REWRITE, "skills", "verify", "SKILL.md"), "verify") == "rewrite:verify"


def test_find_all_skills_defaults_to_phx_only():
    default = find_all_skills()
    both = find_all_skills(plugins.STRUCTURAL_PLUGINS)

    assert all(p.startswith(PHX) for p in default)
    assert any(p.startswith(REWRITE) for p in both)
    assert len(both) > len(default)


def test_eval_lookup_never_crosses_plugins():
    rewrite_verify = os.path.join(REWRITE, "skills", "verify", "SKILL.md")

    assert find_eval("verify") is not None  # phx has evals/verify.json
    assert find_eval("verify", rewrite_verify) is None  # rewrite would need evals/rewrite-verify.json


def test_default_eval_uses_plugin_keywords():
    rewrite_eval = default_eval(os.path.join(REWRITE, "skills", "analyze", "SKILL.md"))
    phx_eval = default_eval(os.path.join(PHX, "skills", "plan", "SKILL.md"))

    def keyword_params(eval_def):
        check = next(c for c in eval_def.dimensions["triggering"].checks if c.check_type == "description_keywords")
        return check.params

    assert "rewrite" in keyword_params(rewrite_eval)["keywords"]
    assert "keywords" not in keyword_params(phx_eval)


def test_skill_refs_resolve_per_namespace():
    content = "Run /phx:plan, then /rewrite:verify and /ecto:n1-check. Load the `elixir-way` skill."

    passed, evidence = valid_skill_refs(content, plugin_root=REWRITE)

    assert passed, evidence


def test_skill_refs_report_missing_namespaced_skill():
    passed, evidence = valid_skill_refs("Run /rewrite:does-not-exist", plugin_root=REWRITE)

    assert not passed
    assert "/rewrite:does-not-exist" in evidence


def test_namespaced_agent_refs_resolve_against_their_plugin():
    content = "Spawn `rewrite:feature-cartographer` and `phx:ecto-schema-designer`, then `Skill(phx:plan)`."

    passed, evidence = valid_agent_refs(content, plugin_root=REWRITE)

    assert passed, evidence


def test_missing_namespaced_agent_is_reported():
    passed, evidence = valid_agent_refs("Spawn `rewrite:no-such-agent`.", plugin_root=REWRITE)

    assert not passed
    assert "rewrite:no-such-agent" in evidence


def test_phx_agent_refs_resolve_only_through_the_phx_root_from_rewrite():
    ok, evidence = valid_agent_refs('Task(subagent_type: "phx:ecto-schema-designer")', plugin_root=REWRITE)
    assert ok, evidence
    ok, evidence = valid_agent_refs("Spawn `phx:ecto-schema-designer`.", plugin_root=REWRITE)
    assert ok, evidence

    for content in ('Task(subagent_type: "phx:feature-cartographer")', "Spawn `phx:feature-cartographer`."):
        ok, evidence = valid_agent_refs(content, plugin_root=REWRITE)
        assert not ok
        assert "phx:feature-cartographer" in evidence


def test_rewrite_agent_refs_resolve_only_through_the_rewrite_root_from_phx():
    ok, evidence = valid_agent_refs('Task(subagent_type: "rewrite:feature-cartographer")', plugin_root=PHX)
    assert ok, evidence
    ok, evidence = valid_agent_refs("Spawn `rewrite:feature-cartographer`.", plugin_root=PHX)
    assert ok, evidence

    for content in ('Task(subagent_type: "rewrite:ecto-schema-designer")', "Spawn `rewrite:ecto-schema-designer`."):
        ok, evidence = valid_agent_refs(content, plugin_root=PHX)
        assert not ok
        assert "rewrite:ecto-schema-designer" in evidence


def test_unqualified_agent_refs_use_the_current_root():
    ok, evidence = valid_agent_refs('Task(subagent_type: "ecto-schema-designer")', plugin_root=PHX)
    assert ok, evidence
    ok, _ = valid_agent_refs('Task(subagent_type: "ecto-schema-designer")', plugin_root=REWRITE)
    assert not ok
    ok, evidence = valid_agent_refs('Task(subagent_type: "feature-cartographer")', plugin_root=REWRITE)
    assert ok, evidence


@pytest.mark.parametrize("module", ["scorer", "agent_scorer"])
@pytest.mark.parametrize(
    "plugin_args",
    [["nonexistent-plugin"], ["elixir-phoenix", "nonexistent-plugin"], ["nonexistent-plugin", "rewrite"]],
)
def test_unknown_plugin_filter_fails_nonzero(module, plugin_args):
    command = [sys.executable, "-m", f"lab.eval.{module}", "--all"]
    for name in plugin_args:
        command += ["--plugin", name]

    result = subprocess.run(command, capture_output=True, text=True, cwd=plugins.REPO_ROOT)

    assert result.returncode != 0
    assert "nonexistent-plugin" in result.stderr
    assert "elixir-phoenix" in result.stderr


def test_known_plugin_filter_still_scores_rewrite_agents():
    result = subprocess.run(
        [sys.executable, "-m", "lab.eval.agent_scorer", "--all", "--plugin", "rewrite"],
        capture_output=True, text=True, cwd=plugins.REPO_ROOT,
    )

    assert result.returncode == 0
    assert "rewrite:" in result.stdout


def test_behavioral_cache_stem_never_collides_across_plugins():
    from lab.eval.dimensions.behavioral import cache_stem

    assert cache_stem(os.path.join(PHX, "skills", "verify", "SKILL.md")) == "verify"
    assert cache_stem(os.path.join(REWRITE, "skills", "verify", "SKILL.md")) == "rewrite-verify"
