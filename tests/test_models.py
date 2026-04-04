"""
Unit tests for data models.

Tests behavior, not implementation details.
"""

import pytest
from ai_delegate.models import (
    Finding,
    ExpertResult,
    ConsensusResult,
    Verdict,
    TaskConfig,
    Tier,
    Structure,
)


class TestFinding:
    """Tests for Finding dataclass."""

    def test_to_dict_minimal(self):
        """Finding with only required fields serializes correctly."""
        finding = Finding(severity="high", issue="SQL injection found")
        result = finding.to_dict()

        assert result == {"severity": "high", "issue": "SQL injection found"}

    def test_to_dict_all_fields(self):
        """Finding with all fields serializes correctly."""
        finding = Finding(
            severity="critical",
            issue="Hardcoded secret",
            location="auth.py:42",
            recommendation="Use environment variables",
            cwe="CWE-798",
            impact="Credential exposure",
            metadata={"confidence": 0.95},
        )
        result = finding.to_dict()

        assert result["severity"] == "critical"
        assert result["issue"] == "Hardcoded secret"
        assert result["location"] == "auth.py:42"
        assert result["recommendation"] == "Use environment variables"
        assert result["cwe"] == "CWE-798"
        assert result["impact"] == "Credential exposure"
        assert result["confidence"] == 0.95

    def test_from_dict_minimal(self):
        """Finding deserializes from minimal dict."""
        data = {"severity": "low", "issue": "Missing logging"}
        finding = Finding.from_dict(data)

        assert finding.severity == "low"
        assert finding.issue == "Missing logging"
        assert finding.location is None
        assert finding.recommendation is None

    def test_from_dict_with_extra_fields(self):
        """Extra fields go into metadata."""
        data = {
            "severity": "medium",
            "issue": "N+1 query",
            "confidence": 0.8,
            "source": "static_analysis",
        }
        finding = Finding.from_dict(data)

        assert finding.severity == "medium"
        assert finding.issue == "N+1 query"
        assert finding.metadata["confidence"] == 0.8
        assert finding.metadata["source"] == "static_analysis"

    def test_roundtrip(self):
        """Finding survives serialization roundtrip."""
        original = Finding(
            severity="high",
            issue="XSS vulnerability",
            location="templates/index.html:15",
            recommendation="Sanitize user input",
        )
        data = original.to_dict()
        restored = Finding.from_dict(data)

        assert restored.severity == original.severity
        assert restored.issue == original.issue
        assert restored.location == original.location
        assert restored.recommendation == original.recommendation


class TestExpertResult:
    """Tests for ExpertResult dataclass."""

    def test_success_property_no_error(self):
        """Result with no error is successful."""
        result = ExpertResult(
            expert_name="owasp",
            expert_type="security",
            findings=[Finding(severity="high", issue="XSS")],
        )
        assert result.success is True

    def test_success_property_with_error(self):
        """Result with error is not successful."""
        result = ExpertResult(
            expert_name="owasp",
            expert_type="security",
            error="API timeout",
        )
        assert result.success is False

    def test_parsed_output_caches(self):
        """parsed_output caches JSON parsing."""
        result = ExpertResult(
            expert_name="test",
            expert_type="security",
            raw_output='{"findings": [{"severity": "high", "issue": "test"}]}',
        )

        # First access parses
        parsed = result.parsed_output
        assert parsed["findings"][0]["severity"] == "high"

        # Second access uses cache
        assert result._parsed_output is not None
        parsed2 = result.parsed_output
        assert parsed is parsed2  # Same object

    def test_parsed_output_empty_on_no_raw(self):
        """parsed_output returns empty dict when no raw_output."""
        result = ExpertResult(
            expert_name="test",
            expert_type="security",
        )
        assert result.parsed_output == {}

    def test_parsed_output_handles_invalid_json(self):
        """parsed_output handles invalid JSON gracefully."""
        result = ExpertResult(
            expert_name="test",
            expert_type="security",
            raw_output="not valid json",
        )
        assert result.parsed_output == {}

    def test_to_dict(self):
        """ExpertResult serializes correctly."""
        result = ExpertResult(
            expert_name="owasp",
            expert_type="security",
            findings=[Finding(severity="high", issue="XSS")],
            raw_output='{"test": true}',
            duration_ms=150.5,
        )
        data = result.to_dict()

        assert data["expert_name"] == "owasp"
        assert data["expert_type"] == "security"
        assert len(data["findings"]) == 1
        assert data["duration_ms"] == 150.5


class TestConsensusResult:
    """Tests for ConsensusResult dataclass."""

    def test_percentage_conversion(self):
        """score converts to percentage correctly."""
        result = ConsensusResult(score=0.85)
        assert result.percentage == 85.0

    def test_tier_fast(self):
        """score >= 0.90 maps to FAST tier."""
        result = ConsensusResult(score=0.92)
        assert result.tier == Tier.FAST.value

    def test_tier_standard(self):
        """score >= 0.70 and < 0.90 maps to STANDARD tier."""
        result = ConsensusResult(score=0.75)
        assert result.tier == Tier.STANDARD.value

    def test_tier_deep(self):
        """score < 0.70 maps to DEEP tier."""
        result = ConsensusResult(score=0.65)
        assert result.tier == Tier.DEEP.value

    def test_to_dict(self):
        """ConsensusResult serializes correctly."""
        result = ConsensusResult(
            score=0.80,
            consensus_findings=[Finding(severity="high", issue="XSS")],
            disputed_findings=[Finding(severity="medium", issue="CSRF")],
            unique_findings={"owasp": [Finding(severity="low", issue="Info leak")]},
        )
        data = result.to_dict()

        assert data["score"] == 0.80
        assert data["percentage"] == 80.0
        assert data["tier"] == Tier.STANDARD.value
        assert len(data["consensus_findings"]) == 1


class TestVerdict:
    """Tests for Verdict dataclass."""

    def test_to_dict_basic(self):
        """Verdict serializes with required fields."""
        verdict = Verdict(
            task_type="audit",
            consensus_score=0.85,
            tier_used=Tier.STANDARD.value,
        )
        data = verdict.to_dict()

        assert data["task_type"] == "audit"
        assert data["consensus_score"] == 0.85
        assert data["tier_used"] == "standard"
        assert "judge_confidence" not in data
        assert "judge_reasoning" not in data

    def test_to_dict_with_judge(self):
        """Verdict includes judge fields when set."""
        verdict = Verdict(
            task_type="audit",
            consensus_score=0.65,
            tier_used=Tier.DEEP.value,
            judge_confidence=90,
            judge_reasoning="Verdict 1 is more complete",
        )
        data = verdict.to_dict()

        assert data["judge_confidence"] == 90
        assert data["judge_reasoning"] == "Verdict 1 is more complete"


class TestTaskConfig:
    """Tests for TaskConfig dataclass."""

    def test_from_task_type_audit(self):
        """Audit task creates correct config."""
        config = TaskConfig.from_task_type("audit")

        assert config.task_type == "audit"
        assert config.display_name == "SECURITY AUDIT"
        assert "owasp" in config.experts
        assert config.always_deep is True

    def test_from_task_type_analyze(self):
        """Analyze task creates correct config."""
        config = TaskConfig.from_task_type("analyze")

        assert config.task_type == "analyze"
        assert config.display_name == "PERFORMANCE ANALYSIS"
        assert "complexity" in config.experts
        assert config.always_deep is False

    def test_from_task_type_invalid(self):
        """Invalid task type raises ValueError."""
        with pytest.raises(ValueError, match="Unknown task type"):
            TaskConfig.from_task_type("invalid")


class TestTier:
    """Tests for Tier enum."""

    def test_tier_values(self):
        """Tier has expected values."""
        assert Tier.FAST.value == "fast"
        assert Tier.STANDARD.value == "standard"
        assert Tier.DEEP.value == "deep"
        assert Tier.AUTO.value == "auto"


class TestStructure:
    """Tests for Structure enum."""

    def test_structure_values(self):
        """Structure has expected values."""
        assert Structure.FLAT.value == "flat"
        assert Structure.HIERARCHICAL.value == "hierarchical"
        assert Structure.MATRIX.value == "matrix"
        assert Structure.TEAM_BASED.value == "team-based"