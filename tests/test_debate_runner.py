"""Tests for ai_delegate/debate_runner.py — DisputedFindingsBundle and DebateResult."""
import json
import pytest
from ai_delegate.models import Finding, ExpertResult
from ai_delegate.debate_runner import DisputedFindingsBundle, DebateResult


def _finding(severity="high", issue="SQL injection", recommendation="use params"):
    return Finding(severity=severity, issue=issue, recommendation=recommendation)


def _expert_result(name="owasp", findings=None):
    return ExpertResult(
        expert_name=name,
        expert_type="security",
        findings=findings or [_finding()],
    )


class TestDisputedFindingsBundle:
    def test_roundtrip_with_findings_and_experts(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[_finding()],
            expert_results=[_expert_result("owasp"), _expert_result("auth")],
            task_type="audit",
            file_context="src/auth.py",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())

        assert restored.task_type == "audit"
        assert restored.file_context == "src/auth.py"
        assert len(restored.disputed_findings) == 1
        assert restored.disputed_findings[0].severity == "high"
        assert restored.disputed_findings[0].issue == "SQL injection"
        assert len(restored.expert_results) == 2
        assert restored.expert_results[0].expert_name == "owasp"

    def test_empty_disputed_findings_roundtrip(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[],
            expert_results=[_expert_result()],
            task_type="architecture",
            file_context="src/",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())
        assert restored.disputed_findings == []

    def test_to_json_is_valid_json(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[_finding(severity="medium", issue="missing rate limit")],
            expert_results=[],
            task_type="migrate",
            file_context="src/api.py",
        )
        parsed = json.loads(bundle.to_json())
        assert parsed["task_type"] == "migrate"
        assert parsed["file_context"] == "src/api.py"
        assert len(parsed["disputed_findings"]) == 1
        assert parsed["disputed_findings"][0]["severity"] == "medium"

    def test_from_json_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            DisputedFindingsBundle.from_json("NOT VALID JSON {{{{")

    def test_multiple_findings_preserved_in_order(self):
        findings = [
            _finding("high", "SQL injection"),
            _finding("medium", "missing rate limit"),
            _finding("low", "verbose logging"),
        ]
        bundle = DisputedFindingsBundle(
            disputed_findings=findings,
            expert_results=[],
            task_type="audit",
            file_context="src/auth.py",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())
        issues = [f.issue for f in restored.disputed_findings]
        assert issues == ["SQL injection", "missing rate limit", "verbose logging"]


class TestDebateResult:
    def test_from_json_resolved_and_unresolved(self):
        raw = json.dumps({
            "resolved_findings": [{"severity": "low", "issue": "minor style issue"}],
            "unresolved_findings": [{"severity": "high", "issue": "SQL injection"}],
            "debate_summary": "experts agreed on style, disagreed on SQL",
        })
        result = DebateResult.from_json(raw)

        assert len(result.resolved_findings) == 1
        assert result.resolved_findings[0].severity == "low"
        assert len(result.unresolved_findings) == 1
        assert result.unresolved_findings[0].issue == "SQL injection"
        assert "SQL" in result.debate_summary

    def test_from_json_empty_fields_use_defaults(self):
        result = DebateResult.from_json(json.dumps({}))
        assert result.resolved_findings == []
        assert result.unresolved_findings == []
        assert result.debate_summary == ""

    def test_from_json_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            DebateResult.from_json("NOT VALID JSON")

    def test_all_resolved_no_unresolved(self):
        raw = json.dumps({
            "resolved_findings": [
                {"severity": "high", "issue": "SQL injection"},
                {"severity": "medium", "issue": "missing rate limit"},
            ],
            "unresolved_findings": [],
            "debate_summary": "full consensus reached",
        })
        result = DebateResult.from_json(raw)
        assert len(result.resolved_findings) == 2
        assert result.unresolved_findings == []

    def test_all_unresolved_no_resolved(self):
        raw = json.dumps({
            "resolved_findings": [],
            "unresolved_findings": [{"severity": "high", "issue": "disputed finding"}],
            "debate_summary": "no consensus reached",
        })
        result = DebateResult.from_json(raw)
        assert result.resolved_findings == []
        assert len(result.unresolved_findings) == 1
