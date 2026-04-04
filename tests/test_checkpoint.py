"""Tests for CheckpointPresenter (concern-organized output)."""
from ai_delegate.checkpoint import CheckpointPresenter
from ai_delegate.models import Verdict, Finding


def make_verdict_with_findings():
    return Verdict(
        task_type="audit",
        consensus_score=0.85,
        tier_used="standard",
        findings=[
            Finding(severity="critical", issue="SQL injection on line 42",
                    location="auth.py:42", recommendation="Use parameterized queries"),
            Finding(severity="high", issue="Hardcoded API key",
                    location="config.py:7", recommendation="Use environment variables"),
            Finding(severity="medium", issue="Missing rate limiting",
                    location="api.py:100", recommendation="Add rate limiting middleware"),
            Finding(severity="low", issue="Missing input validation",
                    location="forms.py:55", recommendation="Validate all user inputs"),
        ],
        recommendations=["Fix SQL injection immediately", "Rotate API keys"],
        action_items=["1. Fix SQL injection", "2. Remove hardcoded keys"],
    )


class TestCheckpointPresenter:
    def test_groups_findings_by_severity(self):
        """Checkpoint must group findings by severity, critical first."""
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)

        critical_pos = report.index("CRITICAL")
        high_pos = report.index("HIGH")
        medium_pos = report.index("MEDIUM")
        assert critical_pos < high_pos < medium_pos

    def test_shows_finding_count_per_severity(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)

        assert "1 finding" in report or "1)" in report
        assert "SQL injection" in report

    def test_includes_action_items_section(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)

        assert "ACTION ITEMS" in report or "action" in report.lower()
        assert "Fix SQL injection" in report

    def test_shows_checkpoint_summary_header(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)

        assert "CHECKPOINT" in report or "SUMMARY" in report
        assert "audit" in report.lower()

    def test_empty_findings_shows_clean_message(self):
        """No findings shows a positive clean message."""
        verdict = Verdict(
            task_type="audit",
            consensus_score=1.0,
            tier_used="fast",
            findings=[],
        )
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)

        assert "No findings" in report or "clean" in report.lower() or "✅" in report
