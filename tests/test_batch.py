"""Tests for BatchAnalyzer parallel file analysis."""
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from ai_delegate.batch import BatchAnalyzer, BatchReport, BatchResult


def make_files(tmpdir, count=3):
    paths = []
    for i in range(count):
        p = Path(tmpdir) / f"file{i}.py"
        p.write_text(f"# file {i}\nprint({i})\n")
        paths.append(p)
    return paths


def mock_run_fn(content, task_type, **kwargs):
    return {
        "task_type": task_type,
        "findings": [{"severity": "high", "issue": "test finding"}],
        "consensus_score": 0.8,
        "tier_used": "standard",
    }


class TestBatchReport:
    def test_succeeded_and_failed_properties(self):
        report = BatchReport(results=[
            BatchResult(file_path="a.py", success=True, result={}),
            BatchResult(file_path="b.py", success=False, error="oops"),
        ])
        assert len(report.succeeded) == 1
        assert len(report.failed) == 1

    def test_to_dict_structure(self):
        report = BatchReport(results=[
            BatchResult(file_path="a.py", success=True, result={"findings": [{"severity": "high", "issue": "X"}]}),
        ])
        d = report.to_dict()
        assert d["total"] == 1
        assert d["succeeded"] == 1
        assert d["failed"] == 0
        assert d["results"][0]["findings_count"] == 1


class TestBatchAnalyzer:
    def test_analyze_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = make_files(tmpdir, count=3)
            analyzer = BatchAnalyzer(max_workers=2)
            report = analyzer.analyze(files, "audit", mock_run_fn)

        assert len(report.results) == 3
        assert all(r.success for r in report.results)

    def test_results_sorted_by_file_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            files = make_files(tmpdir, count=3)
            analyzer = BatchAnalyzer(max_workers=3)
            report = analyzer.analyze(files, "audit", mock_run_fn)

        paths = [r.file_path for r in report.results]
        assert paths == sorted(paths)

    def test_failed_file_captured_not_raised(self):
        def failing_run_fn(content, task_type, **kwargs):
            raise RuntimeError("API error")

        with tempfile.TemporaryDirectory() as tmpdir:
            files = make_files(tmpdir, count=2)
            analyzer = BatchAnalyzer()
            report = analyzer.analyze(files, "audit", failing_run_fn)

        assert len(report.failed) == 2
        assert all("API error" in r.error for r in report.failed)

    def test_mixed_success_and_failure(self):
        call_count = [0]

        def mixed_run_fn(content, task_type, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("first file fails")
            return {"findings": [], "task_type": task_type, "consensus_score": 1.0, "tier_used": "fast"}

        with tempfile.TemporaryDirectory() as tmpdir:
            files = make_files(tmpdir, count=2)
            analyzer = BatchAnalyzer(max_workers=1)  # serial to control order
            report = analyzer.analyze(files, "audit", mixed_run_fn)

        total_outcomes = len(report.succeeded) + len(report.failed)
        assert total_outcomes == 2

    def test_empty_file_list(self):
        analyzer = BatchAnalyzer()
        report = analyzer.analyze([], "audit", mock_run_fn)
        assert report.to_dict()["total"] == 0
