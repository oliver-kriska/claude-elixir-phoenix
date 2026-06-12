"""Tests for lab/eval/scorer.py and lab/eval/agent_scorer.py."""

import pytest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from lab.eval.scorer import score_skill, find_all_skills, find_eval, default_eval
from lab.eval.agent_scorer import score_agent, find_all_agents
from lab.eval.schemas import EvalDefinition, ScoreResult


PLUGIN_SKILLS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "plugins", "elixir-phoenix", "skills"
)
PLUGIN_AGENTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "plugins", "elixir-phoenix", "agents"
)


# --- Skill Scorer ---

class TestScoreSkill:
    def test_scores_real_skill(self):
        """Score a real skill from the plugin — should produce valid result."""
        plan_path = os.path.join(PLUGIN_SKILLS_DIR, "plan", "SKILL.md")
        if not os.path.isfile(plan_path):
            pytest.skip("Plugin not present")
        score = score_skill(plan_path)
        assert isinstance(score, ScoreResult)
        assert 0.0 <= score.composite <= 1.0
        assert "completeness" in score.dimensions
        assert "accuracy" in score.dimensions

    def test_default_eval_has_all_dimensions(self):
        """Default eval should cover all 8 dimensions."""
        eval_def = default_eval("/fake/path/SKILL.md")
        assert len(eval_def.dimensions) == 8
        for dim in ["completeness", "accuracy", "conciseness", "triggering",
                     "safety", "clarity", "specificity", "behavioral"]:
            assert dim in eval_def.dimensions

    def test_scores_with_custom_eval(self):
        """Score with a skill-specific eval JSON."""
        plan_path = os.path.join(PLUGIN_SKILLS_DIR, "plan", "SKILL.md")
        eval_path = find_eval("plan")
        if not os.path.isfile(plan_path) or not eval_path:
            pytest.skip("Plugin not present")
        eval_def = EvalDefinition.from_file(eval_path)
        score = score_skill(plan_path, eval_def)
        assert score.composite >= 0.0

    def test_file_not_found(self):
        """Should raise on missing file."""
        with pytest.raises(FileNotFoundError):
            score_skill("/nonexistent/SKILL.md")

    def test_to_dict_and_json(self):
        """SkillScore should serialize to dict and JSON."""
        plan_path = os.path.join(PLUGIN_SKILLS_DIR, "plan", "SKILL.md")
        if not os.path.isfile(plan_path):
            pytest.skip("Plugin not present")
        score = score_skill(plan_path)
        d = score.to_dict()
        assert "composite" in d
        assert "dimensions" in d
        j = score.to_json()
        parsed = json.loads(j)
        assert parsed["composite"] == d["composite"]


class TestFindAllSkills:
    def test_finds_skills(self):
        """Should find all SKILL.md files in plugin."""
        skills = find_all_skills()
        if not skills:
            pytest.skip("Plugin not present")
        assert len(skills) >= 40
        assert all(s.endswith("SKILL.md") for s in skills)


# --- Agent Scorer ---

class TestScoreAgent:
    def test_scores_real_agent(self):
        """Score a real agent from the plugin."""
        reviewer_path = os.path.join(PLUGIN_AGENTS_DIR, "elixir-reviewer.md")
        if not os.path.isfile(reviewer_path):
            pytest.skip("Plugin not present")
        score = score_agent(reviewer_path)
        assert isinstance(score, ScoreResult)
        assert 0.0 <= score.composite <= 1.0
        assert "completeness" in score.dimensions
        assert "safety" in score.dimensions
        assert "consistency" in score.dimensions

    def test_readonly_enforcement(self):
        """Review agents should have disallowedTools checked."""
        reviewer_path = os.path.join(PLUGIN_AGENTS_DIR, "elixir-reviewer.md")
        if not os.path.isfile(reviewer_path):
            pytest.skip("Plugin not present")
        score = score_agent(reviewer_path)
        safety = score.dimensions.get("safety")
        assert safety is not None
        # Should have the readonly check
        readonly_checks = [a for a in safety.assertions if "readonly" in a.check_type]
        assert len(readonly_checks) > 0


class TestFindAllAgents:
    def test_finds_agents(self):
        """Should find all agent .md files in plugin."""
        agents = find_all_agents()
        if not agents:
            pytest.skip("Plugin not present")
        assert len(agents) >= 20
        assert all(a.endswith(".md") for a in agents)


# --- Integration: All skills pass ---

class TestAllSkillsPass:
    def test_no_fixable_failures(self):
        """All skills should score >= 0.95 (excluding behavioral edge cases)."""
        skills = find_all_skills()
        if not skills:
            pytest.skip("Plugin not present")

        fixable_failures = []
        for skill_path in skills:
            name = os.path.basename(os.path.dirname(skill_path))
            eval_path = find_eval(name)
            eval_def = EvalDefinition.from_file(eval_path) if eval_path else None
            score = score_skill(skill_path, eval_def)

            if score.composite < 0.95:
                # Check if ALL failures are behavioral (edge cases)
                all_behavioral = all(
                    dim_name == "behavioral"
                    for dim_name, dim in score.dimensions.items()
                    for a in dim.assertions if not a.passed
                )
                if not all_behavioral:
                    fixable_failures.append(f"{name}: {score.composite:.3f}")

        assert fixable_failures == [], f"Fixable failures: {fixable_failures}"


class TestAllAgentsPass:
    def test_all_agents_perfect(self):
        """All agents should score >= 0.95."""
        agents = find_all_agents()
        if not agents:
            pytest.skip("Plugin not present")

        failures = []
        for agent_path in agents:
            name = os.path.basename(agent_path).replace(".md", "")
            score = score_agent(agent_path)
            if score.composite < 0.95:
                failures.append(f"{name}: {score.composite:.3f}")

        assert failures == [], f"Agent failures: {failures}"
