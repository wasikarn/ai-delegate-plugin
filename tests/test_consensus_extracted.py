"""Tests for ai_delegate/consensus.py — extracted ConsensusCalculator."""
import pytest
from ai_delegate.consensus import ConsensusCalculator, normalize_finding
from ai_delegate.models import ExpertResult, Finding, ConsensusResult


class TestConsensusCalculatorEmpty:
    def test_empty_list_returns_zero_score(self):
        result = ConsensusCalculator.calculate([])
        assert result.score == 0.0
        assert result.consensus_findings == []
        assert result.disputed_findings == []
        assert result.unique_findings == {}

    def test_all_empty_findings_returns_perfect_score(self):
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[]),
        ]
        assert ConsensusCalculator.calculate(results).score == 1.0


class TestConsensusCalculatorAgreement:
    def test_full_agreement_returns_score_one(self):
        f = Finding(severity="high", issue="XSS")
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[f]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert result.score == 1.0
        assert len(result.consensus_findings) == 1

    def test_no_agreement_returns_zero_score(self):
        results = [
            ExpertResult(expert_name="e1", expert_type="security",
                         findings=[Finding(severity="high", issue="XSS")]),
            ExpertResult(expert_name="e2", expert_type="security",
                         findings=[Finding(severity="medium", issue="CSRF")]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert result.score == 0.0
        assert len(result.disputed_findings) == 0
        assert len(result.unique_findings) == 2  # both are unique

    def test_disputed_finding_two_of_three_experts(self):
        f = Finding(severity="high", issue="SQL injection")
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e3", expert_type="security",
                         findings=[Finding(severity="low", issue="info leak")]),
        ]
        # threshold = ceil(3 * 80/100) = ceil(2.4) = 3 → SQL injection appears 2x = disputed
        result = ConsensusCalculator.calculate(results)
        assert len(result.disputed_findings) == 1
        assert result.disputed_findings[0].issue == "SQL injection"

    def test_case_insensitive_deduplication(self):
        f1 = Finding(severity="HIGH", issue="XSS")
        f2 = Finding(severity="high", issue="xss")
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[f1]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[f2]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert result.score == 1.0
        assert len(result.consensus_findings) == 1

    def test_unique_finding_keyed_by_expert_name(self):
        results = [
            ExpertResult(expert_name="owasp", expert_type="security",
                         findings=[Finding(severity="high", issue="only owasp finds this")]),
            ExpertResult(expert_name="auth", expert_type="security", findings=[]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert "owasp" in result.unique_findings
        assert result.unique_findings["owasp"][0].issue == "only owasp finds this"


class TestNormalizeFinding:
    def test_canonical_format_passthrough(self):
        raw = {"severity": "high", "issue": "XSS", "recommendation": "sanitize"}
        f = normalize_finding(raw)
        assert f.severity == "high"
        assert f.issue == "XSS"
        assert f.recommendation == "sanitize"

    def test_domain_format_title_mapped_to_issue(self):
        raw = {"severity": "high", "title": "SQL injection", "category": "OWASP-A03",
               "file": "db.py", "line": 42, "recommendation": "use params"}
        f = normalize_finding(raw)
        assert f.issue == "SQL injection"
        assert f.location == "db.py:42"

    def test_missing_severity_defaults_to_medium(self):
        raw = {"issue": "unknown risk"}
        f = normalize_finding(raw)
        assert f.severity == "medium"

    def test_missing_issue_uses_empty_string(self):
        raw = {"severity": "low"}
        f = normalize_finding(raw)
        assert f.issue == ""

    def test_title_takes_precedence_over_issue(self):
        raw = {"severity": "high", "title": "SQL injection", "issue": "XSS"}
        f = normalize_finding(raw)
        assert f.issue == "SQL injection"  # title wins
