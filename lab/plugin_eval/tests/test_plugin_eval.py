"""Tests for the `claude plugin eval` trigger-suite generator and analyzer."""

import json
import os
import re

from lab.plugin_eval import analyze, generate


def test_skill_matcher_requires_phx_namespace():
    pattern = re.compile(generate.skill_matcher("verify"))
    assert pattern.search('{"skill": "phx:verify"}')
    # CC ships a built-in `verify` skill; a bare match would count it as a hit.
    assert not pattern.search('{"skill":"verify"}')
    assert not pattern.search('{"skill":"phx:verify-extra"}')


def test_generated_case_loads_dependency_plugins_from_repo_root(tmp_path, monkeypatch):
    out = tmp_path / "cases" / "triggers"
    monkeypatch.setattr(generate, "OUT_DIR", str(out))
    monkeypatch.setattr(generate, "load_triggers", lambda only: {
        "verify": {"should_trigger": ["verify it"], "should_not_trigger": ["review it"]},
    })

    pos, neg = generate.generate(None, max_turns=3, timeout=180)

    assert (pos, neg) == (1, 1)
    case = out / "verify" / "pos-1"
    case_yaml = (case / "case.yaml").read_text()
    for plugin in generate.PLUGIN_DIRS:
        rel = os.path.relpath(os.path.join(generate.PROJECT_ROOT, plugin), case)
        assert json.dumps(rel) in case_yaml
    assert "scaffold_script: fixture.sh" in case_yaml
    assert (case / "fixture.sh").is_file()

    prompt = (case / "prompt.md").read_text()
    assert "max_turns: 3" in prompt
    assert "allowed_tools: [Read, Glob, Grep, Skill]" in prompt
    assert prompt.rstrip().endswith("verify it")

    negative = (out / "verify" / "neg-1" / "graders" / "skill.md").read_text()
    assert "max: 0" in negative and "arm: both" in negative


def test_every_trigger_file_maps_to_a_shipped_skill():
    triggers = generate.load_triggers(None)
    assert triggers, "no trigger files found"
    for skill in triggers:
        assert os.path.isfile(os.path.join(generate.SKILLS_DIR, skill, "SKILL.md"))


def _write_trace(path, *, plugin_errors=None, skills=(), hook=None):
    events = [{"type": "system", "subtype": "init", "plugin_errors": plugin_errors or []}]
    if hook:
        events.append({"type": "system", "subtype": "hook_response", **hook})
    for skill in skills:
        events.append({"type": "assistant", "message": {"content": [
            {"type": "tool_use", "name": "Skill", "input": {"skill": skill}},
        ]}})
    path.write_text("\n".join(json.dumps(e) for e in events) + "\n")


def _case(name, skill, trace, *, negative=False, error=None):
    config = {"tool": "Skill", "input_match": generate.skill_matcher(skill)}
    if negative:
        config.update({"min": 0, "max": 0, "arm": "both"})
    return {
        "name": name,
        "graders": [{"name": "skill", "type": "tool_used", "weight": 1, "config": config}],
        "arms": {"with": [{"tracePath": str(trace), "error": error, "costUsd": 0.1}]},
    }


def test_summary_counts_recall_negatives_stray_and_builtin(tmp_path):
    hit, miss, neg = tmp_path / "hit.jsonl", tmp_path / "miss.jsonl", tmp_path / "neg.jsonl"
    _write_trace(hit, skills=["phx:verify"])
    _write_trace(miss, skills=["phx:review", "verify"])
    _write_trace(neg, skills=["phx:n1-check"])
    data = {"cases": [
        _case("verify--pos-1", "verify", hit),
        _case("verify--pos-2", "verify", miss),
        _case("verify--neg-1", "verify", neg, negative=True),
    ]}

    summary = analyze.summarize(data, str(tmp_path))

    stats = summary["per_skill"]["verify"]
    assert (stats["pos_hit"], stats["pos"], stats["neg_clean"], stats["neg"]) == (1, 2, 1, 1)
    assert stats["misroutes"] == {"review,builtin:verify": 1}
    # review fired on a verify prompt; n1-check on a negative prompt is not stray.
    assert summary["stray"] == {"review": ["verify--pos-2"]}
    assert summary["builtin"] == {"verify": 1}


def test_plugin_load_errors_and_non_turn_cap_errors_are_flagged(tmp_path):
    trace = tmp_path / "t.jsonl"
    _write_trace(trace, plugin_errors=[{"type": "dependency-unsatisfied"}],
                 hook={"hook_name": "SessionStart:startup", "exit_code": 1, "outcome": "error", "stderr": "boom"})
    data = {"cases": [
        _case("a--pos-1", "verify", trace, error="exit 1: Reached maximum number of turns (3)"),
        _case("b--pos-1", "verify", trace, error="API Error: 429 rate limited"),
    ]}

    summary = analyze.summarize(data, str(tmp_path))

    assert len(summary["load_errors"]) == 2
    assert [name for name, _ in summary["run_errors"]] == ["b--pos-1"]
    assert "SessionStart:startup: exit=1 boom" in summary["hook_errors"][0][1][0]


def test_archived_traces_survive_sandbox_deletion(tmp_path):
    sandbox_trace = tmp_path / "sandbox" / "trace.jsonl"
    sandbox_trace.parent.mkdir()
    _write_trace(sandbox_trace, skills=["phx:verify"])
    results = tmp_path / "results"
    results.mkdir()
    data = {"cases": [_case("verify--pos-1", "verify", sandbox_trace)]}

    assert analyze.archive_traces(str(results), data) == 1
    sandbox_trace.unlink()

    summary = analyze.summarize(data, str(results))
    assert summary["unreadable"] == 0
    assert summary["per_skill"]["verify"]["pos_hit"] == 1


def test_trace_parser_tolerates_string_messages_and_blocks(tmp_path):
    trace = tmp_path / "t.jsonl"
    trace.write_text("\n".join(json.dumps(e) for e in [
        {"type": "result", "message": "Reached maximum number of turns"},
        {"type": "assistant", "message": {"content": ["plain", {"type": "tool_use", "name": "Skill", "input": {"skill": "phx:plan"}}]}},
        "not-an-object-line",
    ]) + "\n")

    info = analyze.parse_trace(str(trace))

    assert info["skills_invoked"] == ["phx:plan"]


def test_cleanup_only_removes_eval_sandbox_roots(tmp_path):
    sandbox = tmp_path / "e-AbC123"
    sealed = sandbox / "sealed"
    (sandbox / "out").mkdir(parents=True)
    sealed.mkdir()
    (sandbox / "out" / "trace.jsonl").write_text("{}\n")
    sealed.chmod(0)
    other = tmp_path / "not-a-sandbox"
    (other / "out").mkdir(parents=True)
    (other / "out" / "trace.jsonl").write_text("{}\n")
    data = {"cases": [{"name": "a", "arms": {"with": [
        {"tracePath": str(sandbox / "out" / "trace.jsonl")},
        {"tracePath": str(other / "out" / "trace.jsonl")},
    ]}}]}

    assert analyze.cleanup_sandboxes(data) == 1
    assert not sandbox.exists()
    assert other.exists()
