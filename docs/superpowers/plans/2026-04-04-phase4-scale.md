# Phase 4: Scale & Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add plugin registry (custom expert definitions), analysis memory (cross-session regression detection), batch analysis, and cost transparency.

**Architecture:** `PluginRegistry` reads YAML from `.ai-delegate/plugins/`. `AnalysisMemory` uses SQLite at `~/.ai-delegate/memory.db`. `BatchRunner` wraps existing `run_analysis()` in a parallel executor. Cost is calculated by token count × model rate from a constants table.

**Tech Stack:** Python 3.10+, sqlite3 (stdlib), PyYAML (already in requirements or add), concurrent.futures, existing cli.py

---

### Task 1: Plugin Registry (Custom Expert Definitions)

**Files:**

- Create: `ai_delegate/plugin_registry.py`
- Modify: `ai_delegate/debate/orchestrator.py` (load plugins into expert list)
- Create: `tests/test_plugin_registry.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_plugin_registry.py
import pytest
import os
import tempfile
from pathlib import Path
from ai_delegate.plugin_registry import PluginRegistry, ExpertPlugin


class TestPluginRegistry:
    def test_load_valid_plugin(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        plugin_file = plugin_dir / "gdpr-expert.yaml"
        plugin_file.write_text("""
name: gdpr-expert
display_name: GDPR Compliance Expert
task_types:
  - audit
  - review
prompt: |
  You are a GDPR compliance expert. Analyze the code for GDPR violations.
  Focus on: data minimization, consent, right to erasure, data portability.
  Return JSON with findings list.
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 1
        assert plugins[0].name == "gdpr-expert"
        assert plugins[0].display_name == "GDPR Compliance Expert"
        assert "audit" in plugins[0].task_types

    def test_load_multiple_plugins(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        for name in ["expert-a", "expert-b", "expert-c"]:
            (plugin_dir / f"{name}.yaml").write_text(f"""
name: {name}
display_name: {name.upper()}
task_types: [audit]
prompt: "You are {name}."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 3

    def test_missing_required_field_skipped(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "bad-plugin.yaml").write_text("""
name: bad-plugin
# Missing: task_types, prompt
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 0

    def test_empty_directory_returns_empty_list(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert plugins == []

    def test_nonexistent_directory_returns_empty(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        # Directory does NOT exist
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert plugins == []

    def test_plugin_for_task_type(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "audit-only.yaml").write_text("""
name: audit-only
display_name: Audit Only Expert
task_types: [audit]
prompt: "Audit prompt."
""")
        (plugin_dir / "review-only.yaml").write_text("""
name: review-only
display_name: Review Only Expert
task_types: [review]
prompt: "Review prompt."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        audit_plugins = registry.for_task("audit")
        assert len(audit_plugins) == 1
        assert audit_plugins[0].name == "audit-only"

    def test_to_expert_dict(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "custom.yaml").write_text("""
name: custom-expert
display_name: Custom Expert
task_types: [audit]
prompt: "Custom analysis prompt."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        expert_dict = plugins[0].to_expert_dict()
        assert "custom-expert" in expert_dict
        assert expert_dict["custom-expert"] == "Custom analysis prompt."
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_plugin_registry.py -v 2>&1 | head -20
```

Expected: ImportError for `ai_delegate.plugin_registry`

- [ ] **Step 3: Create PluginRegistry**

```python
# ai_delegate/plugin_registry.py
"""
Plugin registry for custom expert definitions.
Loads YAML expert plugins from .ai-delegate/plugins/.
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class ExpertPlugin:
    name: str
    display_name: str
    task_types: List[str]
    prompt: str

    def to_expert_dict(self) -> Dict[str, str]:
        """Return {name: prompt} for injection into TaskConfig.experts."""
        return {self.name: self.prompt}


class PluginRegistry:
    """Loads custom expert plugins from a directory of YAML files."""

    def __init__(self, plugin_dir: Optional[Path] = None):
        if plugin_dir is None:
            plugin_dir = Path.cwd() / ".ai-delegate" / "plugins"
        self._plugin_dir = Path(plugin_dir)
        self._plugins: Optional[List[ExpertPlugin]] = None

    def load(self) -> List[ExpertPlugin]:
        """Load all plugins from directory. Returns empty list if dir missing or yaml unavailable."""
        if self._plugins is not None:
            return self._plugins

        if not HAS_YAML:
            logger.warning("PyYAML not installed — plugin registry disabled")
            self._plugins = []
            return self._plugins

        if not self._plugin_dir.exists():
            self._plugins = []
            return self._plugins

        plugins = []
        for yaml_file in sorted(self._plugin_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text())
                if not isinstance(data, dict):
                    continue
                name = data.get("name")
                task_types = data.get("task_types")
                prompt = data.get("prompt")
                if not name or not task_types or not prompt:
                    logger.warning("Skipping %s: missing required fields (name, task_types, prompt)", yaml_file.name)
                    continue
                plugins.append(ExpertPlugin(
                    name=str(name),
                    display_name=str(data.get("display_name", name)),
                    task_types=[str(t) for t in task_types],
                    prompt=str(prompt).strip(),
                ))
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", yaml_file.name, e)

        self._plugins = plugins
        return self._plugins

    def for_task(self, task_type: str) -> List[ExpertPlugin]:
        """Return plugins applicable to a given task type."""
        return [p for p in self.load() if task_type in p.task_types]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_plugin_registry.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Integrate plugins into run_analysis()**

In `ai_delegate/cli.py`, in `run_analysis()`, after `config = create_task_config(task_type)`:

```python
    # Load custom expert plugins
    from .plugin_registry import PluginRegistry
    registry = PluginRegistry()
    custom_experts = registry.for_task(task_type)
    for plugin in custom_experts:
        config.experts.update(plugin.to_expert_dict())
    if custom_experts and verbose:
        print(f"Loaded {len(custom_experts)} custom expert(s): {[p.name for p in custom_experts]}")
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/plugin_registry.py tests/test_plugin_registry.py ai_delegate/cli.py
git commit -m "feat: add plugin registry for YAML-based custom expert definitions"
```

---

### Task 2: Analysis Memory (Cross-Session Regression Detection)

**Files:**

- Create: `ai_delegate/memory.py`
- Modify: `ai_delegate/cli.py` (store results, add `--compare` flag)
- Create: `tests/test_memory.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_memory.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_memory.py -v 2>&1 | head -20
```

Expected: ImportError for `ai_delegate.memory`

- [ ] **Step 3: Create AnalysisMemory**

```python
# ai_delegate/memory.py
"""
Analysis memory for cross-session regression detection.
Stores results in SQLite at ~/.ai-delegate/memory.db.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MemoryRecord:
    file_path: str
    task_type: str
    consensus_score: float
    finding_count: int
    critical_count: int
    high_count: int
    findings_summary: str
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow().isoformat()


class AnalysisMemory:
    """Stores and queries analysis results across sessions."""

    DEFAULT_DB = Path.home() / ".ai-delegate" / "memory.db"

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    consensus_score REAL NOT NULL,
                    finding_count INTEGER NOT NULL,
                    critical_count INTEGER NOT NULL,
                    high_count INTEGER NOT NULL,
                    findings_summary TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_file_task ON analysis_runs (file_path, task_type)")

    def store(self, record: MemoryRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO analysis_runs
                   (file_path, task_type, consensus_score, finding_count, critical_count, high_count, findings_summary, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (record.file_path, record.task_type, record.consensus_score,
                 record.finding_count, record.critical_count, record.high_count,
                 record.findings_summary, record.timestamp),
            )

    def get_history(self, file_path: str, task_type: str, limit: int = 10) -> List[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT file_path, task_type, consensus_score, finding_count, critical_count, high_count, findings_summary, timestamp
                   FROM analysis_runs WHERE file_path = ? AND task_type = ?
                   ORDER BY timestamp DESC LIMIT ?""",
                (file_path, task_type, limit),
            ).fetchall()
        return [
            MemoryRecord(
                file_path=r[0], task_type=r[1], consensus_score=r[2],
                finding_count=r[3], critical_count=r[4], high_count=r[5],
                findings_summary=r[6], timestamp=r[7],
            )
            for r in rows
        ]

    def detect_regression(self, current: MemoryRecord) -> Optional[Dict]:
        """Compare current result against most recent stored result. Returns regression dict or None."""
        history = self.get_history(current.file_path, current.task_type, limit=1)
        if not history:
            return None
        prev = history[0]
        new_findings = current.finding_count - prev.finding_count
        new_critical = current.critical_count - prev.critical_count
        if new_findings > 0 or new_critical > 0:
            return {
                "new_findings": max(new_findings, 0),
                "new_critical": max(new_critical, 0),
                "prev_findings": prev.finding_count,
                "curr_findings": current.finding_count,
                "prev_score": prev.consensus_score,
                "curr_score": current.consensus_score,
            }
        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_memory.py -v
```

Expected: All 6 tests PASS

- [ ] **Step 5: Integrate memory into run_analysis()**

In `ai_delegate/cli.py`, update `run_analysis()` to accept and use memory:

Add to the function signature: `store_memory: bool = True`

After `return verdict.to_dict()` in `run_analysis()`, change to:

```python
    result = verdict.to_dict()

    if store_memory and args_file_path:
        from .memory import AnalysisMemory, MemoryRecord
        findings = result.get("findings", [])
        record = MemoryRecord(
            file_path=str(args_file_path),
            task_type=task_type,
            consensus_score=result["consensus_score"],
            finding_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity", "").lower() == "critical"),
            high_count=sum(1 for f in findings if f.get("severity", "").lower() == "high"),
            findings_summary="; ".join(f.get("issue", "")[:80] for f in findings[:10]),
        )
        try:
            memory = AnalysisMemory()
            regression = memory.detect_regression(record)
            memory.store(record)
            result["regression"] = regression
        except Exception:
            pass  # Memory is non-critical

    return result
```

In `main()`, after calling `run_analysis()`, display regression warning:

```python
        regression = result.get("regression")
        if regression and regression["new_findings"] > 0:
            import sys
            print(
                f"\n⚠️  REGRESSION: +{regression['new_findings']} new findings "
                f"(+{regression['new_critical']} critical) vs last run",
                file=sys.stderr,
            )
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/memory.py tests/test_memory.py ai_delegate/cli.py
git commit -m "feat: add analysis memory with cross-session regression detection"
```

---

### Task 3: Batch Analysis

**Files:**

- Create: `ai_delegate/batch_runner.py`
- Modify: `ai_delegate/cli.py` (add `batch` subcommand)
- Create: `tests/test_batch_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_batch_runner.py
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from ai_delegate.batch_runner import BatchRunner, BatchResult


class TestBatchRunner:
    def test_collect_files_from_dir(self, tmp_path):
        (tmp_path / "auth.py").write_text("def login(): pass")
        (tmp_path / "api.py").write_text("def endpoint(): pass")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "utils.py").write_text("def helper(): pass")

        runner = BatchRunner(task_type="audit", max_workers=2)
        files = runner.collect_files(tmp_path, pattern="*.py", recursive=True)
        assert len(files) == 3

    def test_collect_files_non_recursive(self, tmp_path):
        (tmp_path / "auth.py").write_text("def login(): pass")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "utils.py").write_text("def helper(): pass")

        runner = BatchRunner(task_type="audit", max_workers=2)
        files = runner.collect_files(tmp_path, pattern="*.py", recursive=False)
        assert len(files) == 1

    def test_batch_result_aggregation(self):
        results = [
            BatchResult(file_path="a.py", success=True, finding_count=2, critical_count=1, result={}),
            BatchResult(file_path="b.py", success=True, finding_count=0, critical_count=0, result={}),
            BatchResult(file_path="c.py", success=False, finding_count=0, critical_count=0, error="Timeout"),
        ]
        runner = BatchRunner(task_type="audit", max_workers=2)
        summary = runner.summarize(results)
        assert summary["total_files"] == 3
        assert summary["success_count"] == 2
        assert summary["error_count"] == 1
        assert summary["total_findings"] == 2
        assert summary["total_critical"] == 1
        assert "c.py" in summary["errors"][0]

    def test_empty_dir_returns_empty_results(self, tmp_path):
        runner = BatchRunner(task_type="audit", max_workers=2)
        files = runner.collect_files(tmp_path, pattern="*.py", recursive=True)
        assert files == []

    def test_batch_result_error_flag(self):
        result = BatchResult(file_path="x.py", success=False, finding_count=0, critical_count=0, error="Boom")
        assert result.success is False
        assert result.error == "Boom"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_batch_runner.py -v 2>&1 | head -20
```

Expected: ImportError for `ai_delegate.batch_runner`

- [ ] **Step 3: Create BatchRunner**

```python
# ai_delegate/batch_runner.py
"""
Batch analysis runner for processing multiple files.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Any


@dataclass
class BatchResult:
    file_path: str
    success: bool
    finding_count: int
    critical_count: int
    result: Dict[str, Any]
    error: Optional[str] = None


class BatchRunner:
    """Runs analysis on multiple files in parallel."""

    def __init__(self, task_type: str, max_workers: int = 4):
        self._task_type = task_type
        self._max_workers = max_workers

    def collect_files(self, directory: Path, pattern: str = "*.py", recursive: bool = True) -> List[Path]:
        """Collect files matching pattern from directory."""
        if recursive:
            return sorted(directory.rglob(pattern))
        return sorted(directory.glob(pattern))

    def run(
        self,
        files: List[Path],
        analyze_fn: Callable[[str, str], Dict],
        verbose: bool = False,
    ) -> List[BatchResult]:
        """Run analysis on all files using thread pool."""
        results = []
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            future_to_file = {
                executor.submit(self._analyze_file, f, analyze_fn): f
                for f in files
            }
            for future in as_completed(future_to_file):
                file_path = future_to_file[future]
                try:
                    result = future.result()
                    findings = result.get("findings", [])
                    results.append(BatchResult(
                        file_path=str(file_path),
                        success=True,
                        finding_count=len(findings),
                        critical_count=sum(1 for f in findings if f.get("severity", "").lower() == "critical"),
                        result=result,
                    ))
                    if verbose:
                        print(f"  ✓ {file_path} — {len(findings)} findings")
                except Exception as e:
                    results.append(BatchResult(
                        file_path=str(file_path),
                        success=False,
                        finding_count=0,
                        critical_count=0,
                        result={},
                        error=str(e),
                    ))
                    if verbose:
                        print(f"  ✗ {file_path} — error: {e}")
        return results

    def _analyze_file(self, file_path: Path, analyze_fn: Callable) -> Dict:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        return analyze_fn(content, self._task_type)

    def summarize(self, results: List[BatchResult]) -> Dict[str, Any]:
        success = [r for r in results if r.success]
        errors = [r for r in results if not r.success]
        return {
            "total_files": len(results),
            "success_count": len(success),
            "error_count": len(errors),
            "total_findings": sum(r.finding_count for r in success),
            "total_critical": sum(r.critical_count for r in success),
            "files_with_findings": sum(1 for r in success if r.finding_count > 0),
            "errors": [f"{r.file_path}: {r.error}" for r in errors],
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_batch_runner.py -v
```

Expected: All 5 tests PASS

- [ ] **Step 5: Add `batch` subcommand to CLI**

In `ai_delegate/cli.py`, refactor `main()` to use subparsers. Replace:

```python
    parser.add_argument(
        "task_type",
        choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"],
        help="Type of analysis to perform",
    )
```

With subparser approach:

```python
    subparsers = parser.add_subparsers(dest="command")

    # Single file analysis (positional task_type remains as subcommand)
    for task in ["audit", "analyze", "architecture", "refactor", "migrate", "review"]:
        sub = subparsers.add_parser(task, help=f"Run {task} analysis")
        sub.add_argument("--tier", choices=["auto", "fast", "standard", "deep"], default="auto")
        sub.add_argument("--model")
        sub.add_argument("--file", "-f", type=Path)
        sub.add_argument("--output", "-o", choices=["json", "text"], default="json")
        sub.add_argument("--format", choices=["json", "adr", "risk-matrix", "playbook", "perf-profile"])
        sub.add_argument("--flow", choices=["quick", "standard", "bmad", "enterprise"], default="standard")
        sub.add_argument("--verbose", "-v", action="store_true")

    # Batch subcommand
    batch_parser = subparsers.add_parser("batch", help="Run analysis on multiple files")
    batch_parser.add_argument("task_type", choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"])
    batch_parser.add_argument("--dir", "-d", type=Path, required=True, help="Directory to scan")
    batch_parser.add_argument("--pattern", default="*.py", help="File glob pattern (default: *.py)")
    batch_parser.add_argument("--recursive", action="store_true", default=True)
    batch_parser.add_argument("--workers", type=int, default=4)
    batch_parser.add_argument("--output", "-o", choices=["json", "text"], default="text")
    batch_parser.add_argument("--verbose", "-v", action="store_true")
```

Add batch handler in `main()`:

```python
    if args.command == "batch":
        from .batch_runner import BatchRunner
        import json

        def _analyze(content, task_type):
            return run_analysis(content=content, task_type=task_type, verbose=False)

        runner = BatchRunner(task_type=args.task_type, max_workers=args.workers)
        files = runner.collect_files(args.dir, pattern=args.pattern, recursive=args.recursive)
        if not files:
            print(f"No files matching {args.pattern} found in {args.dir}", file=sys.stderr)
            sys.exit(1)

        if args.verbose:
            print(f"Found {len(files)} files. Running {args.task_type} analysis...")

        results = runner.run(files, _analyze, verbose=args.verbose)
        summary = runner.summarize(results)

        if args.output == "json":
            print(json.dumps({"summary": summary, "results": [
                {"file": r.file_path, "findings": r.finding_count, "critical": r.critical_count,
                 "error": r.error} for r in results
            ]}, indent=2))
        else:
            print(f"\nBatch {args.task_type.upper()} — {summary['total_files']} files")
            print(f"  ✓ {summary['success_count']} analyzed  ✗ {summary['error_count']} errors")
            print(f"  Findings: {summary['total_findings']} total, {summary['total_critical']} critical")
            print(f"  Files with findings: {summary['files_with_findings']}")
            if summary["errors"]:
                print("\nErrors:")
                for e in summary["errors"]:
                    print(f"  - {e}")
        return
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/batch_runner.py tests/test_batch_runner.py ai_delegate/cli.py
git commit -m "feat: add batch analysis for scanning multiple files in parallel"
```

---

### Task 4: Cost Transparency

**Files:**

- Create: `ai_delegate/cost_tracker.py`
- Modify: `ai_delegate/cli.py` (add `--show-cost` flag)
- Modify: `ai_delegate/client.py` (track token usage)
- Create: `tests/test_cost_tracker.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_cost_tracker.py
import pytest
from ai_delegate.cost_tracker import CostTracker, ModelRates


class TestCostTracker:
    def test_known_model_cost(self):
        tracker = CostTracker()
        cost = tracker.calculate(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        assert cost > 0
        assert isinstance(cost, float)

    def test_unknown_model_uses_fallback(self):
        tracker = CostTracker()
        cost = tracker.calculate(model="unknown-model-xyz", input_tokens=1000, output_tokens=500)
        assert cost >= 0  # fallback = 0 or cheap rate

    def test_zero_tokens_zero_cost(self):
        tracker = CostTracker()
        cost = tracker.calculate(model="claude-sonnet-4-6", input_tokens=0, output_tokens=0)
        assert cost == 0.0

    def test_input_cheaper_than_output(self):
        tracker = CostTracker()
        input_only = tracker.calculate(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=0)
        output_only = tracker.calculate(model="claude-sonnet-4-6", input_tokens=0, output_tokens=1000)
        # Output tokens are typically 5x more expensive than input
        assert output_only > input_only

    def test_format_cost_usd(self):
        tracker = CostTracker()
        formatted = tracker.format_cost(0.00345)
        assert "$" in formatted
        assert "0.003" in formatted or "0.00" in formatted

    def test_session_accumulation(self):
        tracker = CostTracker()
        tracker.add(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        tracker.add(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        total = tracker.total_cost
        single = tracker.calculate(model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
        assert abs(total - 2 * single) < 0.0001

    def test_model_rates_have_sonnet(self):
        assert "claude-sonnet-4-6" in ModelRates.RATES
        assert "input" in ModelRates.RATES["claude-sonnet-4-6"]
        assert "output" in ModelRates.RATES["claude-sonnet-4-6"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_cost_tracker.py -v 2>&1 | head -20
```

Expected: ImportError for `ai_delegate.cost_tracker`

- [ ] **Step 3: Create CostTracker**

```python
# ai_delegate/cost_tracker.py
"""
Cost tracking and transparency for ai-delegate analysis.
Rates in USD per 1M tokens (as of 2025).
"""
from dataclasses import dataclass, field
from typing import Dict


class ModelRates:
    """USD per 1M tokens for known models."""
    RATES: Dict[str, Dict[str, float]] = {
        "claude-opus-4-6": {"input": 15.0, "output": 75.0},
        "claude-sonnet-4-6": {"input": 3.0, "output": 15.0},
        "claude-haiku-4-5": {"input": 0.8, "output": 4.0},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-1.5-pro": {"input": 1.25, "output": 5.0},
        "glm-5:cloud": {"input": 0.05, "output": 0.10},
        "kimi-k2.5:cloud": {"input": 0.05, "output": 0.10},
        # Ollama local = free
        "ollama": {"input": 0.0, "output": 0.0},
    }
    FALLBACK: Dict[str, float] = {"input": 0.0, "output": 0.0}

    @classmethod
    def get(cls, model: str) -> Dict[str, float]:
        if model in cls.RATES:
            return cls.RATES[model]
        # Prefix match (e.g. "glm-5" matches "glm-5:cloud")
        for key in cls.RATES:
            if model.startswith(key.split(":")[0]):
                return cls.RATES[key]
        return cls.FALLBACK


class CostTracker:
    """Tracks cumulative token cost across a session."""

    def __init__(self):
        self._total: float = 0.0

    def calculate(self, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = ModelRates.get(model)
        cost = (input_tokens * rates["input"] + output_tokens * rates["output"]) / 1_000_000
        return round(cost, 6)

    def add(self, model: str, input_tokens: int, output_tokens: int) -> float:
        cost = self.calculate(model, input_tokens, output_tokens)
        self._total += cost
        return cost

    @property
    def total_cost(self) -> float:
        return round(self._total, 6)

    def format_cost(self, cost: float) -> str:
        if cost < 0.001:
            return f"${cost:.6f}"
        return f"${cost:.4f}"

    def format_total(self) -> str:
        return self.format_cost(self._total)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_cost_tracker.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Add `--show-cost` to CLI**

In `ai_delegate/cli.py`, add to each task subparser (and to the main parser argparse section):

```python
        sub.add_argument("--show-cost", action="store_true", help="Display estimated token cost")
```

In `main()`, after result is printed, add:

```python
        if getattr(args, "show_cost", False):
            from .cost_tracker import CostTracker
            # Estimate: ~4 chars/token, 2 experts × input+output
            content_len = len(content) if "content" in dir() else 0
            est_input = content_len // 4
            est_output = 500  # typical output per expert
            experts_count = len(create_task_config(args.command).experts)
            tracker = CostTracker()
            model_name = getattr(args, "model", None) or DEFAULT_MODELS.get(args.command, "claude-sonnet-4-6")
            cost = tracker.calculate(model=model_name, input_tokens=est_input * experts_count, output_tokens=est_output * experts_count)
            print(f"\nEstimated cost: {tracker.format_cost(cost)} ({est_input * experts_count:,} input + {est_output * experts_count:,} output tokens)", file=sys.stderr)
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/cost_tracker.py tests/test_cost_tracker.py ai_delegate/cli.py
git commit -m "feat: add cost transparency with --show-cost flag and ModelRates table"
```

---

### Task 5: Bump to v0.3.0 and Push

**Files:**

- Modify: `ai_delegate/__init__.py`
- Modify: `ai_delegate/cli.py` (version string)
- Modify: `README.md`

- [ ] **Step 1: Update version strings**

In `ai_delegate/__init__.py`: `__version__ = "0.3.0"`

In `ai_delegate/cli.py` version string: `version="%(prog)s 0.3.0"`

In `README.md` badge: `version-0.2.0-blue` → `version-0.3.0-blue`

In README, add batch and cost examples:

```bash
# Batch security audit on all Python files
ai-delegate batch audit --dir src/ --pattern "*.py" --output text

# Single file audit with cost transparency
ai-delegate audit --file src/auth.py --show-cost

# Custom expert from plugin
# Place .ai-delegate/plugins/gdpr-expert.yaml in project root
# Then run:
ai-delegate audit --file src/user_data.py  # auto-loads GDPR expert
```

- [ ] **Step 2: Update version test**

In `tests/test_cli.py`, update `assert "0.2.0" in captured.out` (both) → `assert "0.3.0" in captured.out`

- [ ] **Step 3: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 4: Commit and push**

```bash
git add ai_delegate/__init__.py ai_delegate/cli.py README.md tests/test_cli.py
git commit -m "feat: bump version to 0.3.0 with plugin registry, memory, batch, cost transparency"
git push origin develop
```
