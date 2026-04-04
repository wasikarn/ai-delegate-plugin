"""Tests for DebatePhase output parsing fix."""
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import DebatePhase
from ai_delegate.models import ExpertResult, Finding, TaskConfig


def make_task_config() -> TaskConfig:
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "You are OWASP expert."},
        display_name="AUDIT",
        description="Security audit",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
    )


class TestDebatePhaseOutputParsing:
    def test_debate_uses_new_findings_not_old_ones(self):
        """Debate phase must parse findings from the new LLM output, not reuse initial findings."""
        client = MagicMock()
        # New output from debate has a different finding
        client.run_json.return_value = {
            "findings": [
                {"severity": "critical", "issue": "New finding discovered in debate"}
            ]
        }

        phase = DebatePhase(client=client, task_config=make_task_config())

        initial_results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="Old initial finding")],
                raw_output='{"findings": [{"severity": "high", "issue": "Old initial finding"}]}',
            )
        ]

        debate_results = phase.run(initial_results)

        assert len(debate_results) == 1
        # Should have NEW finding from debate output, not old one
        assert debate_results[0].findings[0].issue == "New finding discovered in debate"
        assert debate_results[0].findings[0].severity == "critical"

    def test_debate_falls_back_to_old_findings_if_new_output_has_none(self):
        """If debate output has no findings, fall back to original findings."""
        client = MagicMock()
        client.run_json.return_value = {"analysis": "no new issues found"}  # No findings key

        phase = DebatePhase(client=client, task_config=make_task_config())

        initial_results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="Original finding")],
                raw_output='{"findings": [{"severity": "high", "issue": "Original finding"}]}',
            )
        ]

        debate_results = phase.run(initial_results)

        # Falls back to original when new output has no findings
        assert debate_results[0].findings[0].issue == "Original finding"

    def test_debate_skips_errored_results(self):
        """Results with errors are skipped in debate."""
        client = MagicMock()
        client.run_json.return_value = {"findings": []}

        phase = DebatePhase(client=client, task_config=make_task_config())

        results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="SQL injection")],
                raw_output="{}",
                error="API timeout",
            )
        ]

        debate_results = phase.run(results)
        assert len(debate_results) == 0  # Errored result is skipped

    def test_debate_handles_null_findings_in_output(self):
        """Debate output with null findings falls back to original."""
        client = MagicMock()
        client.run_json.return_value = {"findings": None}

        phase = DebatePhase(client=client, task_config=make_task_config())

        initial_results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="Original")],
                raw_output="{}",
            )
        ]

        debate_results = phase.run(initial_results)
        assert debate_results[0].findings[0].issue == "Original"
