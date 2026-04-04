"""Tests for ForcedFindingValidator."""
from unittest.mock import MagicMock, patch
from ai_delegate.debate.orchestrator import DebateOrchestrator, ForcedFindingValidator
from ai_delegate.models import ExpertResult, Finding, TaskConfig, Tier


def make_task_config(always_deep: bool = False) -> TaskConfig:
    return TaskConfig(
        task_type="analyze",
        experts={"Complexity": "...", "Database": "...", "Memory": "..."},
        display_name="ANALYZE",
        description="Performance analysis",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
        always_deep=always_deep,
    )


class TestForcedFindingValidatorUnit:
    def test_all_zero_findings_returns_true(self):
        results = [
            ExpertResult("A", "analyze", findings=[]),
            ExpertResult("B", "analyze", findings=[]),
        ]
        assert ForcedFindingValidator.should_force_deep(results) is True

    def test_nonzero_findings_returns_false(self):
        results = [
            ExpertResult("A", "analyze", findings=[Finding(severity="high", issue="N+1 query")]),
            ExpertResult("B", "analyze", findings=[]),
        ]
        assert ForcedFindingValidator.should_force_deep(results) is False

    def test_all_errored_returns_false(self):
        results = [
            ExpertResult("A", "analyze", findings=[], error="Timeout"),
            ExpertResult("B", "analyze", findings=[], error="Timeout"),
        ]
        assert ForcedFindingValidator.should_force_deep(results) is False

    def test_errored_plus_zero_findings_returns_true(self):
        """Errored experts are excluded — only successful zero-finding experts count."""
        results = [
            ExpertResult("A", "analyze", findings=[], error="Timeout"),
            ExpertResult("B", "analyze", findings=[]),  # successful, zero findings
        ]
        assert ForcedFindingValidator.should_force_deep(results) is True


class TestForcedFindingValidatorIntegration:
    def test_zero_findings_from_all_experts_forces_deep_tier(self):
        """When all experts return 0 findings, tier must be promoted to DEEP."""
        client = MagicMock()
        client.run_json.return_value = {"findings": [], "summary": "No issues"}

        config = make_task_config(always_deep=False)
        orchestrator = DebateOrchestrator(client=client, task_config=config)

        zero_results = [
            ExpertResult("Complexity", "analyze", findings=[], raw_output='{"findings": []}'),
            ExpertResult("Database", "analyze", findings=[], raw_output='{"findings": []}'),
            ExpertResult("Memory", "analyze", findings=[], raw_output='{"findings": []}'),
        ]

        with patch.object(orchestrator.expert_runner, 'run_parallel', return_value=zero_results):
            verdict = orchestrator.analyze("some code", tier=Tier.AUTO.value)

        assert verdict.tier_used == Tier.DEEP.value

    def test_nonzero_findings_allow_normal_tier_selection(self):
        """When experts find issues, normal tier selection applies."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "SQL injection"}]
        }

        config = make_task_config(always_deep=False)
        orchestrator = DebateOrchestrator(client=client, task_config=config)

        findings = [Finding(severity="high", issue="SQL injection")]
        results = [
            ExpertResult("Complexity", "analyze", findings=findings, raw_output='{}'),
            ExpertResult("Database", "analyze", findings=findings, raw_output='{}'),
            ExpertResult("Memory", "analyze", findings=findings, raw_output='{}'),
        ]

        with patch.object(orchestrator.expert_runner, 'run_parallel', return_value=results):
            verdict = orchestrator.analyze("some code", tier=Tier.AUTO.value)

        # 3/3 consensus → FAST tier
        assert verdict.tier_used == Tier.FAST.value
