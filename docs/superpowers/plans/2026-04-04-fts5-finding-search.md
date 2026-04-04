# FTS5 Finding Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `findings` table and FTS5 virtual table to `memory.db` so past individual findings can be searched by text, enabling pattern discovery across analysis runs.

**Architecture:** Extend `AnalysisMemory` with two new tables — `findings` (individual finding rows linked to `analysis_runs`) and `findings_fts` (FTS5 virtual table mirroring `findings.issue_text`). Add `store_findings()` and `search_findings()` methods. The existing regression detection pipeline is untouched.

**Tech Stack:** Python `sqlite3` stdlib (FTS5 built-in since SQLite 3.9, available on all target platforms), no new dependencies.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `ai_delegate/memory.py` | Modify | Add `findings` table, FTS5 table, `store_findings()`, `search_findings()` |
| `tests/test_memory.py` | Modify | Add tests for new methods |

---

### Task 1: Add `findings` table + FTS5 schema to `_init_db()`

**Files:**

- Modify: `ai_delegate/memory.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_memory.py` inside `TestAnalysisMemory`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/test_memory.py -k "store_findings or search_findings" -v
```

Expected: `FAILED` — `AttributeError: 'AnalysisMemory' object has no attribute 'store_findings'`

- [ ] **Step 3: Add `findings` + `findings_fts` tables to `_init_db()`**

In `ai_delegate/memory.py`, update `_init_db()`:

```python
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
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_file_task ON analysis_runs (file_path, task_type)"
        )
        conn.execute("""
            CREATE TABLE IF NOT EXISTS findings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analysis_run_id INTEGER,
                task_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                issue_text TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_findings_task ON findings (task_type)"
        )
        conn.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts
            USING fts5(issue_text, severity, task_type, content=findings, content_rowid=id)
        """)
```

- [ ] **Step 4: Add `store_findings()` and `get_all_findings()` methods**

Add after `detect_regression()` in `ai_delegate/memory.py`:

```python
def store_findings(
    self,
    analysis_run_id: Optional[int],
    task_type: str,
    findings: List[Dict],
) -> None:
    """Store individual findings and update FTS5 index."""
    timestamp = datetime.utcnow().isoformat()
    with self._connect() as conn:
        for f in findings:
            cursor = conn.execute(
                """INSERT INTO findings (analysis_run_id, task_type, severity, issue_text, timestamp)
                   VALUES (?, ?, ?, ?, ?)""",
                (analysis_run_id, task_type, f.get("severity", ""), f.get("issue", ""), timestamp),
            )
            rowid = cursor.lastrowid
            conn.execute(
                "INSERT INTO findings_fts(rowid, issue_text, severity, task_type) VALUES (?, ?, ?, ?)",
                (rowid, f.get("issue", ""), f.get("severity", ""), task_type),
            )

def get_all_findings(self, task_type: Optional[str] = None) -> List[Dict]:
    """Return all stored findings, optionally filtered by task_type."""
    with self._connect() as conn:
        if task_type:
            rows = conn.execute(
                "SELECT id, analysis_run_id, task_type, severity, issue_text, timestamp FROM findings WHERE task_type = ?",
                (task_type,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, analysis_run_id, task_type, severity, issue_text, timestamp FROM findings"
            ).fetchall()
    return [
        {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
         "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
        for r in rows
    ]
```

Also add `Dict` to the imports at the top of `memory.py` (already present via `from typing import Dict, List, Optional`).

- [ ] **Step 5: Add `search_findings()` method**

Add after `get_all_findings()`:

```python
def search_findings(self, query: str, task_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
    """Full-text search across stored findings using FTS5."""
    with self._connect() as conn:
        if task_type:
            rows = conn.execute(
                """SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
                   FROM findings_fts
                   JOIN findings f ON findings_fts.rowid = f.id
                   WHERE findings_fts MATCH ? AND f.task_type = ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, task_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
                   FROM findings_fts
                   JOIN findings f ON findings_fts.rowid = f.id
                   WHERE findings_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
    return [
        {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
         "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
        for r in rows
    ]
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
uv run pytest tests/test_memory.py -k "store_findings or search_findings" -v
```

Expected: 4 PASSED

- [ ] **Step 7: Run full test suite to check no regression**

```bash
uv run pytest tests/ -q
```

Expected: all existing tests still pass

- [ ] **Step 8: Commit**

```bash
git add ai_delegate/memory.py tests/test_memory.py
git commit -m "feat: add findings table and FTS5 search to AnalysisMemory"
```

---

### Task 2: Filter search by severity

**Files:**

- Modify: `ai_delegate/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/test_memory.py`:

```python
def test_search_findings_filter_by_severity(self, memory):
    memory.store_findings(
        analysis_run_id=1,
        task_type="audit",
        findings=[
            {"severity": "critical", "issue": "SQL injection in login handler"},
            {"severity": "high",     "issue": "SQL injection in search endpoint"},
            {"severity": "medium",   "issue": "SQL query uses string format"},
        ],
    )
    results = memory.search_findings("SQL", severity="critical")
    assert len(results) == 1
    assert results[0]["severity"] == "critical"

def test_search_findings_case_insensitive(self, memory):
    memory.store_findings(
        analysis_run_id=1,
        task_type="audit",
        findings=[{"severity": "high", "issue": "XSS vulnerability in template renderer"}],
    )
    results = memory.search_findings("xss")
    assert len(results) == 1
```

- [ ] **Step 2: Run to verify failure**

```bash
uv run pytest tests/test_memory.py -k "filter_by_severity or case_insensitive" -v
```

Expected: `FAILED` — `TypeError: search_findings() got an unexpected keyword argument 'severity'`

- [ ] **Step 3: Update `search_findings()` signature**

Replace the existing `search_findings()` method in `ai_delegate/memory.py`:

```python
def search_findings(
    self,
    query: str,
    task_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 20,
) -> List[Dict]:
    """Full-text search across stored findings using FTS5."""
    conditions = ["findings_fts MATCH ?"]
    params: List = [query]

    if task_type:
        conditions.append("f.task_type = ?")
        params.append(task_type)
    if severity:
        conditions.append("f.severity = ?")
        params.append(severity)

    where = " AND ".join(conditions)
    params.append(limit)

    with self._connect() as conn:
        rows = conn.execute(
            f"""SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
               FROM findings_fts
               JOIN findings f ON findings_fts.rowid = f.id
               WHERE {where}
               ORDER BY rank
               LIMIT ?""",
            params,
        ).fetchall()
    return [
        {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
         "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
        for r in rows
    ]
```

- [ ] **Step 4: Run new tests**

```bash
uv run pytest tests/test_memory.py -k "filter_by_severity or case_insensitive" -v
```

Expected: 2 PASSED

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/memory.py tests/test_memory.py
git commit -m "feat: add severity filter and case-insensitive search to search_findings"
```

---

### Task 3: Wire `store_findings()` into `run_analysis()` in CLI

**Files:**

- Modify: `ai_delegate/cli.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write failing integration test**

Add to `tests/test_memory.py`:

```python
def test_findings_stored_after_analysis(self, memory):
    """store_findings called with correct shape produces searchable results."""
    findings = [
        {"severity": "high",   "issue": "Hardcoded secret in config.py"},
        {"severity": "medium", "issue": "Weak password hashing algorithm"},
    ]
    memory.store_findings(analysis_run_id=None, task_type="audit", findings=findings)
    results = memory.search_findings("secret")
    assert len(results) == 1
    assert "Hardcoded secret" in results[0]["issue_text"]
```

- [ ] **Step 2: Run to verify it passes already (unit test)**

```bash
uv run pytest tests/test_memory.py::TestAnalysisMemory::test_findings_stored_after_analysis -v
```

Expected: PASSED (this tests the API shape, not CLI wiring)

- [ ] **Step 3: Wire into `run_analysis()` in `cli.py`**

In `ai_delegate/cli.py`, find the memory block (inside the `try` after `memory.store(record)`):

```python
    try:
        from .memory import AnalysisMemory, MemoryRecord
        findings = result.get("findings", [])
        record = MemoryRecord(
            file_path=f"<content:{task_type}>",
            task_type=task_type,
            consensus_score=result["consensus_score"],
            finding_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity", "").lower() == "critical"),
            high_count=sum(1 for f in findings if f.get("severity", "").lower() == "high"),
            findings_summary="; ".join(f.get("issue", "")[:80] for f in findings[:10]),
        )
        memory = AnalysisMemory()
        regression = memory.detect_regression(record)
        memory.store(record)
        memory.store_findings(
            analysis_run_id=None,
            task_type=task_type,
            findings=findings,
        )
        result["regression"] = regression
    except Exception:
        pass  # Memory is non-critical
```

- [ ] **Step 4: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/cli.py tests/test_memory.py
git commit -m "feat: wire store_findings into run_analysis for automatic finding persistence"
```

---

### Task 4: Add `ai-delegate memory search` CLI subcommand

**Files:**

- Modify: `ai_delegate/cli.py`

- [ ] **Step 1: Write failing test**

Add to `tests/test_memory.py`:

```python
def test_search_findings_with_task_type_filter(self, memory):
    memory.store_findings(
        analysis_run_id=1, task_type="audit",
        findings=[{"severity": "high", "issue": "SQL injection"}],
    )
    memory.store_findings(
        analysis_run_id=2, task_type="analyze",
        findings=[{"severity": "medium", "issue": "SQL query N+1 problem"}],
    )
    results = memory.search_findings("SQL", task_type="audit")
    assert len(results) == 1
    assert results[0]["task_type"] == "audit"
```

- [ ] **Step 2: Run to verify it passes**

```bash
uv run pytest tests/test_memory.py::TestAnalysisMemory::test_search_findings_with_task_type_filter -v
```

Expected: PASSED

- [ ] **Step 3: Add `search` subparser to `main()`**

In `ai_delegate/cli.py`, add a subparser system. Replace the current `parser.add_argument("task_type", ...)` block with subcommands:

Find the section in `main()` that starts with:

```python
    parser.add_argument(
        "task_type",
        choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"],
```

Add a subparsers setup **before** it, and add a `search` subcommand. Insert this block right after `parser = argparse.ArgumentParser(...)` definition but before `parser.add_argument("--version"`:

```python
    subparsers = parser.add_subparsers(dest="subcommand")

    # --- search subcommand ---
    search_parser = subparsers.add_parser(
        "search", help="Search past findings in memory"
    )
    search_parser.add_argument("query", help="Text to search for in past findings")
    search_parser.add_argument(
        "--task-type", choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"],
        help="Filter by task type"
    )
    search_parser.add_argument(
        "--severity", choices=["critical", "high", "medium", "low", "info"],
        help="Filter by severity"
    )
    search_parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
```

Then at the top of the `args = parser.parse_args()` processing section, add the search dispatch **before** the content reading block:

```python
    args = parser.parse_args()

    # Dispatch search subcommand
    if args.subcommand == "search":
        from .memory import AnalysisMemory
        memory = AnalysisMemory()
        results = memory.search_findings(
            query=args.query,
            task_type=getattr(args, "task_type", None),
            severity=getattr(args, "severity", None),
            limit=args.limit,
        )
        if not results:
            print("No findings matched.")
        else:
            for r in results:
                print(f"[{r['severity'].upper()}] ({r['task_type']}) {r['issue_text']}")
        return
```

- [ ] **Step 4: Smoke test the CLI**

```bash
echo "test" | uv run python -m ai_delegate.cli audit --help
uv run python -m ai_delegate.cli search --help
```

Expected: help text shows `search` subcommand with `query`, `--task-type`, `--severity`, `--limit`

- [ ] **Step 5: Run full test suite**

```bash
uv run pytest tests/ -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/cli.py
git commit -m "feat: add 'ai-delegate search' CLI subcommand for FTS5 finding search"
```

---

## Self-Review

**Spec coverage:**

- ✅ `findings` table linked to `analysis_runs`
- ✅ FTS5 virtual table `findings_fts`
- ✅ `store_findings()` method
- ✅ `search_findings()` with text, task_type, severity filters
- ✅ Auto-persist findings on every `run_analysis()` call
- ✅ CLI `search` subcommand

**Placeholder scan:** None found — all steps have concrete code.

**Type consistency:**

- `store_findings(analysis_run_id, task_type, findings)` — consistent across Tasks 1, 2, 3
- `search_findings(query, task_type, severity, limit)` — consistent across Tasks 1, 2, 4
- Return type `List[Dict]` — consistent in `get_all_findings()` and `search_findings()`
