# Performance Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce debate analysis latency by ~60% and eliminate repeated computation hotspots across the ai-delegate pipeline.

**Architecture:** 8 independent optimization tasks targeting: debate parallelization (5x speedup), hash replacement, build_findings caching, SQLite connection pooling + PRAGMA, ContextLoader caching, lazy consensus evaluation, reduced API timeout, and lru_cache on pure functions.

**Tech Stack:** Python 3.11+, SQLite (sqlite3), concurrent.futures.ThreadPoolExecutor, functools.lru_cache

---

## File Map

| File | Changes |
|------|---------|
| `ai_delegate/debate/orchestrator.py` | Tasks 1, 2, 5 — parallelize DebatePhase, replace MD5, lazy ConsensusCalculator |
| `ai_delegate/memory.py` | Task 3 — batch routing query method, SQLite PRAGMA |
| `ai_delegate/router.py` | Tasks 3, 6 — use batched query, lru_cache on get_model_for_complexity |
| `ai_delegate/context_loader.py` | Task 4 — instance-level cache for disk read |
| `ai_delegate/constants.py` | Task 7 — API_TIMEOUT reduction |

---

## Task 1: Parallelize DebatePhase.run()

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:418-480`
- Test: `tests/test_orchestrator.py`

**Context:** `DebatePhase.run()` currently iterates experts in a sequential `for` loop. With 5 experts x ~300ms per round = ~1.5s wasted. `ExpertRunner.run_parallel()` already shows the correct pattern using `ThreadPoolExecutor.submit` + `as_completed`. We reuse the same shared `ExpertRunner._executor`.

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_orchestrator.py, add:
import time
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import DebatePhase, ExpertRunner
from ai_delegate.models import ExpertResult, Finding

def test_debate_phase_runs_parallel():
    """Debate phase should run experts concurrently, not sequentially."""
    call_times = []

    def slow_run_json(prompt):
        call_times.append(time.monotonic())
        time.sleep(0.05)  # 50ms per expert
        return {"findings": [{"severity": "HIGH", "issue": "test", "recommendation": "fix"}]}

    client = MagicMock()
    client.run_json.side_effect = slow_run_json

    task_config = MagicMock()
    task_config.task_type = "audit"

    expert_results = [
        ExpertResult(expert_name=f"Expert{i}", expert_type="audit",
                     findings=[Finding(severity="HIGH", issue=f"issue{i}", recommendation="fix")],
                     raw_output='{"findings":[]}')
        for i in range(4)
    ]

    phase = DebatePhase(client=client, task_config=task_config)
    start = time.monotonic()
    results = phase.run(expert_results)
    elapsed = time.monotonic() - start

    assert len(results) == 4
    # Sequential would take 4 * 0.05 = 0.2s; parallel should be < 0.15s
    assert elapsed < 0.15, f"Expected parallel execution but took {elapsed:.3f}s"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_orchestrator.py::test_debate_phase_runs_parallel -v
```

Expected: FAIL (sequential takes ~0.2s, assert fails)

- [ ] **Step 3: Replace sequential loop with parallel execution in DebatePhase.run()**

In `ai_delegate/debate/orchestrator.py`, replace the entire `run` method of `DebatePhase` (lines 418-480):

```python
    def run(self, expert_results: List[ExpertResult]) -> List[ExpertResult]:
        """
        Run debate phase between experts in parallel.

        Args:
            expert_results: Results from initial expert analysis

        Returns:
            Updated results after debate
        """
        import concurrent.futures

        valid_results = [r for r in expert_results if not r.error]
        if not valid_results:
            return []

        # Pre-build per-expert "other findings" strings once — O(n) instead of O(n^2)
        other_findings_map = {
            r.expert_name: build_findings(expert_results, exclude=r.expert_name)
            for r in valid_results
        }

        def _run_debate_for_expert(result: ExpertResult) -> ExpertResult:
            other_findings = other_findings_map[result.expert_name]
            prompt = f"""You are the {result.expert_name} Expert.

Your initial findings:
{result.raw_output}

Other experts' findings:
{other_findings}

Instructions:
1. Compare your findings with other experts
2. Identify duplicate or related issues
3. Validate ratings
4. Propose consolidated findings

Output your revised analysis as JSON."""

            try:
                output = self.client.run_json(prompt)

                new_findings = []
                raw_findings = output.get("findings", [])
                if isinstance(raw_findings, list):
                    for f in raw_findings:
                        if isinstance(f, dict):
                            new_findings.append(Finding.from_dict(f))

                final_findings = new_findings if new_findings else result.findings

                return ExpertResult(
                    expert_name=result.expert_name,
                    expert_type=result.expert_type,
                    findings=final_findings,
                    raw_output=json.dumps(output),
                )
            except Exception as e:
                logger.error(f"Debate failed for {result.expert_name}: {e}")
                return result

        debate_results: List[ExpertResult] = []
        futures = {
            ExpertRunner._executor.submit(_run_debate_for_expert, result): result.expert_name
            for result in valid_results
        }

        for future in concurrent.futures.as_completed(futures):
            expert_name = futures[future]
            try:
                debate_results.append(future.result())
                if self.verbose:
                    logger.info(f"[{expert_name} Debate] completed")
            except Exception as e:
                logger.error(f"Debate future failed for {expert_name}: {e}")
                for r in valid_results:
                    if r.expert_name == expert_name:
                        debate_results.append(r)
                        break

        return debate_results
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: All pass including new parallel test.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_orchestrator.py
git commit -m "perf: parallelize DebatePhase.run() using shared ExpertRunner thread pool"
```

---

## Task 2: Replace MD5 with tuple keys in ConsensusCalculator

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:84-96`
- Test: `tests/test_consensus.py`

**Context:** `ConsensusCalculator.calculate()` computes `hashlib.md5(raw.encode()).hexdigest()` for every finding. MD5 is unnecessary here — a plain `(severity, issue)` tuple is hashable and faster. Also removes the `import hashlib` dependency.

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_consensus.py, add:
from unittest.mock import patch
from ai_delegate.debate.orchestrator import ConsensusCalculator
from ai_delegate.models import ExpertResult, Finding

def test_consensus_no_md5_overhead():
    """ConsensusCalculator should not use MD5; tuple key should be used instead."""
    findings = [Finding(severity="HIGH", issue=f"issue_{i}", recommendation="fix") for i in range(50)]
    results = [
        ExpertResult(expert_name=f"E{j}", expert_type="audit", findings=findings, raw_output="{}")
        for j in range(5)
    ]

    import hashlib
    with patch.object(hashlib, "md5", wraps=hashlib.md5) as mock_md5:
        ConsensusCalculator.calculate(results)
        assert mock_md5.call_count == 0, f"hashlib.md5 called {mock_md5.call_count} times, expected 0"

def test_consensus_tuple_key_deduplication():
    """Same (severity, issue) from different experts should be counted as the same finding."""
    shared_finding = Finding(severity="HIGH", issue="SQL injection in login", recommendation="use parameterized queries")
    results = [
        ExpertResult(expert_name="SecurityExpert", expert_type="audit",
                     findings=[shared_finding], raw_output="{}"),
        ExpertResult(expert_name="AuthExpert", expert_type="audit",
                     findings=[shared_finding], raw_output="{}"),
        ExpertResult(expert_name="InputExpert", expert_type="audit",
                     findings=[shared_finding], raw_output="{}"),
    ]
    consensus = ConsensusCalculator.calculate(results)
    assert len(consensus.consensus_findings) == 1
    assert len(consensus.disputed_findings) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_consensus.py::test_consensus_no_md5_overhead tests/test_consensus.py::test_consensus_tuple_key_deduplication -v
```

Expected: `test_consensus_no_md5_overhead` FAILS (md5 still called).

- [ ] **Step 3: Replace MD5 with tuple keys**

In `ai_delegate/debate/orchestrator.py`, modify the dict declarations and key computation in `ConsensusCalculator.calculate()` (lines 84-96):

```python
        # Count findings by normalized key, tracking which expert raised each
        finding_counts: Dict[tuple, int] = {}
        finding_by_key: Dict[tuple, List[Finding]] = {}
        finding_key_to_expert: Dict[tuple, str] = {}

        for result in expert_results:
            for finding in result.findings:
                key = (finding.severity, finding.issue)
                finding_counts[key] = finding_counts.get(key, 0) + 1
                if key not in finding_by_key:
                    finding_by_key[key] = []
                    finding_key_to_expert[key] = result.expert_name
                finding_by_key[key].append(finding)
```

Then check and remove the `import hashlib` at line 9 if unused:

```bash
grep -n "hashlib" ai_delegate/debate/orchestrator.py
```

Remove the line if the only reference was in calculate().

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_consensus.py tests/test_orchestrator.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_consensus.py
git commit -m "perf: replace MD5 hashing with tuple keys in ConsensusCalculator"
```

---

## Task 3: SQLite PRAGMA optimizations + batched routing queries

**Files:**

- Modify: `ai_delegate/memory.py:38-39` and `memory.py:67` (`_init_db`)
- Add method: `ai_delegate/memory.py` (`get_routing_context`)
- Modify: `ai_delegate/router.py:375-389` (use batch method)
- Test: `tests/test_memory.py`, `tests/test_router.py`

**Context:** Every `_connect()` call opens a fresh sqlite3 connection. `select_cli_for_task()` calls `get_cli_performance()` then `get_recent_cli_runs()` — 2 separate connections per routing decision. Fix: (1) add PRAGMA optimizations at init time, (2) batch both queries into one method.

- [ ] **Step 1: Write failing tests**

```python
# In tests/test_memory.py, add:
import tempfile, pathlib
from ai_delegate.memory import AnalysisMemory

def test_get_routing_context_returns_both():
    """get_routing_context should return (perf_rows, recent_runs) in one call."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = AnalysisMemory(db_path=pathlib.Path(tmpdir) / "test.db")
        perf, recent = mem.get_routing_context("audit")
        assert isinstance(perf, list)
        assert isinstance(recent, list)

def test_get_routing_context_single_connection():
    """get_routing_context should open only ONE connection (not 2 separate ones)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = AnalysisMemory(db_path=pathlib.Path(tmpdir) / "test.db")
        connection_count = []
        original_connect = mem._connect

        def counting_connect():
            connection_count.append(1)
            return original_connect()

        mem._connect = counting_connect
        mem.get_routing_context("audit")
        assert len(connection_count) == 1, f"Expected 1 connection, got {len(connection_count)}"

def test_wal_mode_enabled():
    """SQLite should be in WAL journal mode after init."""
    with tempfile.TemporaryDirectory() as tmpdir:
        mem = AnalysisMemory(db_path=pathlib.Path(tmpdir) / "test.db")
        with mem._connect() as conn:
            mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        assert mode == "wal", f"Expected WAL mode, got {mode}"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_memory.py::test_get_routing_context_returns_both tests/test_memory.py::test_get_routing_context_single_connection tests/test_memory.py::test_wal_mode_enabled -v
```

Expected: All 3 FAIL.

- [ ] **Step 3: Add PRAGMA optimizations to _init_db()**

In `ai_delegate/memory.py`, insert these 3 lines at the START of the `with self._connect() as conn:` block inside `_init_db()` (after line 68, before the first `conn.execute("""CREATE TABLE IF NOT EXISTS analysis_runs`):

```python
    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-65536")  # 64 MB page cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
            # ... rest unchanged ...
```

- [ ] **Step 4: Add get_routing_context() method**

In `ai_delegate/memory.py`, add this method after `get_recent_cli_runs()` (after line 333):

```python
    def get_routing_context(self, task_type: str, recent_limit: int = 3) -> tuple:
        """
        Batch query: fetch cli_performance rows AND recent run names in one connection.

        Returns:
            (perf_rows: List[Dict], recent_cli_names: List[str])
        """
        with self._connect() as conn:
            perf_rows = conn.execute(
                """SELECT cli_name, win_rate, win_count, loss_count, run_count, last_updated
                   FROM cli_performance WHERE task_type = ?
                   ORDER BY win_rate DESC""",
                (task_type,),
            ).fetchall()
            recent_rows = conn.execute(
                """SELECT cli_name FROM analysis_runs
                   WHERE task_type = ? AND cli_name IS NOT NULL
                   ORDER BY id DESC LIMIT ?""",
                (task_type, recent_limit),
            ).fetchall()
        return (
            [
                {
                    "cli_name": r[0], "win_rate": r[1], "win_count": r[2],
                    "loss_count": r[3], "run_count": r[4], "last_updated": r[5],
                }
                for r in perf_rows
            ],
            [r[0] for r in recent_rows],
        )
```

- [ ] **Step 5: Update router.py to use get_routing_context()**

In `ai_delegate/router.py`, replace lines 375-394 (the two separate memory calls and the anti-thrash check that uses `recent`):

```python
        # Phase 1: Sort by win_rate + anti-thrash in one DB round-trip
        perf_rows, recent = memory.get_routing_context(
            task_type, recent_limit=AdaptiveConfig.ANTI_THRASH_WINDOW
        )
        perf_map = {row["cli_name"]: row for row in perf_rows}

        sorted_available = sorted(
            available,
            key=lambda x: (
                -perf_map.get(x[0].value, {}).get("win_rate", 0.0),
                x[1].fallback_priority,
            ),
        )
        current_best_type, current_best_config = sorted_available[0]

        # Anti-thrash guard: >=3 distinct CLIs in last ANTI_THRASH_WINDOW runs -> hold static
        if len(set(recent)) >= AdaptiveConfig.ANTI_THRASH_DISTINCT_LIMIT:
```

Remove the old `recent = memory.get_recent_cli_runs(...)` line that previously appeared at line 389.

- [ ] **Step 6: Run all tests**

```bash
pytest tests/test_memory.py tests/test_router.py -v
```

Expected: All pass.

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/memory.py ai_delegate/router.py tests/test_memory.py
git commit -m "perf: SQLite WAL+PRAGMA and batch routing context query (2 queries -> 1)"
```

---

## Task 4: Cache ContextLoader disk read per instance

**Files:**

- Modify: `ai_delegate/context_loader.py`
- Test: `tests/test_context_loader.py`

**Context:** `ContextLoader().format_for_prompt()` is called in `DebateOrchestrator.__init__()` every time an orchestrator is created. In batch analysis, this reads disk once per file. Since the context doesn't change during a session, cache after first read.

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_context_loader.py, add:
from unittest.mock import patch
from ai_delegate.context_loader import ContextLoader
import pathlib

def test_context_loader_caches_result(tmp_path):
    """ContextLoader.format_for_prompt() should only read disk once, not per call."""
    context_file = tmp_path / ".ai-delegate" / "context.md"
    context_file.parent.mkdir(parents=True)
    context_file.write_text("# Project Rules\nNo insecure patterns.")

    read_count = []
    original_read = pathlib.Path.read_text

    def counting_read(self, **kwargs):
        read_count.append(str(self))
        return original_read(self, **kwargs)

    with patch.object(pathlib.Path, "read_text", counting_read):
        loader = ContextLoader(base_dir=tmp_path)
        result1 = loader.format_for_prompt()
        result2 = loader.format_for_prompt()

    assert result1 == result2
    assert len(read_count) == 1, f"Expected 1 disk read, got {len(read_count)}"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_context_loader.py::test_context_loader_caches_result -v
```

Expected: FAIL (read_text called twice).

- [ ] **Step 3: Add instance-level cache to ContextLoader**

Replace entire `ai_delegate/context_loader.py` with:

```python
"""Load project constitution from .ai-delegate/context.md."""

from pathlib import Path
from typing import Optional


CONTEXT_PATHS = [
    ".ai-delegate/context.md",
    ".ai-delegate/CONTEXT.md",
    "ai-delegate-context.md",
]


class ContextLoader:
    """Load and format project constitution for expert prompts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()
        self._cached_context: Optional[str] = None
        self._loaded: bool = False

    def load(self) -> Optional[str]:
        """Load context from first found context file, cached after first read."""
        if not self._loaded:
            for relative_path in CONTEXT_PATHS:
                full_path = self.base_dir / relative_path
                if full_path.exists():
                    self._cached_context = full_path.read_text(encoding="utf-8").strip()
                    break
            self._loaded = True
        return self._cached_context

    def format_for_prompt(self) -> str:
        """Return context formatted for injection into expert prompts.

        Returns empty string if no context file found.
        """
        context = self.load()
        if not context:
            return ""
        return f"""## PROJECT CONTEXT (Constitution)
The following constraints and decisions apply to this project.
All experts MUST respect these when making recommendations:

{context}

---
"""
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_context_loader.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/context_loader.py tests/test_context_loader.py
git commit -m "perf: cache ContextLoader disk read per instance (no re-read on repeated calls)"
```

---

## Task 5: Lazy ConsensusCalculator — skip for always_deep tasks

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:540-569`
- Test: `tests/test_orchestrator.py`

**Context:** `DebateOrchestrator.analyze()` always calls `ConsensusCalculator.calculate()` even for `always_deep=True` tasks (audit, architecture, migrate). For those tasks the result is immediately discarded in `_select_tier()`. Skip the call entirely for `always_deep=True` or explicit non-AUTO tier (unless FAST tier needs it for verdict creation).

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_orchestrator.py, add:
from unittest.mock import MagicMock, patch
from ai_delegate.debate.orchestrator import DebateOrchestrator, ConsensusCalculator
from ai_delegate.models import ExpertResult, Finding, Tier

def test_consensus_skipped_for_always_deep():
    """ConsensusCalculator.calculate() should NOT be called when always_deep=True."""
    client = MagicMock()
    client.run_json.return_value = {"findings": [{"severity": "HIGH", "issue": "x", "recommendation": "y"}]}

    task_config = MagicMock()
    task_config.task_type = "audit"
    task_config.always_deep = True
    task_config.experts = {"Security": "check security"}
    task_config.adjudicator_role = "synthesize"
    task_config.output_format = '{"findings": []}'

    expert_result = ExpertResult(
        expert_name="Security", expert_type="audit",
        findings=[Finding(severity="HIGH", issue="x", recommendation="y")],
        raw_output='{"findings":[]}'
    )

    with patch.object(ConsensusCalculator, "calculate", wraps=ConsensusCalculator.calculate) as mock_calc:
        orchestrator = DebateOrchestrator(client=client, task_config=task_config)
        with patch.object(orchestrator.expert_runner, "run_parallel", return_value=[expert_result]):
            with patch.object(orchestrator.debate_phase, "run", return_value=[expert_result]):
                mock_verdict = MagicMock()
                mock_verdict.tier_used = Tier.DEEP.value
                with patch.object(orchestrator.adjudicator, "adjudicate", return_value=mock_verdict):
                    orchestrator.analyze("some content", tier=Tier.AUTO.value)
    assert mock_calc.call_count == 0, f"ConsensusCalculator called {mock_calc.call_count} times, expected 0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_orchestrator.py::test_consensus_skipped_for_always_deep -v
```

Expected: FAIL (calculate is still called).

- [ ] **Step 3: Add early-exit before ConsensusCalculator in analyze()**

In `ai_delegate/debate/orchestrator.py`, replace lines 552-569 (Phase 2 consensus block):

```python
            # Phase 2: Calculate consensus — skip if always_deep (result unused)
            # or if tier is explicitly not AUTO (except FAST needs consensus for verdict)
            needs_consensus = (
                tier == Tier.AUTO.value and not self.task_config.always_deep
            ) or tier == Tier.FAST.value

            if needs_consensus:
                consensus = ConsensusCalculator.calculate(expert_results)
                if tier == Tier.AUTO.value and ForcedFindingValidator.should_force_deep(expert_results):
                    logger.warning("All experts returned 0 findings — forcing DEEP tier for deeper analysis")
                    selected_tier = Tier.DEEP.value
                else:
                    selected_tier = self._select_tier(tier, consensus)
            else:
                consensus = None
                selected_tier = Tier.DEEP.value if tier == Tier.AUTO.value else tier

            if self.verbose:
                if consensus:
                    logger.info(f"Consensus: {consensus.percentage:.0f}% -> Tier: {selected_tier}")
                else:
                    logger.info(f"Tier: {selected_tier} (consensus skipped)")

            # FAST tier: Return consensus directly (consensus guaranteed non-None here)
            if selected_tier == Tier.FAST.value:
                return self._create_verdict_from_consensus(consensus, selected_tier)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_orchestrator.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_orchestrator.py
git commit -m "perf: skip ConsensusCalculator for always_deep tasks and explicit non-AUTO tiers"
```

---

## Task 6: @lru_cache on get_model_for_complexity

**Files:**

- Modify: `ai_delegate/router.py:178`
- Test: `tests/test_router.py`

**Context:** `get_model_for_complexity(complexity, budget_mode)` has only 6 possible inputs (3 ComplexityLevel x 2 bool). In batch analysis over many files, same calls are repeated. `@functools.lru_cache` eliminates redundant dict lookups.

- [ ] **Step 1: Write the failing test**

```python
# In tests/test_router.py, add:
from ai_delegate.router import get_model_for_complexity, ComplexityLevel

def test_get_model_for_complexity_is_cached():
    """get_model_for_complexity should be decorated with @functools.lru_cache."""
    assert hasattr(get_model_for_complexity, "cache_info"), \
        "get_model_for_complexity must be decorated with @functools.lru_cache"

def test_get_model_for_complexity_cache_hits():
    """Repeated calls with same args should be served from cache."""
    get_model_for_complexity.cache_clear()
    result1 = get_model_for_complexity(ComplexityLevel.HIGH, False)
    result2 = get_model_for_complexity(ComplexityLevel.HIGH, False)
    info = get_model_for_complexity.cache_info()
    assert info.hits >= 1
    assert result1 == result2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_router.py::test_get_model_for_complexity_is_cached tests/test_router.py::test_get_model_for_complexity_cache_hits -v
```

Expected: Both FAIL (no cache_info attribute).

- [ ] **Step 3: Add @lru_cache to get_model_for_complexity**

In `ai_delegate/router.py`, add `import functools` after `import logging` (line 11), then decorate `get_model_for_complexity` (line 178):

```python
import functools

# ... (existing imports unchanged) ...

@functools.lru_cache(maxsize=16)
def get_model_for_complexity(complexity: ComplexityLevel, budget_mode: bool = False) -> Dict:
    """
    Get model config for complexity level.

    Args:
        complexity: Detected complexity level
        budget_mode: Use budget models for cost savings

    Returns:
        Dict with model, cli, max_tokens, reason
    """
    config = COMPLEXITY_MODEL_MAP.get(complexity, COMPLEXITY_MODEL_MAP[ComplexityLevel.MEDIUM])

    if budget_mode and "budget_model" in config:
        return {
            "model": config["budget_model"],
            "cli": CLIType.OLLAMA,
            "max_tokens": config["max_tokens"],
            "reason": f"Budget mode: {config['reason']}"
        }

    return config
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_router.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/router.py tests/test_router.py
git commit -m "perf: add @lru_cache(maxsize=16) to get_model_for_complexity (6 possible inputs)"
```

---

## Task 7: Reduce API_TIMEOUT from 300s to 60s

**Files:**

- Modify: `ai_delegate/constants.py:105`
- Test: `tests/test_client.py`

**Context:** `RetryConfig.API_TIMEOUT = 300` means a hanging subprocess blocks for 5 minutes. Ollama local responds in <10s, cloud APIs in <30s. 60s is generous without causing user-visible hangs.

- [ ] **Step 1: Write the test**

```python
# In tests/test_client.py, add:
from ai_delegate.constants import RetryConfig

def test_api_timeout_is_reasonable():
    """API_TIMEOUT should be at most 60s to avoid long user-visible hangs."""
    assert RetryConfig.API_TIMEOUT <= 60, (
        f"API_TIMEOUT is {RetryConfig.API_TIMEOUT}s — reduce to <=60s to avoid 5-min hangs"
    )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_client.py::test_api_timeout_is_reasonable -v
```

Expected: FAIL (`300 > 60`).

- [ ] **Step 3: Update API_TIMEOUT**

In `ai_delegate/constants.py`, line 105:

```python
    API_TIMEOUT = 60       # seconds (reduced from 300; Ollama <10s, cloud APIs <30s)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_client.py -v
```

Expected: All pass.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/constants.py tests/test_client.py
git commit -m "perf: reduce API_TIMEOUT from 300s to 60s to prevent long subprocess hangs"
```

---

## Task 8: Full test suite verification

**Files:** All modified files

- [ ] **Step 1: Run full test suite**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/ -v --cov=ai_delegate --cov-report=term-missing 2>&1 | tail -30
```

Expected: All tests pass, coverage >= 97%.

- [ ] **Step 2: Verify no regression on test count**

```bash
pytest tests/ --co -q 2>&1 | tail -5
```

Expected: >= 484 tests collected.

---

## Summary of Changes

| Task | File | Type | Expected Speedup |
|------|------|------|-----------------|
| 1 | orchestrator.py | Parallelization | **~5x** on debate phase (~1.5s -> ~0.3s) |
| 2 | orchestrator.py | Algorithm | ~50ms per analysis |
| 3 | memory.py, router.py | I/O batching + PRAGMA | ~30-40% routing overhead |
| 4 | context_loader.py | Caching | ~100ms per batch file |
| 5 | orchestrator.py | Lazy evaluation | ~20ms per always_deep analysis |
| 6 | router.py | Caching | Negligible (defensive) |
| 7 | constants.py | Config | Prevents 5-min user hangs |
