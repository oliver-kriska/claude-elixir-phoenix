"""Tests for lab/eval/matchers.py — 24 deterministic matchers."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", ".."))

from lab.eval.matchers import (
    parse_frontmatter, get_sections,
    section_exists, max_section_lines,
    content_present, grep_count,
    frontmatter_field,
    description_length, description_keywords, description_no_vague,
    has_iron_laws, has_gotchas, no_dangerous_patterns,
    action_density, has_examples,
    workflow_step_coverage, description_structure,
)


# --- Fixtures ---

VALID_SKILL = """---
name: test-skill
description: "Test Elixir/Phoenix patterns for ecto queries and liveview components. Use when editing test files."
effort: medium
---

# Test Skill

## Usage

Run this skill when testing.

## Iron Laws

1. **NEVER skip tests** — always run mix test
2. **DO NOT mock the database** — use real DB
3. **Check coverage** — ensure all paths tested

## Workflow

### Step 1: Setup

Create test fixtures.

### Step 2: Run

Execute the tests.

### Step 3: Verify

Check results.

## References

- `${CLAUDE_SKILL_DIR}/references/patterns.md`
"""

MINIMAL_SKILL = """---
name: minimal
description: short
---

# Minimal
"""

BROKEN_YAML = """not yaml at all
# Just Markdown
"""

EMPTY_FRONTMATTER = """---
---

# Empty FM
"""


# --- Frontmatter ---

class TestParseFrontmatter:
    def test_valid_frontmatter(self):
        fm = parse_frontmatter(VALID_SKILL)
        assert fm["name"] == "test-skill"
        assert "Elixir" in fm["description"]

    def test_broken_yaml(self):
        fm = parse_frontmatter(BROKEN_YAML)
        assert fm == {}

    def test_empty_frontmatter(self):
        fm = parse_frontmatter(EMPTY_FRONTMATTER)
        assert fm == {} or fm is None or not fm

    def test_no_frontmatter(self):
        fm = parse_frontmatter("# Just markdown\nNo frontmatter here.")
        assert fm == {}


# --- Sections ---

class TestGetSections:
    def test_finds_sections(self):
        sections = get_sections(VALID_SKILL)
        assert "Usage" in sections
        assert "Iron Laws" in sections
        assert "Workflow" in sections

    def test_h3_sections(self):
        sections = get_sections(VALID_SKILL)
        assert any("Step 1" in name for name in sections)

    def test_empty_content(self):
        sections = get_sections("---\nname: x\n---\n")
        assert sections == {}


# --- Section matchers ---

class TestSectionExists:
    def test_found(self):
        passed, _ = section_exists(VALID_SKILL, section="Usage")
        assert passed

    def test_not_found(self):
        passed, _ = section_exists(VALID_SKILL, section="Nonexistent")
        assert not passed

    def test_case_insensitive(self):
        passed, _ = section_exists(VALID_SKILL, section="usage")
        assert passed


class TestMaxSectionLines:
    def test_under_limit(self):
        passed, _ = max_section_lines(VALID_SKILL, max=50)
        assert passed

    def test_over_limit(self):
        long_content = "---\nname: x\n---\n## Big\n" + "\n".join(f"line {i}" for i in range(100))
        passed, evidence = max_section_lines(long_content, max=10)
        assert not passed
        assert "Big" in evidence


# --- Content matchers ---

class TestContentPresent:
    def test_found(self):
        passed, _ = content_present(VALID_SKILL, pattern="Iron Laws")
        assert passed

    def test_regex(self):
        passed, _ = content_present(VALID_SKILL, pattern=r"Step \d")
        assert passed

    def test_not_found(self):
        passed, _ = content_present(VALID_SKILL, pattern="xyzzy_nonexistent")
        assert not passed


class TestGrepCount:
    def test_within_range(self):
        passed, _ = grep_count(VALID_SKILL, pattern=r"\*\*NEVER", min=1, max=5)
        assert passed

    def test_below_min(self):
        passed, _ = grep_count(VALID_SKILL, pattern="xyzzy", min=1)
        assert not passed


# --- Frontmatter matchers ---

class TestFrontmatterField:
    def test_exists(self):
        passed, _ = frontmatter_field(VALID_SKILL, field="name")
        assert passed

    def test_missing(self):
        passed, _ = frontmatter_field(MINIMAL_SKILL, field="effort")
        assert not passed

    def test_expected_value(self):
        passed, _ = frontmatter_field(VALID_SKILL, field="effort", expected="medium")
        assert passed


class TestDescriptionLength:
    def test_in_range(self):
        passed, _ = description_length(VALID_SKILL, min=50, max=500)
        assert passed

    def test_too_short(self):
        passed, _ = description_length(MINIMAL_SKILL, min=50, max=500)
        assert not passed


class TestDescriptionKeywords:
    def test_enough_keywords(self):
        passed, _ = description_keywords(VALID_SKILL, min=3)
        assert passed

    def test_too_few(self):
        passed, _ = description_keywords(MINIMAL_SKILL, min=3)
        assert not passed


class TestDescriptionNoVague:
    def test_no_vague(self):
        passed, _ = description_no_vague(VALID_SKILL)
        assert passed

    def test_has_vague(self):
        vague = '---\nname: x\ndescription: "This is a general purpose tool for various tasks"\n---\n'
        passed, _ = description_no_vague(vague)
        assert not passed


# --- Safety matchers ---

class TestHasIronLaws:
    def test_has_items(self):
        passed, evidence = has_iron_laws(VALID_SKILL, min_count=3)
        assert passed
        assert "3 items" in evidence

    def test_missing_section(self):
        passed, _ = has_iron_laws(MINIMAL_SKILL)
        assert not passed

    def test_min_count(self):
        passed, _ = has_iron_laws(VALID_SKILL, min_count=10)
        assert not passed


class TestHasGotchas:
    def test_has_items(self):
        skill = VALID_SKILL + (
            "\n## Gotchas\n\n"
            "1. **Mount runs twice** — guard side effects with connected?/1\n"
            "2. **Oban args are string keys** — match %{\"id\" => id}, not :id\n"
        )
        passed, evidence = has_gotchas(skill, min_count=2)
        assert passed
        assert "2 items" in evidence

    def test_missing_section(self):
        passed, evidence = has_gotchas(VALID_SKILL)
        assert not passed
        assert "optional" in evidence.lower()

    def test_min_count(self):
        skill = VALID_SKILL + "\n## Gotchas\n\n- One sharp edge\n"
        passed, _ = has_gotchas(skill, min_count=3)
        assert not passed


class TestNoDangerousPatterns:
    def test_clean(self):
        passed, _ = no_dangerous_patterns(VALID_SKILL)
        assert passed

    def test_dangerous_outside_iron_laws(self):
        bad = VALID_SKILL + "\n## Examples\nUse `String.to_atom(input)` for this.\n"
        passed, _ = no_dangerous_patterns(bad)
        assert not passed

    def test_safe_in_iron_laws(self):
        safe = "---\nname: x\n---\n## Iron Laws\n1. NEVER use String.to_atom(input)\n"
        passed, _ = no_dangerous_patterns(safe)
        assert passed


# --- Clarity matchers ---

class TestActionDensity:
    def test_high_density(self):
        high = "---\nname: x\n---\n## Steps\n1. Run mix test\n2. Check output\n3. Fix errors\n4. Run again\n"
        passed, _ = action_density(high, min_ratio=0.3)
        assert passed

    def test_low_density(self):
        low = "---\nname: x\n---\n## Theory\nThis is some theory about patterns.\nMore theory here.\nAnd more.\n"
        passed, _ = action_density(low, min_ratio=0.5)
        assert not passed


class TestHasExamples:
    def test_has_code_blocks(self):
        passed, _ = has_examples(VALID_SKILL, min_blocks=0)
        assert passed

    def test_missing_examples(self):
        passed, _ = has_examples(MINIMAL_SKILL, min_blocks=1)
        assert not passed


class TestWorkflowStepCoverage:
    def test_complete_steps(self):
        passed, _ = workflow_step_coverage(VALID_SKILL)
        assert passed

    def test_missing_step(self):
        gap = "---\nname: x\n---\n## Step 1\nDo this.\n## Step 3\nDo that.\n"
        passed, evidence = workflow_step_coverage(gap)
        assert not passed
        assert "2" in evidence

    def test_no_steps(self):
        passed, _ = workflow_step_coverage(MINIMAL_SKILL)
        assert passed  # No steps = not a workflow skill


class TestDescriptionStructure:
    def test_has_what_and_when(self):
        passed, _ = description_structure(VALID_SKILL)
        assert passed

    def test_missing_when(self):
        no_when = '---\nname: x\ndescription: "Does something cool"\n---\n'
        passed, evidence = description_structure(no_when)
        assert not passed
        assert "when" in evidence.lower()
