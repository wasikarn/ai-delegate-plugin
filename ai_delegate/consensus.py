"""
consensus.py — Pure consensus calculation extracted from debate/orchestrator.py.

Responsibilities:
- ConsensusCalculator.calculate(): aggregate ExpertResult list → ConsensusResult
- normalize_finding(): translate domain-specific finding dicts to canonical Finding

No side effects. Thread-safe (reads only). Does not import from debate/.
"""
import math
from typing import Dict, List

from ai_delegate.constants import QualityThresholds
from ai_delegate.models import ConsensusResult, ExpertResult, Finding


class ConsensusCalculator:
    """Calculate consensus between expert findings.

    Deduplication key: (finding.severity.lower(), finding.issue.lower())
    Agreement threshold: ceil(N_experts * CONSENSUS_PERCENTAGE / 100)
    """

    @staticmethod
    def calculate(expert_results: List[ExpertResult]) -> ConsensusResult:
        """Calculate agreement score between expert findings.

        Deduplication is case-insensitive: findings with different casing
        (e.g., "High" vs "HIGH", "xss" vs "XSS") are treated as the same issue.

        Args:
            expert_results: List of expert analysis results. Not modified.

        Returns:
            ConsensusResult — new object. findings are references, not copies.
        """
        if not expert_results:
            return ConsensusResult(score=0.0)

        all_findings: List[Finding] = []
        for result in expert_results:
            all_findings.extend(result.findings)

        if not all_findings:
            return ConsensusResult(score=1.0)

        finding_counts: Dict[tuple, int] = {}
        finding_by_key: Dict[tuple, List[Finding]] = {}
        finding_key_to_expert: Dict[tuple, str] = {}

        for result in expert_results:
            for finding in result.findings:
                key = (finding.severity.lower(), finding.issue.lower())
                finding_counts[key] = finding_counts.get(key, 0) + 1
                if key not in finding_by_key:
                    finding_by_key[key] = []
                    finding_key_to_expert[key] = result.expert_name
                finding_by_key[key].append(finding)

        threshold = math.ceil(
            len(expert_results) * QualityThresholds.CONSENSUS_PERCENTAGE / 100
        )

        consensus_findings: List[Finding] = []
        disputed_findings: List[Finding] = []
        unique_findings: Dict[str, List[Finding]] = {}

        for key, count in finding_counts.items():
            if count >= threshold:
                consensus_findings.append(finding_by_key[key][0])
            elif count > 1:
                disputed_findings.append(finding_by_key[key][0])
            else:
                expert_name = finding_key_to_expert.get(key, "unknown")
                if expert_name not in unique_findings:
                    unique_findings[expert_name] = []
                unique_findings[expert_name].append(finding_by_key[key][0])

        total_unique = len(finding_counts)
        consensus_count = sum(1 for c in finding_counts.values() if c >= threshold)
        score = consensus_count / total_unique if total_unique > 0 else 1.0

        disagreement_parts = []
        for expert_name, findings in unique_findings.items():
            issues = [f.issue for f in findings[:3]]
            if issues:
                disagreement_parts.append(
                    f"{expert_name} uniquely raised: {', '.join(issues)}"
                )
        disagreement_summary = "; ".join(disagreement_parts)

        return ConsensusResult(
            score=score,
            consensus_findings=consensus_findings,
            disputed_findings=disputed_findings,
            unique_findings=unique_findings,
            disagreement_summary=disagreement_summary,
        )


def normalize_finding(raw: dict) -> Finding:
    """Convert domain-specific finding dict to canonical Finding.

    Supports two formats:
    1. Canonical (schema_version: "1.0"): {"severity", "issue", "recommendation", "location"}
    2. Domain format: {"severity", "title", "category", "file", "line", "description", "recommendation"}
    """
    issue = raw.get("title") or raw.get("issue", "")
    location = raw.get("location")
    if not location and raw.get("file"):
        location = f"{raw['file']}:{raw.get('line', '')}"

    return Finding(
        severity=raw.get("severity", "medium"),
        issue=issue,
        location=location,
        recommendation=raw.get("recommendation"),
    )
