"""Data models for the plugin skill evaluation framework."""

from dataclasses import dataclass, field
from typing import Any, Literal
import json


@dataclass
class AssertionResult:
    """Result of a single assertion check."""
    id: str
    check_type: str
    description: str
    passed: bool
    evidence: str
    weight: float = 1.0


@dataclass
class DimensionResult:
    """Aggregated result for one scoring dimension."""
    dimension: str
    score: float  # 0.0 - 1.0
    passed: int
    failed: int
    total: int
    assertions: list[AssertionResult] = field(default_factory=list)

    @classmethod
    def from_assertions(cls, dimension: str, assertions: list[AssertionResult]) -> "DimensionResult":
        total_weight = sum(a.weight for a in assertions)
        if total_weight == 0:
            return cls(dimension=dimension, score=0.0, passed=0, failed=0, total=0, assertions=assertions)
        passed_weight = sum(a.weight for a in assertions if a.passed)
        return cls(
            dimension=dimension,
            score=passed_weight / total_weight,
            passed=sum(1 for a in assertions if a.passed),
            failed=sum(1 for a in assertions if not a.passed),
            total=len(assertions),
            assertions=assertions,
        )


@dataclass
class SkillScore:
    """Complete score for one skill across all dimensions."""
    skill_name: str
    skill_path: str
    composite: float  # Weighted average of dimensions
    dimensions: dict[str, DimensionResult] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill_name,
            "skill_path": self.skill_path,
            "composite": round(self.composite, 4),
            "dimensions": {
                name: {
                    "score": round(dim.score, 4),
                    "passed": dim.passed,
                    "failed": dim.failed,
                    "total": dim.total,
                    "assertions": [
                        {
                            "id": a.id,
                            "type": a.check_type,
                            "desc": a.description,
                            "passed": a.passed,
                            "evidence": a.evidence,
                        }
                        for a in dim.assertions
                    ],
                }
                for name, dim in self.dimensions.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class EvalCheck:
    """A single check definition from an eval JSON file."""
    check_type: str
    description: str
    weight: float = 1.0
    # Type-specific parameters stored as kwargs
    params: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvalCheck":
        check_type = d["type"]
        desc = d.get("desc", d.get("description", ""))
        weight = d.get("weight", 1.0)
        params = {k: v for k, v in d.items() if k not in ("type", "desc", "description", "weight")}
        return cls(check_type=check_type, description=desc, weight=weight, params=params)


@dataclass
class EvalDimension:
    """A dimension definition from an eval JSON file."""
    name: str
    weight: float
    checks: list[EvalCheck]

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "EvalDimension":
        return cls(
            name=name,
            weight=d.get("weight", 0.2),
            checks=[EvalCheck.from_dict(c) for c in d.get("checks", [])],
        )


@dataclass
class EvalDefinition:
    """Complete eval definition for one skill."""
    skill: str
    skill_path: str
    dimensions: dict[str, EvalDimension]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "EvalDefinition":
        return cls(
            skill=d["skill"],
            skill_path=d["skill_path"],
            dimensions={
                name: EvalDimension.from_dict(name, dim_data)
                for name, dim_data in d.get("dimensions", {}).items()
            },
        )

    @classmethod
    def from_file(cls, path: str) -> "EvalDefinition":
        with open(path) as f:
            return cls.from_dict(json.load(f))


# --- Unified scoring shapes (Future AGI-inspired) ---
#
# Architectural rule: scorers do NOT persist results, write caches, or print.
# Callers handle all side effects. See lab/eval/README.md for the rationale.

TargetKind = Literal["skill", "agent", "trigger"]


@dataclass
class ScoreRequest:
    """Inputs to any scorer. Heterogeneous fields cover all three target kinds."""
    target_path: str
    target_kind: TargetKind
    target_name: str = ""               # Resolved at construction or by scorer
    eval_def: "EvalDefinition | None" = None
    plugin_root: str = ""
    use_cache: bool = False
    cache_dir: str = ""
    # Trigger-specific:
    triggers: dict[str, Any] | None = None       # Loaded should_trigger/should_not data
    all_descriptions: dict[str, str] | None = None
    model: str = "claude-haiku-4-5"              # Routing-judge model (trigger scorer)


@dataclass
class ScoreResult:
    """Output from any scorer. Single shape across skill/agent/trigger.
    `metadata` absorbs target-specific fields (accuracy/precision/recall, deviations,
    timestamps) without polluting the top-level shape.
    """
    target_name: str
    target_path: str
    target_kind: TargetKind
    composite: float
    dimensions: dict[str, "DimensionResult"] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    duration: float = 0.0
    cache_hit: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Emit consumer-facing dict. Shape depends on target_kind:
        - skill/agent: legacy SkillScore.to_dict() shape (composite + dimensions)
        - trigger:     legacy trigger result shape (accuracy/precision/recall + results)
        """
        if self.target_kind == "trigger":
            # Locked schema: preserve key order for byte-stable diffs
            base = {
                "skill": self.target_name,
                "accuracy": round(self.metadata.get("accuracy", 0.0), 4),
                "precision": round(self.metadata.get("precision", 0.0), 4),
                "recall": round(self.metadata.get("recall", 0.0), 4),
                "total": self.metadata.get("total", 0),
                "correct": self.metadata.get("correct", 0),
                "tp": self.metadata.get("tp", 0),
                "fp": self.metadata.get("fp", 0),
                "fn": self.metadata.get("fn", 0),
                "tn": self.metadata.get("tn", 0),
                "timestamp": self.metadata.get("timestamp", ""),
                "results": self.metadata.get("results", []),
            }
            if "model" in self.metadata:
                base["model"] = self.metadata["model"]
            if "deviations" in self.metadata:
                base["deviations"] = self.metadata["deviations"]
            return base
        # skill/agent — legacy SkillScore shape
        return {
            "skill": self.target_name,
            "skill_path": self.target_path,
            "composite": round(self.composite, 4),
            "dimensions": {
                name: {
                    "score": round(dim.score, 4),
                    "passed": dim.passed,
                    "failed": dim.failed,
                    "total": dim.total,
                    "assertions": [
                        {
                            "id": a.id,
                            "type": a.check_type,
                            "desc": a.description,
                            "passed": a.passed,
                            "evidence": a.evidence,
                        }
                        for a in dim.assertions
                    ],
                }
                for name, dim in self.dimensions.items()
            },
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())
