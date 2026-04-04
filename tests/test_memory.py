"""Tests for AnalysisMemory cross-session regression detection (plan spec)."""
import pytest
import tempfile
from pathlib import Path
from ai_delegate.memory import AnalysisMemory, MemoryRecord


class TestAnalysisMemory:
    @pytest.fixture
    def memory(self, tmp_path):
        db_path = tmp_path / "test_memory.db"
        return AnalysisMemory(db_path=db_path)

    def test_store_and_retrieve(self, memory):
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        memory.store(record)
        history = memory.get_history("src/auth.py", "audit")
        assert len(history) == 1
        assert history[0].consensus_score == 0.75
        assert history[0].finding_count == 3

    def test_regression_detected_when_new_findings_added(self, memory):
        old = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.80,
            finding_count=2,
            critical_count=0,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit",
        )
        new = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.70,
            finding_count=4,
            critical_count=1,
            high_count=3,
            findings_summary="SQL injection; Missing rate limit; XSS; Path traversal",
        )
        memory.store(old)
        regression = memory.detect_regression(new)
        assert regression is not None
        assert regression["new_findings"] == 2
        assert regression["new_critical"] == 1

    def test_no_regression_when_findings_decrease(self, memory):
        old = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=4,
            critical_count=1,
            high_count=3,
            findings_summary="SQL injection; XSS; Path traversal; CSRF",
        )
        new = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.85,
            finding_count=2,
            critical_count=0,
            high_count=2,
            findings_summary="CSRF; Rate limiting",
        )
        memory.store(old)
        regression = memory.detect_regression(new)
        assert regression is None

    def test_no_history_returns_none_regression(self, memory):
        record = MemoryRecord(
            file_path="src/new.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=2,
            critical_count=0,
            high_count=2,
            findings_summary="Issue A; Issue B",
        )
        regression = memory.detect_regression(record)
        assert regression is None

    def test_multiple_runs_stored(self, memory):
        for i in range(3):
            record = MemoryRecord(
                file_path="src/auth.py",
                task_type="audit",
                consensus_score=0.70 + i * 0.05,
                finding_count=4 - i,
                critical_count=0,
                high_count=2,
                findings_summary=f"Run {i}",
            )
            memory.store(record)
        history = memory.get_history("src/auth.py", "audit")
        assert len(history) == 3

    def test_get_history_limit(self, memory):
        for i in range(5):
            memory.store(MemoryRecord(
                file_path="src/auth.py",
                task_type="audit",
                consensus_score=0.75,
                finding_count=2,
                critical_count=0,
                high_count=2,
                findings_summary=f"Run {i}",
            ))
        history = memory.get_history("src/auth.py", "audit", limit=3)
        assert len(history) == 3

    def test_store_findings_creates_rows(self, memory):
        memory.store_findings(
            analysis_run_id=1,
            task_type="audit",
            findings=[
                {"severity": "high", "issue": "SQL injection in login handler"},
                {"severity": "medium", "issue": "Missing rate limit on /api/auth"},
            ],
        )
        rows = memory.get_all_findings(task_type="audit")
        assert len(rows) == 2
        assert rows[0]["issue_text"] == "SQL injection in login handler"
        assert rows[0]["severity"] == "high"

    def test_search_findings_returns_matches(self, memory):
        memory.store_findings(
            analysis_run_id=1,
            task_type="audit",
            findings=[
                {"severity": "high",   "issue": "SQL injection in login handler"},
                {"severity": "medium", "issue": "Missing rate limit on /api/auth"},
                {"severity": "low",    "issue": "Unused import statement"},
            ],
        )
        results = memory.search_findings("SQL injection")
        assert len(results) == 1
        assert results[0]["issue_text"] == "SQL injection in login handler"

    def test_search_findings_empty_when_no_match(self, memory):
        memory.store_findings(
            analysis_run_id=1,
            task_type="audit",
            findings=[{"severity": "low", "issue": "Unused import statement"}],
        )
        results = memory.search_findings("XSS")
        assert results == []

    def test_search_findings_partial_match(self, memory):
        memory.store_findings(
            analysis_run_id=1,
            task_type="audit",
            findings=[
                {"severity": "high", "issue": "SQL injection via string concat"},
                {"severity": "high", "issue": "SQL injection via ORM bypass"},
            ],
        )
        results = memory.search_findings("SQL")
        assert len(results) == 2
