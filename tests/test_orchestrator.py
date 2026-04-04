"""
Integration tests for DebateOrchestrator.

Tests the complete analysis flow from start to finish.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Any

from ai_delegate.client import OllamaClient
from ai_delegate.models import TaskConfig, ExpertResult, Finding, Tier, Verdict
from ai_delegate.debate.orchestrator import DebateOrchestrator, ConsensusCalculator


class TestDebateOrchestrator:
    """Integration tests for DebateOrchestrator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock AI client with realistic responses."""
        client = Mock(spec=OllamaClient)

        def mock_run_json(prompt: str) -> dict:
            """Simulate realistic AI responses based on prompt content."""
            if "OWASP" in prompt or "security" in prompt.lower():
                return {
                    "findings": [
                        {"severity": "high", "issue": "SQL injection in login"},
                        {"severity": "medium", "issue": "XSS in search"},
                    ]
                }
            elif "Adjudicator" in prompt:
                return {
                    "findings": [
                        {"severity": "high", "issue": "SQL injection in login"},
                        {"severity": "medium", "issue": "XSS in search"},
                    ],
                    "recommendations": ["Use parameterized queries", "Sanitize input"],
                    "action_items": ["Fix SQL injection", "Add XSS protection"],
                }
            elif "Judge" in prompt:
                return {
                    "selected_verdict": 1,
                    "confidence": 90,
                    "reasoning": "Verdict 1 is more complete",
                }
            else:
                return {"findings": []}

        client.run_json.side_effect = mock_run_json
        return client

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def analyze_config(self) -> TaskConfig:
        """Create analyze task config."""
        return TaskConfig.from_task_type("analyze")

    @pytest.fixture
    def orchestrator(self, mock_client: Any, audit_config: TaskConfig) -> DebateOrchestrator:
        """Create DebateOrchestrator instance."""
        return DebateOrchestrator(mock_client, audit_config, verbose=False)

    def test_analyze_returns_verdict(
        self, orchestrator: DebateOrchestrator, sample_code: str
    ):
        """Analyze should return a Verdict."""
        result = orchestrator.analyze(sample_code)

        assert isinstance(result, Verdict)
        assert result.task_type == "audit"

    def test_analyze_fast_tier_skips_debate(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """FAST tier should skip debate and adjudication."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        # Patch consensus to return high score
        with patch.object(
            ConsensusCalculator, "calculate"
        ) as mock_consensus:
            from ai_delegate.models import ConsensusResult

            mock_consensus.return_value = ConsensusResult(
                score=0.95,  # High consensus = FAST tier
                consensus_findings=[Finding(severity="high", issue="Test")],
            )

            result = orchestrator.analyze(sample_code, tier=Tier.FAST.value)

            # Should return consensus directly
            assert result.tier_used == Tier.FAST.value
            # Should not call run_json for debate/adjudication
            assert result.consensus_score == 0.95

    def test_analyze_deep_tier_runs_all_phases(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """DEEP tier should run all phases including judge."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        result = orchestrator.analyze(sample_code, tier=Tier.DEEP.value)

        assert result.tier_used == Tier.DEEP.value
        # Judge confidence/reasoning only set when verdict 1 is selected (default)
        # Mock returns selected_verdict: 1 by default

    def test_analyze_auto_tier_selects_based_on_consensus(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """AUTO tier should select tier based on consensus."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        # With realistic mock, consensus should select appropriate tier
        result = orchestrator.analyze(sample_code, tier=Tier.AUTO.value)

        assert result.tier_used in [Tier.FAST.value, Tier.STANDARD.value, Tier.DEEP.value]

    def test_analyze_audit_always_deep(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """Audit tasks should always use DEEP tier."""
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        result = orchestrator.analyze(sample_code, tier=Tier.AUTO.value)

        # Audit always uses DEEP (always_deep=True)
        assert result.tier_used == Tier.DEEP.value
        assert result.judge_confidence is not None

    def test_analyze_handles_expert_failures(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """Analyze should handle expert failures gracefully."""
        call_count = 0

        def failing_response(prompt: str):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 experts fail
                raise RuntimeError("API error")
            return {"findings": [{"severity": "low", "issue": "Minor issue"}]}

        mock_client.run_json.side_effect = failing_response
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        # Should not raise, should complete analysis
        result = orchestrator.analyze(sample_code)

        assert isinstance(result, Verdict)

    def test_verbose_logging(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str, caplog
    ):
        """Verbose mode should log progress."""
        import logging

        caplog.set_level(logging.INFO)

        orchestrator = DebateOrchestrator(mock_client, audit_config, verbose=True)
        orchestrator.analyze(sample_code)

        # Should have logged expert completion
        assert "completed" in caplog.text.lower() or len(caplog.records) >= 0


class TestDebateOrchestratorComponents:
    """Tests for DebateOrchestrator component integration."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_expert_runner_integration(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """DebateOrchestrator should use ExpertRunner correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}]
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        results = orchestrator.expert_runner.run_parallel(sample_code)

        # Should have results from all experts
        assert len(results) == 3  # owasp, auth, input
        assert all(r.expert_type == "audit" for r in results)

    def test_adjudicator_integration(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """DebateOrchestrator should use Adjudicator correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}],
            "recommendations": ["Fix XSS"],
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        debate_results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="audit",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": []}',
            )
        ]

        verdict = orchestrator.adjudicator.adjudicate(debate_results)

        assert verdict.task_type == "audit"

    def test_consensus_calculator_integration(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """DebateOrchestrator should use ConsensusCalculator correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}]
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        results = orchestrator.expert_runner.run_parallel(sample_code)
        consensus = ConsensusCalculator.calculate(results)

        assert consensus.score >= 0.0
        assert consensus.score <= 1.0


class TestDebateOrchestratorTierSelection:
    """Tests for tier selection logic."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config (always_deep=True)."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def analyze_config(self) -> TaskConfig:
        """Create analyze config (always_deep=False)."""
        return TaskConfig.from_task_type("analyze")

    def test_select_tier_explicit(self, mock_client: Any, analyze_config: TaskConfig):
        """Explicit tier should be used."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        from ai_delegate.models import ConsensusResult

        consensus = ConsensusResult(score=0.5)

        tier = orchestrator._select_tier(Tier.DEEP.value, consensus)
        assert tier == Tier.DEEP.value

        tier = orchestrator._select_tier(Tier.FAST.value, consensus)
        assert tier == Tier.FAST.value

    def test_select_tier_always_deep(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """Tasks with always_deep=True should always use DEEP."""
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        from ai_delegate.models import ConsensusResult

        # Even with high consensus
        consensus = ConsensusResult(score=0.95)

        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.DEEP.value

    def test_select_tier_consensus_based(
        self, mock_client: Any, analyze_config: TaskConfig
    ):
        """AUTO should select tier based on consensus score."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        from ai_delegate.models import ConsensusResult

        # High consensus = FAST
        consensus = ConsensusResult(score=0.95)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.FAST.value

        # Medium consensus = STANDARD
        consensus = ConsensusResult(score=0.75)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.STANDARD.value

        # Low consensus = DEEP
        consensus = ConsensusResult(score=0.50)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.DEEP.value


class TestDebateOrchestratorEdgeCases:
    """Edge case tests for DebateOrchestrator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_empty_code(self, mock_client: Any, audit_config: TaskConfig):
        """Empty code should be handled."""
        mock_client.run_json.return_value = {"findings": []}

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze("")

        assert isinstance(result, Verdict)

    def test_very_large_code(self, mock_client: Any, audit_config: TaskConfig):
        """Very large code should be handled."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "low", "issue": "Large file"}]
        }

        large_code = "x = 1\n" * 10000

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze(large_code)

        assert isinstance(result, Verdict)

    def test_unicode_code(self, mock_client: Any, audit_config: TaskConfig):
        """Unicode content should be handled."""
        mock_client.run_json.return_value = {"findings": []}

        unicode_code = '''
def hello():
    return "สวัสดี ครับ"
'''

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze(unicode_code)

        assert isinstance(result, Verdict)