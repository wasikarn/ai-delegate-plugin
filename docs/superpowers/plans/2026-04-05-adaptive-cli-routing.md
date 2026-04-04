# Adaptive CLI Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `ai-delegate` learn which CLI performs best per task type and auto-route accordingly, with health monitoring and user feedback loop.

**Architecture:** Three-phase adaptive routing (priors → streak correction → win-rate override) lives in `SmartRouter.select_cli_for_task()`. Performance data persists in SQLite (`cli_performance` table). An in-memory `CliHealthMonitor` gates degraded CLIs before any routing logic runs.

**Tech Stack:** Python 3.10+, SQLite (via `sqlite3`), `subprocess`, `argparse`, `pytest`

---

## File Map

| File | Change |
|------|--------|
| `ai_delegate/constants.py` | Add `AdaptiveConfig`, `HealthConfig` classes + `CLI_PRIORS` dict |
| `ai_delegate/memory.py` | Schema migration: add `cli_name`/`user_rating` columns + `cli_performance` table + 4 new methods; `store()` now returns `int` |
| `ai_delegate/client.py` | Fix `CLIExecutor.execute()` stdin support; fix `_run_ollama()` stdin bug; add `_run_codex()`, `_run_gemini()`; add `cli_type` dispatch + `on_cli_error` callback |
| `ai_delegate/router.py` | Add `CliHealthMonitor` class; update `SmartRouter` with 3-phase `select_cli_for_task()` |
| `ai_delegate/cli.py` | Wire adaptive routing into `run_analysis()`; add `--no-adaptive`, `--no-rating` flags; inline rating prompt; `rate` subcommand |
| `tests/test_memory.py` | Tests for 4 new memory methods |
| `tests/test_router.py` | Tests for `CliHealthMonitor` TTL + 3-phase routing |
| `tests/test_client.py` | Tests for stdin fix, `_run_codex()`, `_run_gemini()`, error classification |
| `tests/test_cli.py` | Tests for rating prompt, `rate` subcommand, `--no-adaptive` flag |

---

## Task 1: Add AdaptiveConfig, HealthConfig, CLI_PRIORS to constants.py

**Files:**

- Modify: `ai_delegate/constants.py`

- [ ] **Step 1: Add the three new exports at the bottom of constants.py**

```python
# =============================================================================
# Adaptive Routing Configuration
# =============================================================================

class AdaptiveConfig:
    """Constants for the adaptive CLI routing algorithm."""
    STREAK_WINDOW              = 3     # consecutive runs to trigger streak lock/skip
    MIN_RUNS_BEFORE_OVERRIDE   = 10    # Phase 3 gate (rated runs only)
    WIN_RATE_DELTA_THRESHOLD   = 0.15  # 15 percentage points for permanent override
    ANTI_THRASH_WINDOW         = 3     # look-back window for oscillation detection
    ANTI_THRASH_DISTINCT_LIMIT = 3     # ≥3 distinct CLIs in window = thrashing


class HealthConfig:
    """TTL constants (seconds) for CLI health degradation."""
    RATE_LIMIT_TTL = 300.0      # 5 min burst window
    NETWORK_TTL    = 60.0       # 1 min transient blip
    AUTH_TTL       = float("inf")  # indefinite — needs user intervention


# CLI_PRIORS: pre-seeded win rates stored as virtual runs at _init_db() time.
# win_rate=0.80 → win_count=8, loss_count=2, run_count=10
CLI_PRIORS: Dict[str, Dict[str, float]] = {
    "codex":  {"architecture": 0.80, "refactor": 0.75, "migrate": 0.75},
    "claude": {"audit": 0.80, "analyze": 0.75, "review": 0.75},
    "ollama": {"audit": 0.70, "analyze": 0.70, "architecture": 0.65,
               "review": 0.70, "refactor": 0.65, "migrate": 0.65},
    "gemini": {"audit": 0.65, "analyze": 0.70, "architecture": 0.65,
               "review": 0.70, "refactor": 0.65, "migrate": 0.65},
}
```

- [ ] **Step 2: Verify the import works**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
python -c "from ai_delegate.constants import AdaptiveConfig, HealthConfig, CLI_PRIORS; print(CLI_PRIORS['codex'])"
```

Expected: `{'architecture': 0.8, 'refactor': 0.75, 'migrate': 0.75}`

- [ ] **Step 3: Commit**

```bash
git add ai_delegate/constants.py
git commit -m "feat: add AdaptiveConfig, HealthConfig, CLI_PRIORS to constants"
```

---

## Task 2: Extend AnalysisMemory — schema + 4 new methods

**Files:**

- Modify: `ai_delegate/memory.py`
- Modify: `tests/test_memory.py`

- [ ] **Step 1: Write the failing tests first**

Add to `tests/test_memory.py`:

```python
from ai_delegate.constants import CLI_PRIORS


class TestCliPerformanceMethods:
    @pytest.fixture
    def memory(self, tmp_path):
        db_path = tmp_path / "test_memory.db"
        return AnalysisMemory(db_path=db_path)

    def test_store_returns_run_id(self, memory):
        record = MemoryRecord(
            file_path="src/auth.py", task_type="audit",
            consensus_score=0.75, finding_count=2,
            critical_count=0, high_count=2,
            findings_summary="Issue A",
        )
        run_id = memory.store(record)
        assert isinstance(run_id, int)
        assert run_id >= 1

    def test_record_cli_run(self, memory):
        record = MemoryRecord(
            file_path="src/auth.py", task_type="audit",
            consensus_score=0.75, finding_count=2,
            critical_count=0, high_count=2, findings_summary="X",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        with memory._connect() as conn:
            row = conn.execute(
                "SELECT cli_name FROM analysis_runs WHERE id = ?", (run_id,)
            ).fetchone()
        assert row[0] == "ollama"

    def test_store_rating_updates_cli_performance(self, memory):
        record = MemoryRecord(
            file_path="src/auth.py", task_type="audit",
            consensus_score=0.75, finding_count=2,
            critical_count=0, high_count=2, findings_summary="X",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        memory.store_rating(run_id, 1)  # win
        perf = memory.get_cli_performance("audit")
        ollama_perf = next(p for p in perf if p["cli_name"] == "ollama")
        # Prior win_count=7 (0.70 * 10) + 1 new win = 8
        assert ollama_perf["win_count"] >= 8
        assert ollama_perf["win_rate"] > 0.0

    def test_store_rating_loss_decrements(self, memory):
        record = MemoryRecord(
            file_path="src/auth.py", task_type="audit",
            consensus_score=0.75, finding_count=2,
            critical_count=0, high_count=2, findings_summary="X",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, "ollama")
        memory.store_rating(run_id, 0)  # loss
        perf = memory.get_cli_performance("audit")
        ollama_perf = next(p for p in perf if p["cli_name"] == "ollama")
        # Prior loss_count=3 (0.30 * 10) + 1 new loss = 4
        assert ollama_perf["loss_count"] >= 4

    def test_get_cli_performance_returns_all_seeded_clis(self, memory):
        perf = memory.get_cli_performance("audit")
        cli_names = {p["cli_name"] for p in perf}
        assert "ollama" in cli_names
        assert "claude" in cli_names

    def test_get_cli_performance_ordered_by_win_rate(self, memory):
        perf = memory.get_cli_performance("audit")
        win_rates = [p["win_rate"] for p in perf]
        assert win_rates == sorted(win_rates, reverse=True)

    def test_get_cli_performance_dict_keys(self, memory):
        perf = memory.get_cli_performance("audit")
        assert len(perf) > 0
        row = perf[0]
        assert "cli_name" in row
        assert "win_rate" in row
        assert "win_count" in row
        assert "loss_count" in row
        assert "run_count" in row
        assert "last_updated" in row

    def test_get_recent_cli_runs_newest_first(self, memory):
        for cli in ["ollama", "gemini", "codex"]:
            record = MemoryRecord(
                file_path="src/auth.py", task_type="audit",
                consensus_score=0.75, finding_count=2,
                critical_count=0, high_count=2, findings_summary="X",
            )
            run_id = memory.store(record)
            memory.record_cli_run(run_id, cli)
        recent = memory.get_recent_cli_runs("audit", limit=3)
        assert recent == ["codex", "gemini", "ollama"]  # newest first

    def test_get_recent_cli_runs_limit(self, memory):
        for cli in ["ollama", "gemini", "codex", "ollama", "gemini"]:
            record = MemoryRecord(
                file_path="src/auth.py", task_type="audit",
                consensus_score=0.75, finding_count=2,
                critical_count=0, high_count=2, findings_summary="X",
            )
            run_id = memory.store(record)
            memory.record_cli_run(run_id, cli)
        recent = memory.get_recent_cli_runs("audit", limit=3)
        assert len(recent) == 3

    def test_get_recent_cli_runs_only_rows_with_cli_name(self, memory):
        # Runs without cli_name should not appear in recent runs
        record = MemoryRecord(
            file_path="src/auth.py", task_type="audit",
            consensus_score=0.75, finding_count=2,
            critical_count=0, high_count=2, findings_summary="X",
        )
        memory.store(record)  # no record_cli_run called
        recent = memory.get_recent_cli_runs("audit", limit=3)
        assert len(recent) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_memory.py::TestCliPerformanceMethods -v 2>&1 | head -30
```

Expected: FAIL — `store()` returns `None`, methods don't exist yet.

- [ ] **Step 3: Implement the schema changes and new methods in memory.py**

In `_init_db()`, after the existing `CREATE TABLE` and index statements, add:

```python
# Adaptive routing columns (backward-compatible migrations)
conn.execute(
    "ALTER TABLE analysis_runs ADD COLUMN cli_name TEXT"
) if not self._column_exists(conn, "analysis_runs", "cli_name") else None
conn.execute(
    "ALTER TABLE analysis_runs ADD COLUMN user_rating INTEGER"
) if not self._column_exists(conn, "analysis_runs", "user_rating") else None
conn.execute(
    "CREATE INDEX IF NOT EXISTS idx_cli_task ON analysis_runs (cli_name, task_type)"
)

conn.execute("""
    CREATE TABLE IF NOT EXISTS cli_performance (
        cli_name     TEXT NOT NULL,
        task_type    TEXT NOT NULL,
        run_count    INTEGER NOT NULL DEFAULT 0,
        win_count    INTEGER NOT NULL DEFAULT 0,
        loss_count   INTEGER NOT NULL DEFAULT 0,
        win_rate     REAL NOT NULL DEFAULT 0.0,
        last_updated TEXT NOT NULL,
        PRIMARY KEY (cli_name, task_type)
    )
""")
self._seed_cli_priors(conn)
```

Add helper method `_column_exists()`:

```python
def _column_exists(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)
```

Add helper method `_seed_cli_priors()`:

```python
def _seed_cli_priors(self, conn: sqlite3.Connection) -> None:
    """Seed cli_performance with CLI_PRIORS if rows don't exist yet."""
    from .constants import CLI_PRIORS
    timestamp = datetime.utcnow().isoformat()
    for cli_name, task_rates in CLI_PRIORS.items():
        for task_type, win_rate in task_rates.items():
            existing = conn.execute(
                "SELECT 1 FROM cli_performance WHERE cli_name = ? AND task_type = ?",
                (cli_name, task_type),
            ).fetchone()
            if existing:
                continue
            # win_rate=0.80 → 8 wins, 2 losses out of 10 virtual runs
            virtual_runs = 10
            win_count = round(win_rate * virtual_runs)
            loss_count = virtual_runs - win_count
            conn.execute(
                """INSERT INTO cli_performance
                   (cli_name, task_type, run_count, win_count, loss_count, win_rate, last_updated)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (cli_name, task_type, virtual_runs, win_count, loss_count, win_rate, timestamp),
            )
```

Update `store()` to return the row id:

```python
def store(self, record: MemoryRecord) -> int:
    with self._connect() as conn:
        cursor = conn.execute(
            """INSERT INTO analysis_runs
               (file_path, task_type, consensus_score, finding_count,
                critical_count, high_count, findings_summary, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record.file_path, record.task_type, record.consensus_score,
                record.finding_count, record.critical_count, record.high_count,
                record.findings_summary, record.timestamp,
            ),
        )
        return cursor.lastrowid
```

Add the 4 new methods:

```python
def record_cli_run(self, run_id: int, cli_name: str) -> None:
    """Backfill cli_name into analysis_runs after a run completes."""
    with self._connect() as conn:
        conn.execute(
            "UPDATE analysis_runs SET cli_name = ? WHERE id = ?",
            (cli_name, run_id),
        )

def store_rating(self, run_id: int, rating: int) -> None:
    """Store binary rating (0/1) and incrementally update cli_performance."""
    with self._connect() as conn:
        row = conn.execute(
            "SELECT cli_name, task_type FROM analysis_runs WHERE id = ?",
            (run_id,),
        ).fetchone()
        if not row or not row[0]:
            return
        cli_name, task_type = row
        conn.execute(
            "UPDATE analysis_runs SET user_rating = ? WHERE id = ?",
            (rating, run_id),
        )
        timestamp = datetime.utcnow().isoformat()
        if rating == 1:
            conn.execute(
                """UPDATE cli_performance
                   SET win_count = win_count + 1,
                       run_count = run_count + 1,
                       win_rate = CAST(win_count + 1 AS REAL) / (win_count + loss_count + 1),
                       last_updated = ?
                   WHERE cli_name = ? AND task_type = ?""",
                (timestamp, cli_name, task_type),
            )
        else:
            conn.execute(
                """UPDATE cli_performance
                   SET loss_count = loss_count + 1,
                       run_count = run_count + 1,
                       win_rate = CAST(win_count AS REAL) / (win_count + loss_count + 1),
                       last_updated = ?
                   WHERE cli_name = ? AND task_type = ?""",
                (timestamp, cli_name, task_type),
            )
        # Upsert if row doesn't exist (CLI not in priors)
        conn.execute(
            """INSERT OR IGNORE INTO cli_performance
               (cli_name, task_type, run_count, win_count, loss_count, win_rate, last_updated)
               VALUES (?, ?, 1, ?, ?, ?, ?)""",
            (cli_name, task_type,
             1 if rating == 1 else 0,
             0 if rating == 1 else 1,
             float(rating), timestamp),
        )

def get_cli_performance(self, task_type: str) -> List[Dict]:
    """Return all cli_performance rows for a task_type, ordered by win_rate DESC."""
    with self._connect() as conn:
        rows = conn.execute(
            """SELECT cli_name, win_rate, win_count, loss_count, run_count, last_updated
               FROM cli_performance WHERE task_type = ?
               ORDER BY win_rate DESC""",
            (task_type,),
        ).fetchall()
    return [
        {
            "cli_name": r[0], "win_rate": r[1], "win_count": r[2],
            "loss_count": r[3], "run_count": r[4], "last_updated": r[5],
        }
        for r in rows
    ]

def get_recent_cli_runs(self, task_type: str, limit: int = 3) -> List[str]:
    """Return cli_name of last N runs for task_type (newest first).
    Only includes rows where cli_name is set."""
    with self._connect() as conn:
        rows = conn.execute(
            """SELECT cli_name FROM analysis_runs
               WHERE task_type = ? AND cli_name IS NOT NULL
               ORDER BY id DESC LIMIT ?""",
            (task_type, limit),
        ).fetchall()
    return [r[0] for r in rows]
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_memory.py -v
```

Expected: All tests pass (including existing ones — `store()` returning `int` doesn't break anything since callers ignored the `None` return).

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/memory.py tests/test_memory.py
git commit -m "feat: extend AnalysisMemory with cli_performance table and adaptive routing methods"
```

---

## Task 3: Fix _run_ollama() stdin bug + add _run_codex() + _run_gemini()

**Files:**

- Modify: `ai_delegate/client.py`
- Modify: `tests/test_client.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_client.py`:

```python
class TestCLIExecutorStdin:
    @patch("ai_delegate.client.subprocess.run")
    def test_execute_passes_input_to_subprocess(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        executor = CLIExecutor()
        executor.execute(["ollama", "run", "model"], input="my prompt\n")
        _, kwargs = mock_run.call_args
        assert kwargs.get("input") == "my prompt\n"

    @patch("ai_delegate.client.subprocess.run")
    def test_execute_without_input_passes_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        executor = CLIExecutor()
        executor.execute(["echo", "hello"])
        _, kwargs = mock_run.call_args
        assert kwargs.get("input") is None


class TestRunOllamaStdinFix:
    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_uses_stdin_not_arg(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"findings": []}', stderr="")
        client = OllamaClient(model="glm-5:cloud")
        client.run("my prompt", json_output=False)
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        # Prompt must NOT be in cmd args
        assert "my prompt" not in cmd
        # Must be passed via stdin
        assert call_args[1].get("input") is not None

    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_json_format_uses_two_args(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"findings": []}', stderr="")
        client = OllamaClient(model="glm-5:cloud")
        client.run("my prompt", json_output=True)
        cmd = mock_run.call_args[0][0]
        # --format json must appear as two consecutive args
        assert "--format" in cmd
        fmt_idx = cmd.index("--format")
        assert cmd[fmt_idx + 1] == "json"


class TestRunCodex:
    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_run_codex_uses_exec_full_auto(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="analysis result", stderr="")
        client = OllamaClient(model="glm-5:cloud", cli_type="codex")
        client.run("analyze this", json_output=False)
        cmd = mock_run.call_args[0][0]
        assert "codex" in cmd
        assert "exec" in cmd
        assert "--full-auto" in cmd

    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_run_codex_passes_prompt_via_stdin(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        client = OllamaClient(model="o3-mini", cli_type="codex")
        client.run("my prompt", json_output=False)
        assert mock_run.call_args[1].get("input") == "my prompt"


class TestRunGemini:
    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_run_gemini_uses_yolo_flag(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='{"findings": []}', stderr="")
        client = OllamaClient(model="gemini-2.0-flash", cli_type="gemini")
        client.run("analyze", json_output=False)
        cmd = mock_run.call_args[0][0]
        assert "gemini" in cmd
        assert "--yolo" in cmd

    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_run_gemini_uses_p_flag(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        client = OllamaClient(model="gemini-2.0-flash", cli_type="gemini")
        client.run("my prompt", json_output=False)
        cmd = mock_run.call_args[0][0]
        assert "-p" in cmd
        p_idx = cmd.index("-p")
        assert cmd[p_idx + 1] == "my prompt"


class TestErrorClassification:
    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_on_cli_error_called_on_rate_limit(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="429 rate limit exceeded"
        )
        error_calls = []
        client = OllamaClient(
            model="glm-5:cloud",
            max_retries=1,
            on_cli_error=lambda cli, etype: error_calls.append((cli, etype)),
        )
        with pytest.raises(Exception):
            client.run("prompt")
        assert any(etype == "rate_limit" for _, etype in error_calls)

    @patch("ai_delegate.client.subprocess.run")
    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_on_cli_error_called_on_auth_error(self, mock_which, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="401 unauthorized"
        )
        error_calls = []
        client = OllamaClient(
            model="glm-5:cloud",
            max_retries=1,
            on_cli_error=lambda cli, etype: error_calls.append((cli, etype)),
        )
        with pytest.raises(Exception):
            client.run("prompt")
        assert any(etype == "auth" for _, etype in error_calls)
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_client.py::TestCLIExecutorStdin tests/test_client.py::TestRunOllamaStdinFix tests/test_client.py::TestRunCodex tests/test_client.py::TestRunGemini tests/test_client.py::TestErrorClassification -v 2>&1 | head -40
```

Expected: FAIL.

- [ ] **Step 3: Fix CLIExecutor.execute() to accept input parameter**

In `ai_delegate/client.py`, update `CLIExecutor.execute()`:

```python
def execute(
    self,
    cmd: List[str],
    timeout: int = RetryConfig.API_TIMEOUT,
    input: Optional[str] = None,
) -> str:
    """
    Execute command and return stdout.

    Args:
        cmd: Command and arguments as list
        timeout: Timeout in seconds
        input: Optional stdin input string

    Returns:
        stdout from command

    Raises:
        RuntimeError: If command fails or times out
    """
    if self.verbose:
        logger.info(f"Running: {' '.join(cmd[:3])}...")

    try:
        result = subprocess.run(
            cmd,
            input=input,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            raise RuntimeError(f"Command failed: {result.stderr}")

        return result.stdout

    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Command timed out after {timeout}s")
```

- [ ] **Step 4: Add _classify_cli_error() helper and update OllamaClient**

Add at the module level (before OllamaClient):

```python
def _classify_cli_error(error_text: str) -> Optional[str]:
    """Classify CLI error for health monitoring.

    Returns:
        'rate_limit', 'auth', 'network', or None if unclassified.
    """
    text = error_text.lower()
    if any(s in text for s in ["429", "rate limit", "too many requests", "usage limit"]):
        return "rate_limit"
    if any(s in text for s in ["401", "unauthorized", "authentication", "forbidden"]):
        return "auth"
    if any(s in text for s in ["econnrefused", "timeout", "network", "connection refused"]):
        return "network"
    return None
```

Add `cli_type: str = "ollama"` and `on_cli_error: Optional[Callable[[str, str], None]] = None` to `OllamaClient.__init__()`:

```python
def __init__(
    self,
    model: str = Models.KIMI_K25_CLOUD,
    fallback_model: str = Models.CLAUDE_SONNET,
    max_retries: int = RetryConfig.MAX_RETRIES,
    initial_retry_delay: float = RetryConfig.INITIAL_DELAY,
    verbose: bool = False,
    strict_validation: bool = False,
    cli_type: str = "ollama",                                   # NEW
    on_cli_error: Optional[Callable[[str, str], None]] = None, # NEW
    # Dependency injection for testing
    executor: Optional[CLIExecutor] = None,
    rate_limiter: Optional[RateLimiter] = None,
    output_processor: Optional[OutputProcessor] = None,
    response_parser: Optional[ResponseParser] = None,
):
    ...
    self.cli_type = cli_type          # NEW
    self.on_cli_error = on_cli_error  # NEW
```

Update `run()` to dispatch by `cli_type` and classify errors:

```python
def run(self, prompt: str, json_output: bool = True) -> str:
    # Validate prompt
    validation_result = validate_prompt(prompt, strict=self.strict_validation)
    if not validation_result.valid:
        raise ValueError(f"Invalid prompt: {validation_result.error}")
    effective_prompt = validation_result.sanitized if validation_result.sanitized else prompt
    if validation_result.warning:
        logger.warning(f"Prompt validation warning: {validation_result.warning}")

    # Dispatch based on CLI type
    if self.cli_type == "codex":
        return self._run_with_error_handling(
            lambda: self._run_codex(effective_prompt), "codex"
        )
    elif self.cli_type == "gemini":
        return self._run_with_error_handling(
            lambda: self._run_gemini(effective_prompt, json_output), "gemini"
        )
    elif self.cli_type == "claude":
        return self._run_with_error_handling(
            lambda: self._run_fallback(effective_prompt), "claude"
        )
    else:  # ollama (default)
        try:
            return self.rate_limiter.execute_with_retry(
                operation=lambda: self._run_ollama(effective_prompt, json_output),
                on_rate_limit=lambda e: logger.warning("Rate limited, retrying..."),
            )
        except RateLimitError:
            logger.warning("Max retries exceeded — falling back to Claude")
            return self._run_fallback(effective_prompt)
```

Add `_run_with_error_handling()` helper:

```python
def _run_with_error_handling(self, fn: Callable[[], str], cli_name: str) -> str:
    """Run fn, classify errors, and invoke on_cli_error callback if set."""
    try:
        return fn()
    except RuntimeError as e:
        error_type = _classify_cli_error(str(e))
        if error_type and self.on_cli_error:
            self.on_cli_error(cli_name, error_type)
        raise
```

- [ ] **Step 5: Fix _run_ollama() stdin bug**

Replace the existing `_run_ollama()` method:

```python
def _run_ollama(self, prompt: str, json_output: bool) -> str:
    """Execute Ollama command via stdin (not prompt-as-arg)."""
    cmd = ["ollama", "run", self.model, "--nowordwrap"]
    if json_output:
        cmd.extend(["--format", "json"])

    try:
        output = self.executor.execute(cmd, input=prompt + "\n")
        rate_limit_error = self.rate_limiter.detect_rate_limit(output)
        if rate_limit_error:
            raise rate_limit_error
        return self.output_processor.process(output)
    except RuntimeError as e:
        rate_limit_error = self.rate_limiter.detect_rate_limit(str(e))
        if rate_limit_error:
            error_type = _classify_cli_error(str(e))
            if error_type and self.on_cli_error:
                self.on_cli_error("ollama", error_type)
            raise rate_limit_error
        raise
```

- [ ] **Step 6: Add _run_codex() method**

```python
def _run_codex(self, prompt: str) -> str:
    """Execute Codex CLI non-interactively via stdin."""
    model = self.model if self.model in ("o3-mini", "gpt-4o") else "o3-mini"
    cmd = ["codex", "exec", "--full-auto", "-m", model]
    output = self.executor.execute(cmd, input=prompt)
    return self.output_processor.process(output)
```

- [ ] **Step 7: Add _run_gemini() method**

```python
def _run_gemini(self, prompt: str, json_output: bool) -> str:
    """Execute Gemini CLI non-interactively."""
    model = self.model if "gemini" in self.model else "gemini-2.0-flash"
    cmd = ["gemini", "-p", prompt, "-m", model, "--yolo"]
    if json_output:
        cmd.extend(["-o", "json"])
    output = self.executor.execute(cmd)
    return self.output_processor.process(output)
```

- [ ] **Step 8: Run all client tests**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_client.py -v
```

Expected: All pass.

- [ ] **Step 9: Commit**

```bash
git add ai_delegate/client.py tests/test_client.py
git commit -m "feat: fix ollama stdin bug, add codex/gemini runners, error classification"
```

---

## Task 4: Add CliHealthMonitor to router.py

**Files:**

- Modify: `ai_delegate/router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_router.py`:

```python
import time
from ai_delegate.router import CliHealthMonitor, CLIType, SmartRouter
from ai_delegate.constants import HealthConfig


class TestCliHealthMonitor:
    def test_new_cli_is_not_degraded(self):
        monitor = CliHealthMonitor()
        assert not monitor.is_degraded(CLIType.OLLAMA)

    def test_mark_failed_degrades_cli(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.OLLAMA, "rate_limit")
        assert monitor.is_degraded(CLIType.OLLAMA)

    def test_rate_limit_ttl_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "rate_limit")
        assert monitor.is_degraded(CLIType.CODEX)
        # Manually expire by backdating the timestamp
        monitor._degraded[CLIType.CODEX] = (
            time.monotonic() - HealthConfig.RATE_LIMIT_TTL - 1,
            "rate_limit",
        )
        assert not monitor.is_degraded(CLIType.CODEX)

    def test_auth_degradation_never_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.GEMINI, "auth")
        # Backdate far in the past — should still be degraded
        monitor._degraded[CLIType.GEMINI] = (
            time.monotonic() - 10_000,
            "auth",
        )
        assert monitor.is_degraded(CLIType.GEMINI)

    def test_network_ttl_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CLAUDE, "network")
        monitor._degraded[CLIType.CLAUDE] = (
            time.monotonic() - HealthConfig.NETWORK_TTL - 1,
            "network",
        )
        assert not monitor.is_degraded(CLIType.CLAUDE)

    def test_clear_removes_degraded_state(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.OLLAMA, "auth")
        assert monitor.is_degraded(CLIType.OLLAMA)
        monitor.clear(CLIType.OLLAMA)
        assert not monitor.is_degraded(CLIType.OLLAMA)

    def test_clear_nonexistent_cli_is_noop(self):
        monitor = CliHealthMonitor()
        monitor.clear(CLIType.OLLAMA)  # Should not raise

    def test_should_warn_auth_first_time(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "auth")
        assert monitor.should_warn_auth(CLIType.CODEX)

    def test_should_warn_auth_only_once(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "auth")
        monitor.should_warn_auth(CLIType.CODEX)  # consume first warning
        assert not monitor.should_warn_auth(CLIType.CODEX)


class TestSmartRouterHealthGate:
    @patch("ai_delegate.router.shutil.which")
    def test_degraded_cli_is_skipped_in_routing(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"  # all available
        router = SmartRouter()
        router.health_monitor.mark_failed(CLIType.OLLAMA, "auth")
        # Ollama is degraded → should fall through to next CLI (gemini)
        config, model = router.select_cli_for_task("audit")
        assert config.cli_type != CLIType.OLLAMA

    @patch("ai_delegate.router.shutil.which")
    def test_all_degraded_raises_runtime_error(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"
        router = SmartRouter()
        for cli in CLIType:
            router.health_monitor.mark_failed(cli, "auth")
        with pytest.raises(RuntimeError, match="No AI CLI available"):
            router.select_cli_for_task("audit")
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_router.py::TestCliHealthMonitor tests/test_router.py::TestSmartRouterHealthGate -v 2>&1 | head -30
```

Expected: FAIL — `CliHealthMonitor` doesn't exist yet.

- [ ] **Step 3: Add CliHealthMonitor class to router.py**

Add to `router.py` imports:

```python
import time
from typing import Dict, List, Optional, Tuple, Set
```

Add `CliHealthMonitor` class before `SmartRouter`:

```python
class CliHealthMonitor:
    """In-memory CLI health tracker. Fresh per session, zero I/O on healthy runs."""

    _TTL: Dict[str, float] = {
        "rate_limit": HealthConfig.RATE_LIMIT_TTL,
        "network":    HealthConfig.NETWORK_TTL,
        "auth":       HealthConfig.AUTH_TTL,
    }

    def __init__(self) -> None:
        self._degraded: Dict[CLIType, Tuple[float, str]] = {}
        self._auth_warned: Set[CLIType] = set()

    def mark_failed(self, cli: CLIType, error_type: str) -> None:
        """Mark CLI as degraded. error_type: 'rate_limit' | 'auth' | 'network'"""
        if isinstance(cli, str):
            try:
                cli = CLIType(cli)
            except ValueError:
                return
        self._degraded[cli] = (time.monotonic(), error_type)

    def is_degraded(self, cli: CLIType) -> bool:
        """Returns True if CLI is within its TTL window."""
        if cli not in self._degraded:
            return False
        failed_at, error_type = self._degraded[cli]
        ttl = self._TTL.get(error_type, 60.0)
        if ttl == float("inf"):
            return True
        if time.monotonic() - failed_at > ttl:
            del self._degraded[cli]
            return False
        return True

    def should_warn_auth(self, cli: CLIType) -> bool:
        """Returns True once per session for auth-degraded CLIs (print warning once)."""
        if cli in self._auth_warned:
            return False
        self._auth_warned.add(cli)
        return True

    def clear(self, cli: CLIType) -> None:
        """Manually clear degraded state (e.g., after user fixes auth)."""
        self._degraded.pop(cli, None)
        self._auth_warned.discard(cli)
```

Update `router.py` imports to include `HealthConfig`:

```python
from .constants import (
    Models,
    TokenLimits,
    ComplexityThresholds,
    QualityThresholds,
    RetryConfig,
    CLIPriority,
    TaskTypes,
    OLLAMA_MODELS,
    GEMINI_MODELS,
    CODEX_MODELS,
    CLAUDE_MODELS,
    GLM_MODELS,
    CLI_STRENGTHS,
    FALLBACK_MODEL,
    HealthConfig,      # NEW
)
```

Update `SmartRouter.__init__()` to create a `health_monitor`:

```python
def __init__(self):
    """Initialize router and detect available CLIs."""
    self._available_clis: Dict[CLIType, bool] = {}
    self.health_monitor = CliHealthMonitor()   # NEW
    self._detect_clis()
```

Update `select_cli_for_task()` to add health gate (Step 0) — replace the existing availability check:

```python
def select_cli_for_task(
    self,
    task_type: str,
    prefer_structured_output: bool = True,
) -> Tuple[CLIConfig, str]:
    ...
    # Step 0: Health gate — filter out degraded CLIs
    for cli_type, config in priority_order:
        if not self.is_available(cli_type):
            continue
        if self.health_monitor.is_degraded(cli_type):
            # Warn once per session for auth errors
            failed_state = self.health_monitor._degraded.get(cli_type)
            if failed_state and failed_state[1] == "auth":
                if self.health_monitor.should_warn_auth(cli_type):
                    logger.warning(
                        f"⚠ {cli_type.value} unavailable (auth error) — skipping"
                    )
            continue
        ...rest of existing logic...
```

- [ ] **Step 4: Run tests**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_router.py -v
```

Expected: All tests pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/router.py tests/test_router.py
git commit -m "feat: add CliHealthMonitor to SmartRouter with TTL-based degradation"
```

---

## Task 5: Implement 3-phase adaptive routing in SmartRouter

**Files:**

- Modify: `ai_delegate/router.py`
- Modify: `tests/test_router.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_router.py`:

```python
import tempfile
from pathlib import Path
from ai_delegate.memory import AnalysisMemory, MemoryRecord
from ai_delegate.constants import AdaptiveConfig


class TestAdaptiveRouting:
    @pytest.fixture
    def memory(self, tmp_path):
        return AnalysisMemory(db_path=tmp_path / "test.db")

    @pytest.fixture
    def router(self):
        with patch("ai_delegate.router.shutil.which", return_value="/usr/bin/tool"):
            return SmartRouter()

    def _add_run(self, memory, task_type, cli_name):
        """Helper: add a run record with cli_name."""
        record = MemoryRecord(
            file_path="src/x.py", task_type=task_type,
            consensus_score=0.75, finding_count=1,
            critical_count=0, high_count=1, findings_summary="X",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, cli_name)
        return run_id

    def test_no_adaptive_uses_static_priority(self, router, memory):
        """--no-adaptive always returns the static priority CLI."""
        config, _ = router.select_cli_for_task(
            "audit", memory=memory, no_adaptive=True
        )
        # Static priority for audit: ollama first
        assert config.cli_type == CLIType.OLLAMA

    def test_phase1_priors_select_higher_win_rate(self, router, memory):
        """Phase 1: cli_performance priors sort CLIs by win_rate."""
        # Claude prior for audit = 0.80, ollama = 0.70
        config, _ = router.select_cli_for_task("audit", memory=memory)
        # Claude should win (0.80 > 0.70)
        assert config.cli_type == CLIType.CLAUDE

    def test_phase2_winning_streak_locks_cli(self, router, memory):
        """Phase 2: 3 consecutive same-CLI runs → lock that CLI."""
        for _ in range(3):
            self._add_run(memory, "refactor", "ollama")
        config, _ = router.select_cli_for_task("refactor", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_phase2_losing_streak_skips_current_best(self, router, memory):
        """Phase 2: current_best not in last 3 runs → skip to next."""
        # Last 3 runs were gemini (codex has highest win_rate for architecture via priors)
        for _ in range(3):
            self._add_run(memory, "architecture", "gemini")
        # codex is current_best for architecture (prior 0.80) but wasn't used → skip
        config, _ = router.select_cli_for_task("architecture", memory=memory)
        assert config.cli_type != CLIType.CODEX

    def test_anti_thrash_guard_holds_static(self, router, memory):
        """Anti-thrash: ≥3 distinct CLIs in last 3 runs → use static priority."""
        self._add_run(memory, "audit", "ollama")
        self._add_run(memory, "audit", "gemini")
        self._add_run(memory, "audit", "codex")
        # 3 distinct CLIs → hold static (ollama for audit per _task_priority_map)
        config, _ = router.select_cli_for_task("audit", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_phase3_win_rate_override(self, router, memory):
        """Phase 3: win_rate delta ≥15pp after 10+ rated runs → override."""
        # Give ollama 15 wins for audit (run_count reaches threshold)
        for _ in range(15):
            run_id = self._add_run(memory, "audit", "ollama")
            memory.store_rating(run_id, 1)  # all wins
        # Give claude 5 losses for audit
        for _ in range(5):
            run_id = self._add_run(memory, "audit", "claude")
            memory.store_rating(run_id, 0)
        config, _ = router.select_cli_for_task("audit", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_no_memory_uses_static_priority(self, router):
        """Without memory, falls back to static priority."""
        config, _ = router.select_cli_for_task("audit")
        assert config.cli_type == CLIType.OLLAMA
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_router.py::TestAdaptiveRouting -v 2>&1 | head -40
```

Expected: FAIL — `select_cli_for_task()` doesn't accept `memory` / `no_adaptive` yet.

- [ ] **Step 3: Update select_cli_for_task() with 3-phase adaptive logic**

Replace `SmartRouter.select_cli_for_task()` entirely:

```python
def select_cli_for_task(
    self,
    task_type: str,
    prefer_structured_output: bool = True,
    memory: Optional["AnalysisMemory"] = None,
    no_adaptive: bool = False,
) -> Tuple[CLIConfig, str]:
    """
    Select the best CLI and model for a task.

    Phases (when memory provided and not no_adaptive):
      0. Health gate: skip degraded CLIs
      1. Priors: sort by win_rate from cli_performance (decisive from run 1)
      2. Streak correction (runs 3+): lock winning streak, skip losing CLI
      3. Win rate override (runs 10+): permanent override if delta ≥15pp
      Anti-thrash: ≥3 distinct CLIs in last 3 runs → hold static

    Args:
        task_type: Task type (audit, analyze, etc.)
        prefer_structured_output: Prefer CLIs that support JSON output
        memory: AnalysisMemory for adaptive routing (None = static only)
        no_adaptive: If True, use static priority map only

    Returns:
        Tuple of (CLIConfig, model_name)

    Raises:
        RuntimeError: If no CLI is available
    """
    _default = [
        (CLIType.OLLAMA, OLLAMA_CONFIG),
        (CLIType.GEMINI, GEMINI_CONFIG),
        (CLIType.CODEX, CODEX_CONFIG),
        (CLIType.CLAUDE, CLAUDE_CONFIG),
    ]
    _task_priority_map = {
        TaskTypes.AUDIT: _default,
        TaskTypes.ANALYZE: _default,
        TaskTypes.ARCHITECTURE: [
            (CLIType.CODEX, CODEX_CONFIG),
            (CLIType.OLLAMA, OLLAMA_CONFIG),
            (CLIType.GEMINI, GEMINI_CONFIG),
            (CLIType.CLAUDE, CLAUDE_CONFIG),
        ],
        TaskTypes.REVIEW: [
            (CLIType.OLLAMA, OLLAMA_CONFIG),
            (CLIType.CODEX, CODEX_CONFIG),
            (CLIType.GEMINI, GEMINI_CONFIG),
            (CLIType.CLAUDE, CLAUDE_CONFIG),
        ],
    }
    priority_order = _task_priority_map.get(task_type, _default)

    # Step 0: Health gate — filter installed + not degraded
    available = [
        (cli_type, config)
        for cli_type, config in priority_order
        if self.is_available(cli_type) and not self.health_monitor.is_degraded(cli_type)
    ]

    # Warn once per session for auth-degraded CLIs
    for cli_type, _ in priority_order:
        if self.is_available(cli_type) and self.health_monitor.is_degraded(cli_type):
            state = self.health_monitor._degraded.get(cli_type)
            if state and state[1] == "auth" and self.health_monitor.should_warn_auth(cli_type):
                logger.warning(
                    f"⚠ {cli_type.value} unavailable (auth error) — skipping"
                )

    if not available:
        raise RuntimeError(
            "No AI CLI available. Install one of: ollama, gemini, codex, or claude"
        )

    def _select_from(candidates):
        """Pick first candidate respecting prefer_structured_output."""
        for cli_type, config in candidates:
            if prefer_structured_output and not config.structured_output:
                if len(candidates) == 1:
                    break
                continue
            model = config.models.get(task_type, FALLBACK_MODEL)
            return config, model
        # Fallback: ignore structured_output preference
        cli_type, config = candidates[0]
        model = config.models.get(task_type, FALLBACK_MODEL)
        return config, model

    # Static selection (reference for Phase 3 + fallback when no_adaptive)
    static_config, static_model = _select_from(available)

    if no_adaptive or memory is None:
        logger.info(
            f"Selected {static_config.cli_type.value} with model {static_model} "
            f"for task {task_type} (static)"
        )
        return static_config, static_model

    # Phase 1: Sort by win_rate from cli_performance (includes pre-seeded priors)
    perf_rows = memory.get_cli_performance(task_type)
    perf_map = {row["cli_name"]: row for row in perf_rows}

    sorted_available = sorted(
        available,
        key=lambda x: (
            -perf_map.get(x[0].value, {}).get("win_rate", 0.0),
            x[1].fallback_priority,
        ),
    )
    current_best_type, current_best_config = sorted_available[0]

    # Anti-thrash guard: ≥3 distinct CLIs in last ANTI_THRASH_WINDOW runs → hold static
    recent = memory.get_recent_cli_runs(task_type, limit=AdaptiveConfig.ANTI_THRASH_WINDOW)
    if len(set(recent)) >= AdaptiveConfig.ANTI_THRASH_DISTINCT_LIMIT:
        logger.info(
            f"Anti-thrash: holding static CLI {static_config.cli_type.value} for {task_type}"
        )
        return static_config, static_model

    # Phase 2: Streak correction (need at least STREAK_WINDOW runs)
    if len(recent) >= AdaptiveConfig.STREAK_WINDOW:
        last_n = recent[:AdaptiveConfig.STREAK_WINDOW]

        # Winning streak: all same CLI → lock it
        if len(set(last_n)) == 1:
            winner_name = last_n[0]
            for cli_type, config in available:
                if cli_type.value == winner_name:
                    model = config.models.get(task_type, FALLBACK_MODEL)
                    logger.info(
                        f"Streak lock: {winner_name} for {task_type} "
                        f"({AdaptiveConfig.STREAK_WINDOW} consecutive runs)"
                    )
                    return config, model

        # Losing streak: current_best not in last N runs → skip to next
        if current_best_type.value not in last_n:
            remaining = [(ct, cfg) for ct, cfg in sorted_available[1:]]
            if remaining:
                logger.info(
                    f"Streak skip: {current_best_type.value} not in last "
                    f"{AdaptiveConfig.STREAK_WINDOW} runs for {task_type}"
                )
                return _select_from(remaining)

    # Phase 3: Win rate override (10+ rated runs, delta ≥15pp)
    current_best_perf = perf_map.get(current_best_type.value, {})
    if current_best_perf.get("run_count", 0) >= AdaptiveConfig.MIN_RUNS_BEFORE_OVERRIDE:
        static_perf = perf_map.get(static_config.cli_type.value, {})
        delta = (
            current_best_perf.get("win_rate", 0.0)
            - static_perf.get("win_rate", 0.0)
        )
        if delta >= AdaptiveConfig.WIN_RATE_DELTA_THRESHOLD:
            model = current_best_config.models.get(task_type, FALLBACK_MODEL)
            logger.info(
                f"[adaptive] {task_type} → {current_best_type.value} "
                f"(was {static_config.cli_type.value}) — "
                f"{current_best_type.value}: {current_best_perf['win_rate']:.0%} win rate "
                f"vs {static_config.cli_type.value}: {static_perf.get('win_rate', 0.0):.0%} "
                f"({current_best_perf['run_count']} runs)"
            )
            return current_best_config, model

    # Default: Phase 1 winner
    model = current_best_config.models.get(task_type, FALLBACK_MODEL)
    logger.info(
        f"Selected {current_best_type.value} with model {model} "
        f"for task {task_type} (adaptive phase 1)"
    )
    return current_best_config, model
```

Add import at top of router.py:

```python
from .constants import (
    ...
    AdaptiveConfig,    # NEW
)
```

Also add the type annotation import fix — `AnalysisMemory` is used as a string annotation, so add `TYPE_CHECKING` guard:

```python
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .memory import AnalysisMemory
```

- [ ] **Step 4: Run all router tests**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_router.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/router.py tests/test_router.py
git commit -m "feat: implement 3-phase adaptive routing in SmartRouter.select_cli_for_task()"
```

---

## Task 6: Wire adaptive routing into cli.py + rating prompt + rate subcommand

**Files:**

- Modify: `ai_delegate/cli.py`
- Modify: `tests/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_cli.py`:

```python
class TestRateSubcommand:
    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "y"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_last_y_stores_win(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            42, "ollama", "audit"
        )
        mock_memory.get_cli_performance.return_value = [
            {"cli_name": "ollama", "win_count": 8, "loss_count": 2}
        ]
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_memory.store_rating.assert_called_once_with(42, 1)

    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "n"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_last_n_stores_loss(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            42, "ollama", "audit"
        )
        mock_memory.get_cli_performance.return_value = []
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_memory.store_rating.assert_called_once_with(42, 0)

    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "y"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_no_runs_exits_with_error(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


class TestNoAdaptiveFlag:
    @patch("ai_delegate.cli.run_analysis")
    @patch("sys.stdin")
    def test_no_adaptive_passed_to_run_analysis(self, mock_stdin, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
        }
        with patch("sys.argv", ["ai-delegate", "audit", "--no-adaptive", "--no-rating"]):
            main()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("no_adaptive") is True


class TestInlineRatingPrompt:
    @patch("ai_delegate.cli.run_analysis")
    @patch("ai_delegate.cli.AnalysisMemory")
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin")
    def test_rating_prompt_shown_after_analysis(
        self, mock_stdin, mock_input, mock_memory_cls, mock_run
    ):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit"]):
            main()
        mock_memory.store_rating.assert_called_once_with(42, 1)

    @patch("ai_delegate.cli.run_analysis")
    @patch("builtins.input", side_effect=EOFError)
    @patch("sys.stdin")
    def test_eof_in_rating_prompt_is_silent(self, mock_stdin, mock_input, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit"]):
            main()  # Should not raise

    @patch("ai_delegate.cli.run_analysis")
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin")
    def test_no_rating_flag_skips_prompt(self, mock_stdin, mock_input, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit", "--no-rating"]):
            main()
        mock_input.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_cli.py::TestRateSubcommand tests/test_cli.py::TestNoAdaptiveFlag tests/test_cli.py::TestInlineRatingPrompt -v 2>&1 | head -40
```

Expected: FAIL.

- [ ] **Step 3: Add _handle_rate_subcommand() and update main() in cli.py**

Add import at top of `cli.py`:

```python
from .memory import AnalysisMemory
```

Add `_handle_rate_subcommand()` function before `main()`:

```python
def _handle_rate_subcommand(args: list) -> None:
    """Handle 'ai-delegate rate --last y|n' subcommand."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate rate")
    parser.add_argument("--last", choices=["y", "n"], required=True,
                        help="Rate the most recent run (y=useful, n=not useful)")
    parsed = parser.parse_args(args)

    memory = AnalysisMemory()
    with memory._connect() as conn:
        row = conn.execute(
            "SELECT id, cli_name, task_type FROM analysis_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        print("No runs to rate.", file=sys.stderr)
        sys.exit(1)

    run_id, cli_name, task_type = row
    rating = 1 if parsed.last == "y" else 0
    memory.store_rating(run_id, rating)

    perf = memory.get_cli_performance(task_type or "")
    cli_perf = next((p for p in perf if p["cli_name"] == cli_name), None)
    if cli_perf:
        print(
            f"✓ Rating saved ({cli_name} / {task_type}: "
            f"{cli_perf['win_count']} wins, {cli_perf['loss_count']} losses)"
        )
    else:
        print("✓ Rating saved")
    sys.exit(0)
```

At the start of `main()`, before creating the parser, add:

```python
def main():
    """Main CLI entry point."""
    # Handle 'rate' subcommand before main parser (avoids positional arg conflict)
    if sys.argv[1:2] == ["rate"]:
        _handle_rate_subcommand(sys.argv[2:])
        return

    parser = argparse.ArgumentParser(...)
```

Add `--no-adaptive` and `--no-rating` to the argument parser:

```python
parser.add_argument(
    "--no-adaptive",
    action="store_true",
    help="Disable adaptive CLI routing (use static priority map)",
)
parser.add_argument(
    "--no-rating",
    action="store_true",
    help="Disable inline rating prompt after analysis",
)
```

- [ ] **Step 4: Wire adaptive routing into run_analysis()**

Update `run_analysis()` signature to add `no_adaptive`:

```python
def run_analysis(
    content: str,
    task_type: str,
    tier: str = Tier.AUTO.value,
    model: Optional[str] = None,
    verbose: bool = False,
    elicit: Optional[str] = None,
    mode: str = "solo",
    no_adaptive: bool = False,   # NEW
) -> dict:
```

In `run_analysis()`, replace the memory block and OllamaClient creation:

```python
    # Initialize memory for regression detection and adaptive routing
    memory = None
    run_id = None
    try:
        memory = AnalysisMemory()
    except Exception:
        pass  # Memory is non-critical

    # Select CLI using adaptive routing (or static if no_adaptive / no memory)
    from .router import get_router
    from .constants import FALLBACK_MODEL as _FALLBACK_MODEL
    router = get_router()
    cli_config, selected_model = router.select_cli_for_task(
        task_type,
        memory=memory if not no_adaptive else None,
        no_adaptive=no_adaptive,
    )
    effective_model = model or selected_model
    if verbose:
        print(f"CLI: {cli_config.cli_name} | Model: {effective_model}")

    # Create client with selected CLI type and health monitor callback
    client = OllamaClient(
        model=effective_model,
        verbose=verbose,
        cli_type=cli_config.cli_name,
        on_cli_error=router.health_monitor.mark_failed,
    )
```

In the memory block after `verdict = orchestrator.analyze(...)`, update to thread `run_id`:

```python
    # Store result in memory and check for regressions (non-critical, best effort)
    try:
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
        if memory is None:
            memory = AnalysisMemory()
        regression = memory.detect_regression(record)
        run_id = memory.store(record)
        memory.record_cli_run(run_id, cli_config.cli_name)
        result["regression"] = regression
        result["_run_id"] = run_id    # for inline rating prompt
        result["_cli_name"] = cli_config.cli_name
    except Exception:
        pass  # Memory is non-critical
```

- [ ] **Step 5: Add inline rating prompt in main() after result is printed**

In `main()`, after the output block (after `print(json.dumps(result, indent=2))` etc.) and before the `show_cost` block, add:

```python
        # Inline rating prompt (skipped in --no-rating mode and CI/pipe)
        run_id = result.get("_run_id")
        if run_id and not args.no_rating:
            try:
                cli_name = result.get("_cli_name", "")
                print(
                    f"\n✓ Analysis complete — {cli_name} {effective_model} "
                    f"— consensus {result['consensus_score']:.2f}",
                    file=sys.stderr,
                )
                rating_input = input(
                    "Was this result useful? (y/n, Enter to skip): "
                ).strip().lower()
                if rating_input in ("y", "n"):
                    from .memory import AnalysisMemory as _AM
                    _AM().store_rating(run_id, 1 if rating_input == "y" else 0)
            except EOFError:
                pass  # CI/pipe safe — silent skip
```

Update the `run_analysis()` call in `main()` to pass `no_adaptive`:

```python
        result = run_analysis(
            content=content,
            task_type=args.task_type,
            tier=tier,
            model=args.model,
            verbose=args.verbose,
            elicit=elicit,
            mode=args.mode,
            no_adaptive=args.no_adaptive,   # NEW
        )
```

- [ ] **Step 6: Run all tests**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: All tests pass.

- [ ] **Step 7: Smoke test the CLI**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
echo "x = input()" | python -m ai_delegate.cli audit --no-rating --no-adaptive 2>&1 | head -5
python -m ai_delegate.cli rate --help
```

- [ ] **Step 8: Commit**

```bash
git add ai_delegate/cli.py tests/test_cli.py
git commit -m "feat: wire adaptive routing into cli.py + inline rating prompt + rate subcommand"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Task |
|---|---|
| `cli_name` + `user_rating` columns on `analysis_runs` | Task 2 |
| `cli_performance` table + seeding from `CLI_PRIORS` | Task 2 |
| `record_cli_run()`, `store_rating()`, `get_cli_performance()`, `get_recent_cli_runs()` | Task 2 |
| `AdaptiveConfig`, `HealthConfig`, `CLI_PRIORS` in constants | Task 1 |
| `CliHealthMonitor` with TTL-based degradation | Task 4 |
| Health gate Step 0 in routing | Task 4 |
| Auth warning once per session | Task 4 |
| Phase 1: priors via `cli_performance` | Task 5 |
| Phase 2: streak correction (win + loss) | Task 5 |
| Phase 3: win rate override after 10+ runs | Task 5 |
| Anti-thrash guard | Task 5 |
| `--no-adaptive` flag | Task 6 |
| Inline rating prompt (y/n, Enter to skip, EOFError safe) | Task 6 |
| `--no-rating` flag | Task 6 |
| `ai-delegate rate --last y|n` subcommand | Task 6 |
| Verbose routing change feedback | Task 5 (via logger.info) |
| Fix `_run_ollama()` stdin bug | Task 3 |
| Add `_run_codex()` | Task 3 |
| Add `_run_gemini()` | Task 3 |
| Error classification → `health_monitor.mark_failed()` | Task 3 + 4 |
| `probe_cli()` per CLI | Not in scope — health is reactive; ollama probed via HTTP in future |

**Note on `probe_cli()`:** The spec mentions it but the design settled on Hybrid/Lazy (reactive) for all API CLIs. Ollama proactive health via `GET /api/tags` is left as a future enhancement to keep scope bounded. All other health detection is reactive (classify errors from run failures).

**Type consistency check:**

- `store()` returns `int` — used as `run_id` throughout ✓
- `get_cli_performance()` returns `List[Dict]` with keys: `cli_name`, `win_rate`, `win_count`, `loss_count`, `run_count`, `last_updated` — consistent across Tasks 2, 5, 6 ✓
- `get_recent_cli_runs()` returns `List[str]` (cli names) — used in Phase 2 streak check ✓
- `CliHealthMonitor.mark_failed(cli: CLIType, error_type: str)` — signature consistent across Tasks 3, 4, 6 ✓
- `select_cli_for_task(..., memory, no_adaptive)` — consistent across Tasks 5 and 6 ✓
