"""
Tests for Adjudicator component.

Tests verdict synthesis and judge evaluation.
"""

import pytest
from unittest.mock import Mock
from typing import Any

from ai_delegate.client import OllamaClient
from ai_delegate.models import TaskConfig, ExpertResult, Verdict, Finding, Tier
from ai_delegate.debate.orchestrator import Adjudicator


class TestAdjudicator:
    """Tests for Adjudicator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock AI client."""
        client = Mock(spec=OllamaClient)
        client.run_json.return_value = {
            "findings": [
                {"severity": "high", "issue": "SQL injection"},
                {"severity": "medium", "issue": "XSS"},
            ],
            "recommendations": ["Use parameterized queries", "Sanitize input"],
            "action_items": ["Fix SQL injection first", "Add XSS protection"],
        }
        return client

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create audit task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def adjudicator(self, mock_client: Any, task_config: TaskConfig) -> Adjudicator:
        """Create Adjudicator instance."""
        return Adjudicator(mock_client, task_config, verbose=False)

    @pytest.fixture
    def debate_results(self) -> list[ExpertResult]:
        """Create sample debate results."""
        return [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                findings=[Finding(severity="medium", issue="CSRF")],
                raw_output='{"findings": [{"severity": "medium", "issue": "CSRF"}]}',
            ),
        ]

    def test_adjudicate_returns_verdict(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Adjudicate should return a Verdict."""
        verdict = adjudicator.adjudicate(debate_results)

        assert isinstance(verdict, Verdict)
        assert verdict.task_type == "audit"
        assert verdict.tier_used == Tier.STANDARD.value

    def test_adjudicate_includes_all_findings(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Adjudicate should receive all expert findings."""
        adjudicator.adjudicate(debate_results)

        # Verify run_json was called with combined findings
        call_args = adjudicator.client.run_json.call_args
        prompt = str(call_args.args[0])

        # Should include both expert outputs
        assert "owasp" in prompt.lower()
        assert "auth" in prompt.lower()

    def test_adjudicate_uses_task_config(
        self, mock_client: Any, task_config: TaskConfig, debate_results: list[ExpertResult]
    ):
        """Adjudicate should use task config for adjudicator role."""
        adjudicator = Adjudicator(mock_client, task_config)

        adjudicator.adjudicate(debate_results)

        # Verify prompt includes adjudicator role from config
        call_args = mock_client.run_json.call_args
        prompt = str(call_args.args[0])
        assert task_config.adjudicator_role in prompt

    def test_run_judge_evaluation_returns_verdict(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Judge evaluation should return enhanced verdict."""
        verdict1 = Verdict(
            task_type="audit",
            consensus_score=0.75,
            tier_used=Tier.DEEP.value,
            raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
        )

        # Mock judge response
        adjudicator.client.run_json.return_value = {
            "selected_verdict": 1,
            "confidence": 90,
            "reasoning": "Verdict 1 is more complete",
        }

        final_verdict = adjudicator.run_judge_evaluation(verdict1, debate_results)

        assert final_verdict.judge_confidence == 90
        assert final_verdict.judge_reasoning == "Verdict 1 is more complete"
        assert final_verdict.tier_used == Tier.DEEP.value

    def test_run_judge_evaluation_selects_verdict_2(
        self, mock_client: Any, task_config: TaskConfig, debate_results: list[ExpertResult]
    ):
        """Judge can select second verdict."""
        adjudicator = Adjudicator(mock_client, task_config)

        verdict1 = Verdict(
            task_type="audit",
            consensus_score=0.75,
            tier_used=Tier.DEEP.value,
            raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
        )

        # Mock judge selects verdict 2
        mock_client.run_json.return_value = {
            "selected_verdict": 2,
            "confidence": 85,
            "reasoning": "Verdict 2 has better prioritization",
        }

        final_verdict = adjudicator.run_judge_evaluation(verdict1, debate_results)

        # Should use verdict 2's output
        assert final_verdict.judge_confidence == 85

    def test_build_findings_includes_all_results(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """_build_findings should include all non-error results."""
        findings_str = adjudicator._build_findings(debate_results)

        assert "owasp" in findings_str
        assert "auth" in findings_str

    def test_build_findings_excludes_error_results(
        self, adjudicator: Adjudicator
    ):
        """_build_findings should exclude results with errors."""
        results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                error="API timeout",
            ),
        ]

        findings_str = adjudicator._build_findings(results)

        assert "owasp" in findings_str
        assert "auth" not in findings_str

    def test_build_findings_with_exclude(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """_build_findings can exclude specific expert."""
        findings_str = adjudicator._build_findings(debate_results, exclude="owasp")

        assert "owasp" not in findings_str
        assert "auth" in findings_str


class TestAdjudicatorPromptConstruction:
    """Tests for prompt construction in Adjudicator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def adjudicator(self, mock_client: Any, task_config: TaskConfig) -> Adjudicator:
        """Create Adjudicator with mock."""
        return Adjudicator(mock_client, task_config)

    @pytest.fixture
    def debate_results(self) -> list[ExpertResult]:
        """Create sample debate results."""
        return [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="security",
                findings=[Finding(severity="medium", issue="CSRF")],
                raw_output='{"findings": [{"severity": "medium", "issue": "CSRF"}]}',
            ),
        ]

    def test_adjudicate_includes_output_format(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Adjudicate prompt should include output format."""
        mock_client = adjudicator.client
        mock_client.run_json.return_value = {"findings": []}  # Ensure proper JSON response

        adjudicator.adjudicate(debate_results)

        call_args = mock_client.run_json.call_args
        prompt_text = str(call_args.args[0])

        # Check that the prompt includes the adjudicator role from task config
        assert "critical" in prompt_text.lower() or "findings" in prompt_text.lower()

    def test_judge_prompt_includes_both_verdicts(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Judge prompt should compare both verdicts."""
        mock_client = adjudicator.client
        verdict1 = Verdict(
            task_type="audit",
            consensus_score=0.75,
            tier_used=Tier.DEEP.value,
            raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
        )

        # First call for second adjudication, second for judge
        mock_client.run_json.return_value = {
            "selected_verdict": 1,
            "confidence": 90,
            "reasoning": "Test",
        }

        adjudicator.run_judge_evaluation(verdict1, debate_results)

        # Verify judge prompt was called
        calls = mock_client.run_json.call_args_list
        assert len(calls) == 2  # Second adjudication + judge

        judge_prompt = str(calls[1].args[0])
        assert "Verdict 1" in judge_prompt
        assert "Verdict 2" in judge_prompt
        assert "COMPLETENESS" in judge_prompt
        assert "CONSENSUS_ACCURACY" in judge_prompt


class TestAdjudicatorEdgeCases:
    """Edge case tests for Adjudicator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def adjudicator(self, mock_client: Any, task_config: TaskConfig) -> Adjudicator:
        """Create Adjudicator."""
        return Adjudicator(mock_client, task_config)

    @pytest.fixture
    def debate_results(self) -> list[ExpertResult]:
        """Create sample debate results."""
        return [
            ExpertResult(
                expert_name="owasp",
                expert_type="security",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
            ),
        ]

    def test_adjudicate_with_empty_results(
        self, adjudicator: Adjudicator
    ):
        """Adjudicate should handle empty results."""
        adjudicator.client.run_json.return_value = {"findings": []}

        verdict = adjudicator.adjudicate([])

        assert verdict is not None
        assert verdict.task_type == "audit"

    def test_adjudicate_with_all_errors(
        self, adjudicator: Adjudicator
    ):
        """Adjudicate should handle all error results."""
        mock_client = adjudicator.client
        mock_client.run_json.return_value = {"findings": []}  # Valid JSON response

        results = [
            ExpertResult(expert_name="expert1", expert_type="security", error="Failed"),
            ExpertResult(expert_name="expert2", expert_type="security", error="Failed"),
        ]

        verdict = adjudicator.adjudicate(results)

        assert verdict is not None
        assert verdict.task_type == "audit"

    def test_judge_handles_missing_confidence(
        self, adjudicator: Adjudicator, debate_results: list[ExpertResult]
    ):
        """Judge should handle missing confidence field."""
        mock_client = adjudicator.client
        mock_client.run_json.return_value = {
            "selected_verdict": 1,
            # Missing confidence
            "reasoning": "Test reasoning",
        }

        verdict1 = Verdict(
            task_type="audit",
            consensus_score=0.75,
            tier_used=Tier.DEEP.value,
            raw_output='{"findings": []}',
        )

        final_verdict = adjudicator.run_judge_evaluation(verdict1, debate_results)

        # Should default confidence
        assert final_verdict.judge_confidence == 50  # Default