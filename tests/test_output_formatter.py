"""Tests for OutputFormatter (structured output formats)."""
import json
import pytest
from ai_delegate.output_formatter import OutputFormatter
from ai_delegate.models import Verdict, Finding


def make_verdict(findings=None, recommendations=None):
    return Verdict(
        task_type="audit",
        consensus_score=0.75,
        tier_used="standard",
        findings=findings or [
            Finding(severity="high", issue="SQL injection in login", location="auth.py:42",
                    recommendation="Use parameterized queries"),
            Finding(severity="medium", issue="Missing rate limiting", location="api.py:15",
                    recommendation="Add rate limiting middleware"),
        ],
        recommendations=recommendations or ["Apply parameterized queries", "Add rate limiting"],
        action_items=["Fix SQL injection immediately"],
    )


class TestOutputFormatter:
    def test_adr_format_contains_context(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="adr")
        assert "# Architecture Decision Record" in output
        assert "## Context" in output
        assert "## Decision" in output
        assert "## Consequences" in output

    def test_adr_format_includes_findings(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="adr")
        assert "SQL injection" in output

    def test_risk_matrix_format(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="risk-matrix")
        assert "| Severity |" in output
        assert "high" in output.lower()
        assert "medium" in output.lower()

    def test_risk_matrix_sorts_by_severity(self):
        formatter = OutputFormatter()
        verdict = make_verdict(findings=[
            Finding(severity="low", issue="Minor issue", recommendation="Fix later"),
            Finding(severity="critical", issue="Critical bug", recommendation="Fix now"),
            Finding(severity="medium", issue="Medium issue", recommendation="Fix soon"),
        ])
        output = formatter.format(verdict, fmt="risk-matrix")
        critical_pos = output.index("critical")
        low_pos = output.index("low")
        assert critical_pos < low_pos

    def test_playbook_format(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="playbook")
        assert "## Playbook" in output
        assert "### Step" in output
        assert "Action:" in output

    def test_playbook_contains_action_items(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="playbook")
        assert "Fix SQL injection immediately" in output

    def test_perf_profile_format(self):
        formatter = OutputFormatter()
        verdict = Verdict(
            task_type="analyze",
            consensus_score=0.85,
            tier_used="standard",
            findings=[
                Finding(severity="high", issue="N+1 query in user list", location="users.py:30",
                        impact="10x slower under load"),
            ],
            recommendations=["Add eager loading"],
            action_items=["Fix N+1 query"],
        )
        output = formatter.format(verdict, fmt="perf-profile")
        assert "## Performance Profile" in output
        assert "N+1" in output

    def test_unknown_format_raises(self):
        formatter = OutputFormatter()
        with pytest.raises(ValueError, match="Unknown format"):
            formatter.format(make_verdict(), fmt="unknown-format")

    def test_default_json_format(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="json")
        data = json.loads(output)
        assert data["task_type"] == "audit"
