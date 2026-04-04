"""Checkpoint Preview: present findings organized by concern/severity."""

from typing import Dict, List

from .models import Finding, Verdict


SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}


class CheckpointPresenter:
    """Format Verdict as human-readable checkpoint report organized by severity."""

    def format(self, verdict: Verdict) -> str:
        """Format verdict into concern-organized checkpoint report."""
        lines = []

        lines.append("=" * 60)
        lines.append(f"  CHECKPOINT REVIEW — {verdict.task_type.upper()}")
        lines.append(f"  Consensus: {verdict.consensus_score:.0%} | Tier: {verdict.tier_used.upper()}")
        lines.append("=" * 60)
        lines.append("")

        by_severity: Dict[str, List[Finding]] = {}
        for finding in verdict.findings:
            sev = finding.severity.lower()
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(finding)

        if not verdict.findings:
            lines.append("  ✅ No findings — analysis returned clean results.")
            lines.append("  ⚠️  Consider running with --elicit red-team to verify.")
            lines.append("")
        else:
            for severity in SEVERITY_ORDER:
                if severity not in by_severity:
                    continue
                findings = by_severity[severity]
                icon = SEVERITY_ICONS.get(severity, "•")
                count = len(findings)
                lines.append(f"{icon} {severity.upper()} ({count} finding{'s' if count != 1 else ''})")
                lines.append("─" * 40)
                for i, f in enumerate(findings, 1):
                    lines.append(f"  {i}. {f.issue}")
                    if f.location:
                        lines.append(f"     📍 {f.location}")
                    if f.recommendation:
                        lines.append(f"     💡 {f.recommendation}")
                lines.append("")

        if verdict.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("─" * 40)
            for rec in verdict.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")

        if verdict.action_items:
            lines.append("ACTION ITEMS")
            lines.append("─" * 40)
            for item in verdict.action_items:
                lines.append(f"  {item}")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)
