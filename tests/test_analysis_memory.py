"""Tests for AnalysisMemory cross-session regression detection."""
import tempfile
from pathlib import Path
import pytest
from ai_delegate.analysis_memory import AnalysisMemory, RegressionResult


def make_findings(issues):
    return [{"severity": "high", "issue": issue} for issue in issues]


class TestAnalysisMemory:
    def setup_method(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self._tmpdir.name) / "memory.db"
        self.memory = AnalysisMemory(db_path=self.db_path)

    def teardown_method(self):
        self._tmpdir.cleanup()

    def test_hash_content_is_stable(self):
        h1 = AnalysisMemory.hash_content("hello world")
        h2 = AnalysisMemory.hash_content("hello world")
        assert h1 == h2

    def test_hash_different_content_differs(self):
        h1 = AnalysisMemory.hash_content("content A")
        h2 = AnalysisMemory.hash_content("content B")
        assert h1 != h2

    def test_store_and_retrieve_history(self):
        self.memory.store("my code", "audit", make_findings(["XSS", "SQLi"]))
        history = self.memory.get_history("my code", "audit")
        assert len(history) == 1
        assert history[0].findings_count == 2
        assert history[0].task_type == "audit"

    def test_no_prior_run_returns_none(self):
        result = self.memory.check_regression("new code", "audit", make_findings(["XSS"]))
        assert result is None

    def test_no_regression_when_findings_unchanged(self):
        findings = make_findings(["XSS", "SQLi"])
        self.memory.store("my code", "audit", findings)
        result = self.memory.check_regression("my code", "audit", findings)
        assert result is not None
        assert not result.has_regression
        assert result.summary == "No changes detected"

    def test_regression_detected_on_new_finding(self):
        self.memory.store("my code", "audit", make_findings(["XSS"]))
        result = self.memory.check_regression("my code", "audit", make_findings(["XSS", "SQLi"]))
        assert result is not None
        assert result.has_regression
        assert "new finding" in result.summary

    def test_resolved_finding_detected(self):
        self.memory.store("my code", "audit", make_findings(["XSS", "SQLi"]))
        result = self.memory.check_regression("my code", "audit", make_findings(["XSS"]))
        assert result is not None
        assert not result.has_regression  # resolved is not a regression
        assert "resolved" in result.summary
        assert len(result.resolved_findings) == 1

    def test_multiple_runs_accumulate_in_history(self):
        self.memory.store("my code", "audit", make_findings(["XSS"]))
        self.memory.store("my code", "audit", make_findings(["XSS", "SQLi"]))
        history = self.memory.get_history("my code", "audit")
        assert len(history) == 2

    def test_regression_uses_most_recent_run(self):
        self.memory.store("my code", "audit", make_findings(["XSS"]))
        self.memory.store("my code", "audit", make_findings(["XSS", "SQLi"]))
        # Compare against latest (XSS + SQLi) — no regression
        result = self.memory.check_regression("my code", "audit", make_findings(["XSS", "SQLi"]))
        assert result is not None
        assert not result.has_regression

    def test_different_task_types_are_independent(self):
        self.memory.store("code", "audit", make_findings(["XSS"]))
        # No history for "analyze" task
        result = self.memory.check_regression("code", "analyze", make_findings(["XSS"]))
        assert result is None
