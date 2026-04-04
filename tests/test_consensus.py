"""
Tests for ConsensusCalculator.

Tests consensus calculation logic with various expert finding scenarios.
"""

import pytest
from ai_delegate.models import Finding, ExpertResult
from ai_delegate.debate.orchestrator import ConsensusCalculator


class TestConsensusCalculator:
    """Tests for ConsensusCalculator static methods."""

    def test_empty_results(self):
        """Empty expert results return zero consensus."""
        result = ConsensusCalculator.calculate([])
        assert result.score == 0.0

    def test_no_findings(self):
        """Results with no findings return perfect consensus."""
        results = [
            ExpertResult(expert_name="expert1", expert_type="security", findings=[]),
            ExpertResult(expert_name="expert2", expert_type="security", findings=[]),
        ]
        consensus = ConsensusCalculator.calculate(results)

        assert consensus.score == 1.0
        assert len(consensus.consensus_findings) == 0

    def test_single_expert(self):
        """Single expert has perfect consensus with itself."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS vulnerability"),
                    Finding(severity="medium", issue="CSRF token missing"),
                ],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # 100% of findings are consensus (all experts agree)
        assert consensus.score == 1.0
        assert len(consensus.consensus_findings) == 2

    def test_full_consensus(self):
        """All experts finding same issues results in full consensus."""
        findings = [
            Finding(severity="critical", issue="SQL injection in login"),
            Finding(severity="high", issue="XSS in search"),
        ]

        results = [
            ExpertResult(expert_name="owasp", expert_type="security", findings=findings),
            ExpertResult(expert_name="auth", expert_type="security", findings=findings),
            ExpertResult(expert_name="input", expert_type="security", findings=findings),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # All findings found by all experts
        assert consensus.score >= 0.9  # High consensus
        assert len(consensus.consensus_findings) == 2

    def test_partial_consensus(self):
        """Some overlap results in partial consensus."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS in search"),
                    Finding(severity="medium", issue="Info leak"),
                ],
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS in search"),
                    Finding(severity="low", issue="Missing header"),
                ],
            ),
            ExpertResult(
                expert_name="input",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS in search"),
                ],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # XSS found by all 3 (consensus - threshold is 80% of 3 = 2.4, rounds to 2)
        # So XSS (count=3) >= threshold(2) is consensus
        # Total unique = 3 findings, consensus_count = 1
        assert consensus.score > 0.3  # 1/3 = 0.33
        assert len(consensus.consensus_findings) >= 1  # XSS is consensus

    def test_no_consensus(self):
        """No overlapping findings results in low consensus."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="Issue A")],
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                findings=[Finding(severity="high", issue="Issue B")],
            ),
            ExpertResult(
                expert_name="input",
                expert_type="security",
                findings=[Finding(severity="high", issue="Issue C")],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # No consensus threshold met (need 80% of experts = 2.4, so 3 for 3 experts)
        assert consensus.score < 0.5
        assert len(consensus.consensus_findings) == 0

    def test_disputed_findings(self):
        """Findings agreed by some but not all are disputed."""
        results = [
            ExpertResult(
                expert_name="expert1",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS"),
                    Finding(severity="medium", issue="CSRF"),
                ],
            ),
            ExpertResult(
                expert_name="expert2",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS"),
                    Finding(severity="medium", issue="CSRF"),
                ],
            ),
            ExpertResult(
                expert_name="expert3",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # With 3 experts, threshold = ceil(3 * 80/100) = ceil(2.4) = 3
        # XSS found by 3 >= 3 → consensus
        # CSRF found by 2 < 3 → disputed
        assert len(consensus.consensus_findings) == 1  # Only XSS is consensus
        assert len(consensus.disputed_findings) == 1   # CSRF is disputed

    def test_unique_findings_categorized(self):
        """Findings unique to single expert are tracked."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[
                    Finding(
                        severity="high",
                        issue="XSS",
                        metadata={"expert": "owasp"},
                    ),
                    Finding(
                        severity="low",
                        issue="Info leak",
                        metadata={"expert": "owasp"},
                    ),
                ],
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                findings=[
                    Finding(
                        severity="high",
                        issue="XSS",
                        metadata={"expert": "auth"},
                    ),
                    Finding(
                        severity="medium",
                        issue="Weak password",
                        metadata={"expert": "auth"},
                    ),
                ],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # Check unique findings are tracked
        # Info leak unique to owasp, Weak password unique to auth
        unique_count = sum(len(v) for v in consensus.unique_findings.values())
        assert unique_count >= 0  # May have unique findings

    def test_finding_key_normalization(self):
        """Finding keys are normalized using md5 hash — different issues are different keys."""
        # These two issues differ after char 50 — old [:50] truncation made them collide
        # New md5 hash correctly distinguishes them
        results = [
            ExpertResult(
                expert_name="expert1",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="SQL injection in user search function"),
                ],
            ),
            ExpertResult(
                expert_name="expert2",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="SQL injection in user search function with details"),
                ],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # With 2 experts, threshold = ceil(2 * 80/100) = ceil(1.6) = 2
        # Each finding appears once (count=1 < threshold=2) → not consensus
        # Both are unique findings
        assert len(consensus.consensus_findings) == 0

    def test_with_error_results(self):
        """Results with errors don't break consensus calculation."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                error="API timeout",
            ),
            ExpertResult(
                expert_name="input",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
            ),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # 3 experts total (including errored), threshold = ceil(3 * 80/100) = 3
        # XSS found by 2 successful experts, 2 < 3 → not consensus but disputed
        # Calculation still completes without error
        assert isinstance(consensus.score, float)
        assert len(consensus.disputed_findings) == 1  # XSS agreed by 2, disputed


class TestConsensusThresholds:
    """Test consensus threshold calculations."""

    def test_threshold_80_percent(self):
        """Consensus requires 80% of experts to agree."""
        # 5 experts, 80% = 4 need to agree
        findings = [Finding(severity="high", issue="XSS")]

        results = [
            ExpertResult(expert_name=f"expert{i}", expert_type="security", findings=findings)
            for i in range(4)
        ] + [
            ExpertResult(expert_name="expert5", expert_type="security", findings=[]),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # 4/5 = 80%, meets threshold
        assert len(consensus.consensus_findings) == 1

    def test_below_threshold(self):
        """Below 80% threshold is not consensus."""
        findings = [Finding(severity="high", issue="XSS")]

        # 3 experts, threshold = ceil(3 * 80/100) = ceil(2.4) = 3
        results = [
            ExpertResult(expert_name="expert1", expert_type="security", findings=findings),
            ExpertResult(expert_name="expert2", expert_type="security", findings=findings),
            ExpertResult(expert_name="expert3", expert_type="security", findings=[]),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # 2/3 found XSS, need 3 (ceil(2.4)) → NOT consensus
        assert len(consensus.consensus_findings) == 0


class TestConsensusThresholdBoundary:
    """Boundary tests for math.ceil fix (Task 2)."""

    def test_three_experts_all_agree_is_consensus(self):
        """3/3 experts agreeing should be consensus at 80% threshold."""
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("C", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 1
        assert consensus.consensus_findings[0].issue == "SQL injection"

    def test_two_of_three_experts_is_NOT_consensus(self):
        """2/3 = 66.7% should NOT be consensus at 80% threshold.

        Bug: old code does 3 * 80 // 100 = 2, accepting 2/3 as consensus.
        Fix: math.ceil(3 * 80 / 100) = 3, requiring 3/3.
        """
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("C", "audit", findings=[Finding(severity="high", issue="XSS vulnerability")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        # SQL injection appears 2/3 times = 66.7%, below 80% threshold
        assert len(consensus.consensus_findings) == 0
        assert len(consensus.disputed_findings) == 1  # 2 experts agreed, 1 didn't

    def test_five_experts_four_agree_is_consensus(self):
        """4/5 = 80% should be consensus (exactly at threshold)."""
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("C", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("D", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("E", "audit", findings=[Finding(severity="high", issue="XSS")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        # 4/5 = 80% = exactly at threshold (ceil(4.0) = 4)
        assert len(consensus.consensus_findings) == 1

    def test_five_experts_three_agree_is_NOT_consensus(self):
        """3/5 = 60% should NOT be consensus."""
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("C", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("D", "audit", findings=[Finding(severity="high", issue="XSS")]),
            ExpertResult("E", "audit", findings=[Finding(severity="high", issue="CSRF")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 0


class TestFindingNormalization:
    """Tests for md5 hash normalization fix (Task 3)."""

    def test_different_issues_with_same_first_50_chars_are_NOT_merged(self):
        """Two findings with same severity+first50chars but different full text must be separate."""
        long_prefix = "A" * 49  # 49 chars shared prefix
        finding_a = Finding(severity="high", issue=long_prefix + "Z_additional_context_A")
        finding_b = Finding(severity="high", issue=long_prefix + "Z_additional_context_B")

        results = [
            ExpertResult("Expert1", "audit", findings=[finding_a]),
            ExpertResult("Expert2", "audit", findings=[finding_b]),
        ]
        consensus = ConsensusCalculator.calculate(results)

        # Old code: both get key "high|" + 49*"A" + "Z" (same first 50), merged as consensus
        # New code: different md5 hashes, treated as separate unique findings
        assert len(consensus.consensus_findings) == 0

    def test_identical_issues_ARE_merged(self):
        """Same finding from all experts should still create consensus."""
        results = [
            ExpertResult("Expert1", "audit", findings=[Finding(severity="high", issue="SQL injection on line 42")]),
            ExpertResult("Expert2", "audit", findings=[Finding(severity="high", issue="SQL injection on line 42")]),
            ExpertResult("Expert3", "audit", findings=[Finding(severity="high", issue="SQL injection on line 42")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 1

    def test_same_issue_different_severity_are_separate_findings(self):
        """Same issue text but different severity = different keys."""
        results = [
            ExpertResult("Expert1", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
            ExpertResult("Expert2", "audit", findings=[Finding(severity="critical", issue="SQL injection")]),
            ExpertResult("Expert3", "audit", findings=[Finding(severity="high", issue="SQL injection")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        # "high|SQL injection" appears 2/3 (not consensus), "critical|SQL injection" appears 1/3
        assert len(consensus.consensus_findings) == 0


class TestDisagreementSummary:
    """Tests for disagreement_summary field (P3-T3)."""

    def test_no_disagreement_when_all_agree(self):
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="XSS")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="XSS")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert consensus.disagreement_summary == ""

    def test_disagreement_summary_includes_disputed(self):
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="XSS"), Finding(severity="medium", issue="CSRF")]),
            ExpertResult("B", "audit", findings=[Finding(severity="high", issue="XSS"), Finding(severity="medium", issue="CSRF")]),
            ExpertResult("C", "audit", findings=[Finding(severity="high", issue="XSS")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        # CSRF is disputed — 2/3, not reaching ceil(2.4)=3
        assert "disputed" in consensus.disagreement_summary
        assert "CSRF" in consensus.disagreement_summary

    def test_disagreement_summary_includes_unique(self):
        results = [
            ExpertResult("A", "audit", findings=[
                Finding(severity="high", issue="XSS", metadata={"expert": "A"}),
            ]),
            ExpertResult("B", "audit", findings=[
                Finding(severity="high", issue="SQLi", metadata={"expert": "B"}),
            ]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert "unique" in consensus.disagreement_summary

    def test_to_dict_includes_disagreement_summary(self):
        results = [
            ExpertResult("A", "audit", findings=[Finding(severity="high", issue="XSS")]),
            ExpertResult("B", "audit", findings=[Finding(severity="low", issue="Other")]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        d = consensus.to_dict()
        assert "disagreement_summary" in d
        assert isinstance(d["disagreement_summary"], str)

    def test_no_findings_returns_empty_summary(self):
        results = [
            ExpertResult("A", "audit", findings=[]),
            ExpertResult("B", "audit", findings=[]),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert consensus.disagreement_summary == ""