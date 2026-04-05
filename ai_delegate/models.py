"""
Data models for AI Delegation Framework.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import json

from .constants import FALLBACK_MODEL, TaskTypes, QualityThresholds


class Tier(str, Enum):
    """Quality assurance tier."""
    FAST = "fast"
    STANDARD = "standard"
    DEEP = "deep"
    AUTO = "auto"


class Structure(str, Enum):
    """Organizational structure."""
    FLAT = "flat"
    HIERARCHICAL = "hierarchical"
    MATRIX = "matrix"
    TEAM_BASED = "team-based"
    AUTO = "auto"


@dataclass
class Finding:
    """A single finding from an expert."""
    severity: str
    issue: str
    location: Optional[str] = None
    recommendation: Optional[str] = None
    cwe: Optional[str] = None  # For security findings
    impact: Optional[str] = None  # For performance findings
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "severity": self.severity,
            "issue": self.issue,
        }
        if self.location:
            result["location"] = self.location
        if self.recommendation:
            result["recommendation"] = self.recommendation
        if self.cwe:
            result["cwe"] = self.cwe
        if self.impact:
            result["impact"] = self.impact
        if self.metadata:
            result.update(self.metadata)
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Finding":
        """Create from dictionary."""
        return cls(
            severity=data.get("severity", "medium"),
            issue=data.get("issue", ""),
            location=data.get("location"),
            recommendation=data.get("recommendation"),
            cwe=data.get("cwe"),
            impact=data.get("impact"),
            metadata={k: v for k, v in data.items()
                     if k not in ["severity", "issue", "location", "recommendation", "cwe", "impact"]},
        )


@dataclass
class ExpertResult:
    """Result from a single expert analysis."""
    expert_name: str
    expert_type: str
    findings: List[Finding] = field(default_factory=list)
    raw_output: Optional[str] = None
    _parsed_output: Optional[Dict[str, Any]] = field(default=None, repr=False)
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    persona_name: Optional[str] = None

    @property
    def success(self) -> bool:
        """Check if expert analysis succeeded."""
        return self.error is None

    @property
    def parsed_output(self) -> Dict[str, Any]:
        """Get parsed JSON output, cached for performance."""
        if self._parsed_output is None and self.raw_output:
            try:
                self._parsed_output = json.loads(self.raw_output)
            except json.JSONDecodeError:
                self._parsed_output = {}
        return self._parsed_output or {}

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "expert_name": self.expert_name,
            "expert_type": self.expert_type,
            "findings": [f.to_dict() for f in self.findings],
            "raw_output": self.raw_output,
            "error": self.error,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpertResult":
        """Create from dictionary (inverse of to_dict)."""
        return cls(
            expert_name=data.get("expert_name", ""),
            expert_type=data.get("expert_type", ""),
            findings=[Finding.from_dict(f) for f in data.get("findings", [])],
            raw_output=data.get("raw_output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms"),
        )


@dataclass
class ConsensusResult:
    """Result of consensus calculation between experts."""
    score: float  # 0.0 to 1.0
    consensus_findings: List[Finding] = field(default_factory=list)
    disputed_findings: List[Finding] = field(default_factory=list)
    unique_findings: Dict[str, List[Finding]] = field(default_factory=dict)
    disagreement_summary: str = ""

    @property
    def percentage(self) -> float:
        """Get consensus as percentage."""
        return self.score * 100

    @property
    def tier(self) -> str:
        """Determine tier based on consensus score."""
        # Thresholds are 0-100 in constants; score is 0-1
        tier_thresholds = [
            (QualityThresholds.FAST_THRESHOLD / 100, Tier.FAST.value),
            (QualityThresholds.STANDARD_THRESHOLD / 100, Tier.STANDARD.value),
        ]
        for threshold, tier_value in tier_thresholds:
            if self.score >= threshold:
                return tier_value
        return Tier.DEEP.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "percentage": self.percentage,
            "tier": self.tier,
            "consensus_findings": [f.to_dict() for f in self.consensus_findings],
            "disputed_findings": [f.to_dict() for f in self.disputed_findings],
            "unique_findings": {
                k: [f.to_dict() for f in v]
                for k, v in self.unique_findings.items()
            },
            "disagreement_summary": self.disagreement_summary,
        }


@dataclass
class Verdict:
    """Final adjudicated verdict."""
    task_type: str
    consensus_score: float
    tier_used: str
    findings: List[Finding] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    raw_output: Optional[str] = None
    judge_confidence: Optional[float] = None  # For DEEP tier
    judge_reasoning: Optional[str] = None  # For DEEP tier

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = {
            "task_type": self.task_type,
            "consensus_score": self.consensus_score,
            "tier_used": self.tier_used,
            "findings": [f.to_dict() for f in self.findings],
            "recommendations": self.recommendations,
            "action_items": self.action_items,
        }
        if self.judge_confidence is not None:
            result["judge_confidence"] = self.judge_confidence
        if self.judge_reasoning:
            result["judge_reasoning"] = self.judge_reasoning
        return result


@dataclass
class TaskConfig:
    """Configuration for a specific task."""
    task_type: str
    experts: Dict[str, str]  # expert_name -> prompt
    display_name: str
    description: str
    adjudicator_role: str
    output_format: str
    default_model: str
    always_deep: bool = False  # Some tasks always use DEEP tier
    expert_models: Dict[str, str] = field(default_factory=dict)
    # Maps expert_name -> model_name override. Empty = all experts use session client.
    sparse_topology_k: Optional[int] = None
    # None = full peer visibility. Integer k = each expert sees k peers (round-robin).

    @classmethod
    def from_task_type(
        cls,
        task_type: str,
        expert_models: Optional[Dict[str, str]] = None,
        sparse_topology_k: Optional[int] = None,
    ) -> "TaskConfig":
        """Create task config from task type."""
        from .config import (
            TASK_DISPLAY_NAMES,
            TASK_EXPERT_DESCRIPTIONS,
            TASK_ADJUDICATOR_ROLES,
            TASK_OUTPUT_FORMATS,
            DEFAULT_MODELS,
            EXPERT_CONFIGS,
        )

        # Map task type to expert config
        expert_map = {
            "audit": "security",
            "analyze": "performance",
            "architecture": "architecture",
            "refactor": "refactor",
            "migrate": "migrate",
            "review": "review",
        }

        expert_type = expert_map.get(task_type)
        if not expert_type:
            raise ValueError(f"Unknown task type: {task_type}")

        return cls(
            task_type=task_type,
            experts=EXPERT_CONFIGS.get(expert_type, {}),
            display_name=TASK_DISPLAY_NAMES.get(task_type, task_type.upper()),
            description=TASK_EXPERT_DESCRIPTIONS.get(task_type, ""),
            adjudicator_role=TASK_ADJUDICATOR_ROLES.get(task_type, ""),
            output_format=TASK_OUTPUT_FORMATS.get(task_type, ""),
            default_model=DEFAULT_MODELS.get(task_type, FALLBACK_MODEL),
            always_deep=task_type in TaskTypes.ALWAYS_DEEP,
            expert_models=expert_models or {},
            sparse_topology_k=sparse_topology_k,
        )