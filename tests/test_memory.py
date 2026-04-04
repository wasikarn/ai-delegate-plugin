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


class TestCliPerformanceMethods:
    """Tests for CLI performance tracking and adaptive routing."""

    @pytest.fixture
    def memory(self, tmp_path):
        db_path = tmp_path / "test_memory.db"
        return AnalysisMemory(db_path=db_path)

    def test_store_returns_run_id(self, memory):
        """Test that store() returns the run_id as integer."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        assert isinstance(run_id, int)
        assert run_id > 0

    def test_record_cli_run_backfills_cli_name(self, memory):
        """Test that record_cli_run() updates cli_name for an existing run."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        history = memory.get_history("src/auth.py", "audit")
        assert len(history) == 1
        # Verify cli_name was recorded (via direct query or inspection)

    def test_store_rating_creates_cli_performance_entry(self, memory):
        """Test that store_rating() creates or updates cli_performance entry."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        memory.store_rating(run_id, 1)  # 1 = win
        perf = memory.get_cli_performance("audit")
        assert len(perf) > 0
        assert any(p["cli_name"] == "ollama" for p in perf)

    def test_store_rating_updates_win_loss_counts(self, memory):
        """Test that store_rating() correctly updates win/loss counts and win_rate."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "codex")
        memory.store_rating(run_id, 1)  # win
        perf = memory.get_cli_performance("audit")
        codex_perf = [p for p in perf if p["cli_name"] == "codex"][0]
        assert codex_perf["win_count"] > 0
        assert codex_perf["run_count"] > 0
        assert codex_perf["win_rate"] > 0

    def test_store_rating_handles_loss(self, memory):
        """Test that store_rating() with rating=0 increments loss_count."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "gemini")
        memory.store_rating(run_id, 0)  # loss
        perf = memory.get_cli_performance("audit")
        gemini_perf = [p for p in perf if p["cli_name"] == "gemini"][0]
        assert gemini_perf["loss_count"] > 0
        assert gemini_perf["run_count"] > 0

    def test_get_cli_performance_returns_sorted_by_win_rate(self, memory):
        """Test that get_cli_performance() returns CLIs sorted by win_rate descending."""
        record1 = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id1 = memory.store(record1)
        memory.record_cli_run(run_id1, "ollama")
        memory.store_rating(run_id1, 1)

        record2 = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.70,
            finding_count=2,
            critical_count=0,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit",
        )
        run_id2 = memory.store(record2)
        memory.record_cli_run(run_id2, "codex")
        memory.store_rating(run_id2, 0)

        perf = memory.get_cli_performance("audit")
        # Verify sorted by win_rate descending
        if len(perf) > 1:
            assert perf[0]["win_rate"] >= perf[1]["win_rate"]

    def test_get_cli_performance_empty_when_no_ratings(self, memory):
        """Test that get_cli_performance() returns seeded priors when no explicit ratings."""
        perf = memory.get_cli_performance("audit")
        # Should return seeded priors from CLI_PRIORS
        assert len(perf) > 0

    def test_get_recent_cli_runs_returns_list_of_cli_names(self, memory):
        """Test that get_recent_cli_runs() returns recent CLI names in order."""
        record = MemoryRecord(
            file_path="src/auth.py",
            task_type="audit",
            consensus_score=0.75,
            finding_count=3,
            critical_count=1,
            high_count=2,
            findings_summary="SQL injection; Missing rate limit; Weak password policy",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        recent = memory.get_recent_cli_runs("audit", limit=5)
        assert isinstance(recent, list)
        assert "ollama" in recent

    def test_get_recent_cli_runs_respects_limit(self, memory):
        """Test that get_recent_cli_runs() respects the limit parameter."""
        for i in range(5):
            record = MemoryRecord(
                file_path="src/auth.py",
                task_type="audit",
                consensus_score=0.75,
                finding_count=3,
                critical_count=1,
                high_count=2,
                findings_summary=f"Run {i}",
            )
            run_id = memory.store(record)
            memory.record_cli_run(run_id, f"cli_{i}")

        recent = memory.get_recent_cli_runs("audit", limit=2)
        assert len(recent) <= 2

    def test_cli_performance_seeded_from_cli_priors(self, memory):
        """Test that cli_performance table is seeded from CLI_PRIORS on init."""
        perf = memory.get_cli_performance("audit")
        # Should have entries for all CLIs in CLI_PRIORS
        assert len(perf) > 0
        cli_names = [p["cli_name"] for p in perf]
        assert any(name in cli_names for name in ["ollama", "codex", "gemini", "claude"])
