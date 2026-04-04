"""Tests for ConsensusResult disagreement detail (P3-T3 plan spec)."""
import pytest
from ai_delegate.models import Finding, ExpertResult, ConsensusResult
from ai_delegate.debate.orchestrator import ConsensusCalculator


def make_expert_result(name: str, findings: list) -> ExpertResult:
    return ExpertResult(expert_name=name, expert_type="security", findings=findings)


class TestConsensusDetail:
    def test_disagreement_detail_populated(self):
        """Unique findings include which expert raised them."""
        f1 = Finding(severity="high", issue="SQL injection in login")
        f2 = Finding(severity="medium", issue="Missing CSRF protection")
        f3 = Finding(severity="low", issue="Verbose error messages")

        results = [
            make_expert_result("OWASP Expert", [f1, f2]),
            make_expert_result("Auth Expert", [f1, f3]),
            make_expert_result("Input Expert", [f1]),
        ]

        consensus = ConsensusCalculator.calculate(results)

        # f1 raised by all 3 = consensus
        assert len(consensus.consensus_findings) == 1
        # f2 raised by OWASP Expert only = unique
        assert "OWASP Expert" in consensus.unique_findings
        assert any(f.issue == "Missing CSRF protection" for f in consensus.unique_findings["OWASP Expert"])

    def test_disagreement_reason_in_verdict(self):
        """ConsensusResult.disagreement_summary describes what was disputed."""
        f1 = Finding(severity="high", issue="SQL injection in login")
        f2 = Finding(severity="medium", issue="Missing CSRF protection")

        results = [
            make_expert_result("Expert A", [f1, f2]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]

        consensus = ConsensusCalculator.calculate(results)
        summary = consensus.disagreement_summary

        assert "Expert A" in summary
        assert "Missing CSRF protection" in summary

    def test_full_consensus_has_empty_disagreement(self):
        f1 = Finding(severity="high", issue="SQL injection")
        results = [
            make_expert_result("Expert A", [f1]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert consensus.disagreement_summary == ""

    def test_consensus_result_to_dict_includes_disagreement(self):
        f1 = Finding(severity="high", issue="SQL injection")
        f2 = Finding(severity="low", issue="Minor issue")
        results = [
            make_expert_result("Expert A", [f1, f2]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        d = consensus.to_dict()
        assert "disagreement_summary" in d
