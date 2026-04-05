"""
debate_runner.py — Data models for Path D Agent Teams peer debate.

DisputedFindingsBundle: Python → Claude Code skill layer handoff (JSON).
DebateResult: DebateTeamRunner → Adjudicator (resolved vs unresolved findings).

These are pure data containers. All Agent Teams orchestration happens at the
Claude Code skill layer (debate-lead.md), not here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .models import Finding, ExpertResult


@dataclass
class DisputedFindingsBundle:
    """Serializable handoff from Python layer to Claude Code skill layer.

    Created when task.always_deep is True and consensus.score < 0.90.
    Passed as JSON string to DebateTeamRunner (debate-lead agent).
    """
    disputed_findings: list[Finding]
    expert_results: list[ExpertResult]
    task_type: str        # "audit", "architecture", or "migrate"
    file_context: str     # file path(s) being analyzed

    def to_json(self) -> str:
        """Serialize to JSON string for handoff to Claude Code skill layer."""
        return json.dumps({
            "disputed_findings": [f.to_dict() for f in self.disputed_findings],
            "expert_results": [r.to_dict() for r in self.expert_results],
            "task_type": self.task_type,
            "file_context": self.file_context,
        })

    @classmethod
    def from_json(cls, raw: str) -> "DisputedFindingsBundle":
        """Deserialize from JSON string. Raises json.JSONDecodeError on invalid input."""
        data = json.loads(raw)
        return cls(
            disputed_findings=[Finding.from_dict(f) for f in data["disputed_findings"]],
            expert_results=[ExpertResult.from_dict(r) for r in data["expert_results"]],
            task_type=data["task_type"],
            file_context=data["file_context"],
        )


@dataclass
class DebateResult:
    """Returned by DebateTeamRunner → consumed by Adjudicator.

    resolved_findings: ≥80% experts agreed — skip Adjudicator entirely.
    unresolved_findings: still disputed — escalate to Adjudicator.
    debate_summary: human-readable transcript for logging.
    """
    resolved_findings: list[Finding] = field(default_factory=list)
    unresolved_findings: list[Finding] = field(default_factory=list)
    debate_summary: str = ""

    @classmethod
    def from_json(cls, raw: str) -> "DebateResult":
        """Deserialize from JSON string. Raises json.JSONDecodeError on invalid input."""
        data = json.loads(raw)
        return cls(
            resolved_findings=[
                Finding.from_dict(f) for f in data.get("resolved_findings", [])
            ],
            unresolved_findings=[
                Finding.from_dict(f) for f in data.get("unresolved_findings", [])
            ],
            debate_summary=data.get("debate_summary", ""),
        )
