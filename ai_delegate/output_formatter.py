"""Structured output formatters for ai-delegate verdicts."""

import json

from .models import Finding, Verdict

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _severity_rank(f: Finding) -> int:
    return _SEVERITY_ORDER.get(f.severity.lower(), 5)


class OutputFormatter:
    """Formats Verdict into various structured output formats."""

    def format(self, verdict: Verdict, fmt: str = "json") -> str:
        if fmt == "json":
            return json.dumps(verdict.to_dict(), indent=2)
        elif fmt == "adr":
            return self._format_adr(verdict)
        elif fmt == "risk-matrix":
            return self._format_risk_matrix(verdict)
        elif fmt == "playbook":
            return self._format_playbook(verdict)
        elif fmt == "perf-profile":
            return self._format_perf_profile(verdict)
        else:
            raise ValueError(f"Unknown format: {fmt}. Valid: json, adr, risk-matrix, playbook, perf-profile")

    def _format_adr(self, verdict: Verdict) -> str:
        lines = [
            "# Architecture Decision Record",
            f"\n**Task:** {verdict.task_type.upper()}",
            f"**Consensus:** {verdict.consensus_score:.0%}",
            f"**Tier:** {verdict.tier_used}",
            "\n## Context",
            f"Analysis identified {len(verdict.findings)} findings across {verdict.task_type} review.",
            "\n## Decision",
        ]
        for r in verdict.recommendations:
            lines.append(f"- {r}")
        lines.append("\n## Consequences")
        for f in sorted(verdict.findings, key=_severity_rank):
            loc = f" ({f.location})" if f.location else ""
            lines.append(f"- **[{f.severity.upper()}]** {f.issue}{loc}")
        lines.append("\n## Action Items")
        for item in verdict.action_items:
            lines.append(f"- [ ] {item}")
        return "\n".join(lines)

    def _format_risk_matrix(self, verdict: Verdict) -> str:
        lines = [
            "# Risk Matrix",
            f"\n**Task:** {verdict.task_type.upper()} | **Consensus:** {verdict.consensus_score:.0%}",
            "\n| Severity | Issue | Location | Recommendation |",
            "|----------|-------|----------|----------------|",
        ]
        for f in sorted(verdict.findings, key=_severity_rank):
            loc = f.location or "—"
            rec = f.recommendation or "—"
            lines.append(f"| {f.severity} | {f.issue} | {loc} | {rec} |")
        return "\n".join(lines)

    def _format_playbook(self, verdict: Verdict) -> str:
        lines = [
            "## Playbook",
            f"\n**Task:** {verdict.task_type.upper()} | **Tier:** {verdict.tier_used}",
            "\n### Immediate Actions",
        ]
        for i, item in enumerate(verdict.action_items, 1):
            lines.append(f"\n### Step {i}")
            lines.append(f"**Action:** {item}")
        critical = [f for f in verdict.findings if f.severity.lower() in ("critical", "high")]
        if critical:
            lines.append("\n### Critical Findings to Address")
            for f in critical:
                loc = f" at `{f.location}`" if f.location else ""
                lines.append(f"\n**{f.issue}**{loc}")
                if f.recommendation:
                    lines.append(f"- Recommendation: {f.recommendation}")
        return "\n".join(lines)

    def _format_perf_profile(self, verdict: Verdict) -> str:
        lines = [
            "## Performance Profile",
            f"\n**Task:** {verdict.task_type.upper()} | **Consensus:** {verdict.consensus_score:.0%}",
            "\n### Findings",
        ]
        for f in sorted(verdict.findings, key=_severity_rank):
            loc = f" (`{f.location}`)" if f.location else ""
            impact = f"\n  - Impact: {f.impact}" if f.impact else ""
            rec = f"\n  - Fix: {f.recommendation}" if f.recommendation else ""
            lines.append(f"\n**[{f.severity.upper()}]** {f.issue}{loc}{impact}{rec}")
        lines.append("\n### Recommendations")
        for r in verdict.recommendations:
            lines.append(f"- {r}")
        return "\n".join(lines)
