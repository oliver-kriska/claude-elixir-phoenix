"""Multi-plugin routing pool for the trigger scorer: namespacing, fixture stems, CLI.

Deterministic: the judge is never called. Every model-facing path is mocked.
"""

import json
import os
import subprocess
import sys

import pytest

from lab.eval import trigger_scorer
from lab.eval.plugins import listing, namespace_map, plugin_dir

REWRITE_COMMANDS = ("start", "analyze", "architect", "roadmap", "verify")


def _skill(root, name, description, extra=""):
    skill_dir = root / "skills" / name
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: {name}\ndescription: \"{description}\"\n{extra}---\n\n# {name}\n")


@pytest.fixture
def two_plugin_pool(tmp_path, monkeypatch):
    """A phx-like default plugin plus a namespaced `rewrite` plugin that reuses the name `verify`."""
    phx = tmp_path / "phx"
    rewrite = tmp_path / "rewrite"
    _skill(phx, "plan", "Plan Phoenix features")
    _skill(phx, "verify", "Compile, format and test Phoenix changes")
    _skill(rewrite, "analyze", "Analyze a legacy app before rewriting it in Elixir")
    _skill(rewrite, "verify", "Verify a rewrite slice against its parity obligations")
    _skill(rewrite, "elixir-way", "Map legacy mechanisms to Elixir", extra="user-invocable: false\n")
    _skill(rewrite, "hidden", "Never shown to the model", extra="disable-model-invocation: true\n")
    monkeypatch.setattr(trigger_scorer, "description_sources", lambda: [(None, str(phx)), ("rewrite", str(rewrite))])
    return phx, rewrite


def test_fixture_stem_and_skill_key():
    assert trigger_scorer.skill_key(None, "verify") == "verify"
    assert trigger_scorer.skill_key("rewrite", "verify") == "rewrite:verify"
    assert trigger_scorer.fixture_stem("verify") == "verify"
    assert trigger_scorer.fixture_stem("rewrite:elixir-way") == "rewrite-elixir-way"


def test_pool_namespaces_secondary_plugins_and_keeps_default_bare(two_plugin_pool):
    descriptions = trigger_scorer.load_all_descriptions()

    assert list(descriptions) == ["plan", "verify", "rewrite:analyze", "rewrite:elixir-way", "rewrite:verify"]
    assert descriptions["verify"].startswith("Compile")
    assert descriptions["rewrite:verify"].startswith("Verify a rewrite slice")


def test_pool_keeps_reference_skills_and_drops_model_hidden_ones(two_plugin_pool):
    descriptions = trigger_scorer.load_all_descriptions()

    assert "rewrite:elixir-way" in descriptions
    assert "rewrite:hidden" not in descriptions


def test_pool_rejects_keys_that_share_a_fixture_stem(two_plugin_pool):
    phx, _rewrite = two_plugin_pool
    _skill(phx, "rewrite-analyze", "A default-plugin skill whose name collides with a namespaced stem")

    with pytest.raises(ValueError, match="rewrite-analyze.json"):
        trigger_scorer.load_all_descriptions()


def test_invalid_description_in_secondary_plugin_names_namespaced_key(two_plugin_pool):
    _phx, rewrite = two_plugin_pool
    (rewrite / "skills" / "broken").mkdir()
    (rewrite / "skills" / "broken" / "SKILL.md").write_text("---\nname: broken\ndescription:\n---\n")

    with pytest.raises(ValueError, match="rewrite:broken"):
        trigger_scorer.load_all_descriptions()


def test_real_sources_put_phx_first_and_namespace_rewrite_by_manifest():
    sources = trigger_scorer.description_sources()

    assert sources[0] == (None, trigger_scorer.PLUGIN_ROOT)
    assert ("rewrite", plugin_dir("rewrite")) in sources
    namespaces = {os.path.realpath(root): name for name, root in namespace_map().items()}
    assert namespaces[os.path.realpath(trigger_scorer.PLUGIN_ROOT)] == trigger_scorer.DEFAULT_NAMESPACE


def test_real_pool_covers_every_rewrite_skill_beside_phx_verify():
    descriptions = trigger_scorer.load_all_descriptions()

    assert "verify" in descriptions and "rewrite:verify" in descriptions
    assert descriptions["verify"] != descriptions["rewrite:verify"]
    rewrite_skills = {f"rewrite:{name}" for name in listing(plugin_dir("rewrite"), "skills")}
    assert rewrite_skills == {key for key in descriptions if key.startswith("rewrite:")}
    assert {f"rewrite:{name}" for name in REWRITE_COMMANDS} | {"rewrite:elixir-way"} <= rewrite_skills


def test_real_fixture_set_passes_the_all_preflight():
    descriptions = trigger_scorer.load_all_descriptions()

    fixtures = trigger_scorer.load_all_trigger_files(set(descriptions))

    assert set(fixtures) == set(descriptions)
    assert fixtures["rewrite:verify"]["skill"] == "rewrite:verify"
    assert fixtures["verify"]["skill"] == "verify"


def test_rewrite_fixtures_have_disjoint_positives_and_hard_negatives():
    for name in (*REWRITE_COMMANDS, "elixir-way"):
        fixture = trigger_scorer.load_trigger_file(f"rewrite:{name}")
        positives, negatives = fixture["should_trigger"], fixture["should_not_trigger"]
        assert len(positives) >= 5 and len(negatives) >= 5, name
        assert len(set(positives)) == len(positives) and len(set(negatives)) == len(negatives), name
        assert not set(positives) & set(negatives), name


def test_rewrite_positives_span_many_source_stacks():
    """Guards against fixtures that only ever say Rails."""
    text = " ".join(
        prompt
        for name in (*REWRITE_COMMANDS, "elixir-way")
        for prompt in trigger_scorer.load_trigger_file(f"rewrite:{name}")["should_trigger"]
    ).lower()

    for stack in ("django", "laravel", "nestjs", "express", "go ", "spring boot", ".net", "python", "kafka",
                  "pipeline", "wordpress"):
        assert stack in text, stack


def test_load_trigger_file_reads_the_safe_stem(tmp_path, monkeypatch):
    (tmp_path / "rewrite-analyze.json").write_text(json.dumps({"skill": "rewrite:analyze"}))
    monkeypatch.setattr(trigger_scorer, "TRIGGERS_DIR", str(tmp_path))

    assert trigger_scorer.load_trigger_file("rewrite:analyze") == {"skill": "rewrite:analyze"}
    assert trigger_scorer.load_trigger_file("rewrite-analyze") == {"skill": "rewrite:analyze"}


def _fixture(tmp_path, stem, skill, **extra):
    data = {"skill": skill, "should_trigger": [f"{skill} yes"], "should_not_trigger": [f"{skill} no"], **extra}
    (tmp_path / f"{stem}.json").write_text(json.dumps(data))


def test_all_preflight_matches_fixtures_by_stem(tmp_path, monkeypatch):
    _fixture(tmp_path, "verify", "verify")
    _fixture(tmp_path, "rewrite-verify", "rewrite:verify")
    monkeypatch.setattr(trigger_scorer, "TRIGGERS_DIR", str(tmp_path))

    fixtures = trigger_scorer.load_all_trigger_files({"verify", "rewrite:verify"})

    assert fixtures["rewrite:verify"]["should_trigger"] == ["rewrite:verify yes"]
    assert fixtures["verify"]["should_trigger"] == ["verify yes"]


def test_all_preflight_reports_missing_namespaced_fixture(tmp_path, monkeypatch):
    _fixture(tmp_path, "verify", "verify")
    monkeypatch.setattr(trigger_scorer, "TRIGGERS_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="missing fixtures: rewrite-verify"):
        trigger_scorer.load_all_trigger_files({"verify", "rewrite:verify"})


def test_all_preflight_rejects_fixture_declaring_another_skill(tmp_path, monkeypatch):
    _fixture(tmp_path, "rewrite-verify", "verify")
    monkeypatch.setattr(trigger_scorer, "TRIGGERS_DIR", str(tmp_path))

    with pytest.raises(ValueError, match="declares skill 'verify'"):
        trigger_scorer.load_all_trigger_files({"rewrite:verify"})


@pytest.mark.parametrize(
    ("output", "expected"),
    [
        ("rewrite:verify\nverify", ["rewrite:verify", "verify"]),
        ("1. /rewrite:verify", ["rewrite:verify"]),
        ("`rewrite:analyze`", ["rewrite:analyze"]),
        ("phx:verify", ["verify"]),
        ("rewrite-analyze", ["rewrite:analyze"]),
        ("analyze", None),
        ("rewrite:plan", None),
        ("phx:verify\nverify", None),
        ("none\n\nThis is a language choice, so **plan** would only apply later.", []),
        ("none\nplan", None),
    ],
)
def test_judge_output_resolves_namespaced_names(output, expected):
    names = {"verify", "plan", "rewrite:verify", "rewrite:analyze"}

    assert trigger_scorer._parse_judge_output(output, names) == expected


def test_judge_prompt_lists_both_verify_skills(monkeypatch):
    captured = {}

    def run(command, **_kwargs):
        captured["prompt"] = command[2]
        return subprocess.CompletedProcess(command, 0, stdout="rewrite:verify\n", stderr="")

    monkeypatch.setattr(trigger_scorer.subprocess, "run", run)
    pool = {"verify": "Compile and test", "rewrite:verify": "Verify a rewrite slice"}

    assert trigger_scorer.ask_model(pool, "verify slice 02 of the port") == ["rewrite:verify"]
    assert "- verify: Compile and test" in captured["prompt"]
    assert "- rewrite:verify: Verify a rewrite slice" in captured["prompt"]


def test_namespaced_cache_never_touches_the_phx_cache(tmp_path, monkeypatch):
    pool = {"verify": "Compile and test", "rewrite:verify": "Verify a rewrite slice"}
    triggers = {"should_trigger": ["verify slice 02"], "should_not_trigger": ["run mix test"]}
    monkeypatch.setattr(trigger_scorer, "RESULTS_DIR", str(tmp_path))
    monkeypatch.setattr(
        trigger_scorer,
        "ask_model",
        lambda _pool, prompt, _model=None: ["rewrite:verify"] if prompt == "verify slice 02" else ["verify"],
    )

    result = trigger_scorer.score_skill_triggers("rewrite:verify", triggers, pool)

    assert result["skill"] == "rewrite:verify"
    assert result["accuracy"] == 1.0
    assert sorted(os.listdir(tmp_path)) == ["rewrite-verify.json"]
    assert json.loads((tmp_path / "rewrite-verify.json").read_text())["skill"] == "rewrite:verify"

    monkeypatch.setattr(
        trigger_scorer,
        "ask_model",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("cache hit must not call the judge")),
    )
    cached = trigger_scorer.score_skill_triggers("rewrite:verify", triggers, pool, use_cache=True)
    assert cached["accuracy"] == 1.0


@pytest.mark.parametrize("argument", ["rewrite:verify", "rewrite-verify", "/rewrite:verify"])
def test_single_skill_cli_resolves_namespaced_names(argument, monkeypatch, capsys):
    seen = {}
    monkeypatch.setattr(sys, "argv", ["trigger_scorer", "--skill", argument, "--summary"])
    monkeypatch.setattr(trigger_scorer, "load_all_descriptions", lambda: {"verify": "V", "rewrite:verify": "RV"})
    monkeypatch.setattr(trigger_scorer, "load_trigger_file", lambda name: seen.setdefault("fixture", name) and {"x": 1})

    def score(name, *_args, **_kwargs):
        seen["scored"] = name
        return {"accuracy": 1.0, "precision": 1.0, "recall": 1.0}

    monkeypatch.setattr(trigger_scorer, "score_skill_triggers", score)

    assert trigger_scorer.main() == 0
    assert seen == {"fixture": "rewrite:verify", "scored": "rewrite:verify"}
    assert capsys.readouterr().out.startswith("rewrite:verify [")


def test_single_skill_cli_keeps_bare_phx_names(monkeypatch):
    seen = {}
    monkeypatch.setattr(sys, "argv", ["trigger_scorer", "--skill", "phx:verify", "--summary"])
    monkeypatch.setattr(trigger_scorer, "load_all_descriptions", lambda: {"verify": "V", "rewrite:verify": "RV"})
    monkeypatch.setattr(trigger_scorer, "load_trigger_file", lambda _name: {"x": 1})
    monkeypatch.setattr(
        trigger_scorer,
        "score_skill_triggers",
        lambda name, *_a, **_k: seen.setdefault("scored", name) and {"accuracy": 1.0, "precision": 1.0, "recall": 1.0},
    )

    assert trigger_scorer.main() == 0
    assert seen["scored"] == "verify"


def test_single_skill_cli_rejects_a_skill_outside_the_pool(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["trigger_scorer", "--skill", "rewrite:nope", "--summary"])
    monkeypatch.setattr(trigger_scorer, "load_all_descriptions", lambda: {"verify": "V"})
    monkeypatch.setattr(
        trigger_scorer,
        "score_skill_triggers",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("scored an unknown skill")),
    )

    assert trigger_scorer.main() == 1


def test_all_cli_scores_namespaced_skills_into_the_aggregate(tmp_path, monkeypatch):
    triggers_dir = tmp_path / "triggers"
    triggers_dir.mkdir()
    _fixture(triggers_dir, "verify", "verify")
    _fixture(triggers_dir, "rewrite-verify", "rewrite:verify")
    aggregate_path = tmp_path / "aggregate.json"
    scored = []
    monkeypatch.setattr(sys, "argv", ["trigger_scorer", "--all", "--summary"])
    monkeypatch.setattr(trigger_scorer, "TRIGGERS_DIR", str(triggers_dir))
    monkeypatch.setattr(trigger_scorer, "load_all_descriptions", lambda: {"verify": "V", "rewrite:verify": "RV"})
    monkeypatch.setattr(trigger_scorer, "aggregate_path_for_model", lambda _model: str(aggregate_path))

    def score(name, triggers, *_args, **_kwargs):
        scored.append((name, triggers["skill"]))
        return {"accuracy": 1.0, "precision": 1.0, "recall": 1.0}

    monkeypatch.setattr(trigger_scorer, "score_skill_triggers", score)

    assert trigger_scorer.main() == 0
    assert scored == [("rewrite:verify", "rewrite:verify"), ("verify", "verify")]
    assert set(json.loads(aggregate_path.read_text())["per_skill"]) == {"verify", "rewrite:verify"}


@pytest.mark.parametrize(
    ("path", "key"),
    [
        (os.path.join(plugin_dir("rewrite"), "skills", "verify", "SKILL.md"), "rewrite:verify"),
        (os.path.join(trigger_scorer.PLUGIN_ROOT, "skills", "verify", "SKILL.md"), "verify"),
        ("/skills/demo/SKILL.md", "demo"),
    ],
)
def test_skill_key_for_path(path, key):
    assert trigger_scorer.skill_key_for_path(path) == key
