"""Batch analysis: run analysis on multiple files in parallel."""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .constants import WorkerConstants


@dataclass
class BatchResult:
    """Result for a single file in a batch run."""
    file_path: str
    success: bool
    result: Optional[dict] = None
    error: Optional[str] = None


@dataclass
class BatchReport:
    """Summary report for a batch analysis run."""
    results: List[BatchResult] = field(default_factory=list)

    @property
    def succeeded(self) -> List[BatchResult]:
        return [r for r in self.results if r.success]

    @property
    def failed(self) -> List[BatchResult]:
        return [r for r in self.results if not r.success]

    def to_dict(self) -> dict:
        return {
            "total": len(self.results),
            "succeeded": len(self.succeeded),
            "failed": len(self.failed),
            "results": [
                {
                    "file": r.file_path,
                    "success": r.success,
                    "error": r.error,
                    "findings_count": len(r.result.get("findings", [])) if r.result else 0,
                }
                for r in self.results
            ],
        }


class BatchAnalyzer:
    """Run analysis on multiple files in parallel."""

    def __init__(self, max_workers: int = WorkerConstants.DEFAULT_MAX_WORKERS):
        self.max_workers = max_workers

    def analyze(
        self,
        files: List[Path],
        task_type: str,
        run_fn,
        **kwargs,
    ) -> BatchReport:
        """
        Analyze multiple files in parallel.

        Args:
            files: List of file paths to analyze
            task_type: Analysis task type (audit, analyze, etc.)
            run_fn: Callable(content, task_type, **kwargs) -> dict
            **kwargs: Extra arguments forwarded to run_fn

        Returns:
            BatchReport with per-file results
        """
        results: List[BatchResult] = []
        futures = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            for file_path in files:
                future = executor.submit(
                    self._analyze_file, file_path, task_type, run_fn, kwargs
                )
                futures[future] = file_path

            for future in as_completed(futures):
                file_path = futures[future]
                try:
                    result = future.result()
                    results.append(BatchResult(
                        file_path=str(file_path),
                        success=True,
                        result=result,
                    ))
                except Exception as e:
                    results.append(BatchResult(
                        file_path=str(file_path),
                        success=False,
                        error=str(e),
                    ))

        # Sort by file path for deterministic output
        results.sort(key=lambda r: r.file_path)
        return BatchReport(results=results)

    @staticmethod
    def _analyze_file(file_path: Path, task_type: str, run_fn, kwargs: dict) -> dict:
        content = file_path.read_text()
        return run_fn(content=content, task_type=task_type, **kwargs)
