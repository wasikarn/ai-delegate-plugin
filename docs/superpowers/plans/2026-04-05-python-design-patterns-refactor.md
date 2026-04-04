# Python Design Patterns Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 4 design smells — encapsulation violation, misleading name, incomplete factory, dead abstraction — without changing any runtime behavior.

**Architecture:** Four independent surgical fixes applied in order B→C→D→A. Each fix is isolated to 1-2 files and must not change observable behavior. All 500 existing tests must pass after every task.

**Tech Stack:** Python 3.14, pytest, dataclasses, ThreadPoolExecutor

---

## File Map

| Task | Modify | Test |
|------|--------|------|
| B | `ai_delegate/debate/orchestrator.py` | `tests/test_orchestrator.py` |
| C | `ai_delegate/models.py` | `tests/test_models.py` |
| D | `ai_delegate/supervisor.py` | `tests/test_supervisor.py` |
| A | `ai_delegate/client.py`, `ai_delegate/__init__.py`, `ai_delegate/debate/orchestrator.py`, `ai_delegate/cli.py`, 5 test files | — (rename only) |

---

## Task 1 (Fix B): Add `ExpertRunner.get_executor()` classmethod

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:301-317` (add classmethod after `shutdown`)
- Modify: `ai_delegate/debate/orchestrator.py:533` (update DebatePhase)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing test for `get_executor()`**

In `tests/test_orchestrator.py`, add inside the existing `TestExpertRunner` class (or create one):

```python
def test_get_executor_returns_thread_pool(self):
    """get_executor() should return the shared ThreadPoolExecutor."""
    from concurrent.futures import ThreadPoolExecutor
    executor = ExpertRunner.get_executor()
    assert isinstance(executor, ThreadPoolExecutor)

def test_get_executor_returns_same_instance(self):
    """get_executor() should return the same instance every time."""
    assert ExpertRunner.get_executor() is ExpertRunner.get_executor()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_orchestrator.py -k "test_get_executor" -v
```

Expected: `AttributeError: type object 'ExpertRunner' has no attribute 'get_executor'`

- [ ] **Step 3: Add `get_executor()` classmethod to `ExpertRunner`**

In `ai_delegate/debate/orchestrator.py`, add after `shutdown()` (after line 308, before `_register_cleanup`):

```python
@classmethod
def get_executor(cls) -> ThreadPoolExecutor:
    """Get the shared thread pool for external use (e.g. DebatePhase)."""
    return cls._executor
```

- [ ] **Step 4: Update `DebatePhase.run()` to use public method**

In `ai_delegate/debate/orchestrator.py`, find the line in `DebatePhase.run()` that reads:

```python
            ExpertRunner._executor.submit(_debate_one, result): result.expert_name
```

Replace with:

```python
            ExpertRunner.get_executor().submit(_debate_one, result): result.expert_name
```

- [ ] **Step 5: Run new tests to verify they pass**

```bash
python -m pytest tests/test_orchestrator.py -k "test_get_executor" -v
```

Expected: 2 PASSED

- [ ] **Step 6: Run full suite to verify no regressions**

```bash
python -m pytest tests/ -x -q
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_orchestrator.py
git commit -m "refactor: expose ExpertRunner.get_executor() — fixes DebatePhase private attr access"
```

---

## Task 2 (Fix C): Add `expert_models` and `sparse_topology_k` params to `TaskConfig.from_task_type()`

**Files:**

- Modify: `ai_delegate/models.py:203-237`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write failing tests**

In `tests/test_models.py`, add a new test class or extend existing:

```python
def test_from_task_type_accepts_expert_models():
    """from_task_type should pass expert_models to constructor."""
    config = TaskConfig.from_task_type("audit", expert_models={"owasp": "gpt-4o"})
    assert config.expert_models == {"owasp": "gpt-4o"}

def test_from_task_type_accepts_sparse_topology_k():
    """from_task_type should pass sparse_topology_k to constructor."""
    config = TaskConfig.from_task_type("audit", sparse_topology_k=2)
    assert config.sparse_topology_k == 2

def test_from_task_type_defaults_preserve_existing_behavior():
    """from_task_type with no overrides should behave identically to before."""
    config = TaskConfig.from_task_type("audit")
    assert config.expert_models == {}
    assert config.sparse_topology_k is None

def test_from_task_type_sparse_topology_k_none_preserved():
    """None for sparse_topology_k means full topology — must not become 0 or {}."""
    config = TaskConfig.from_task_type("audit", sparse_topology_k=None)
    assert config.sparse_topology_k is None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_models.py -k "test_from_task_type_accepts" -v
```

Expected: `TypeError: from_task_type() got an unexpected keyword argument 'expert_models'`

- [ ] **Step 3: Update `from_task_type()` signature and return**

In `ai_delegate/models.py`, replace the method signature (line 203):

```python
@classmethod
def from_task_type(cls, task_type: str) -> "TaskConfig":
```

With:

```python
@classmethod
def from_task_type(
    cls,
    task_type: str,
    expert_models: Optional[Dict[str, str]] = None,
    sparse_topology_k: Optional[int] = None,
) -> "TaskConfig":
```

Then update the `return cls(...)` statement at the end of the method to add:

```python
        return cls(
            task_type=task_type,
            experts=EXPERT_CONFIGS.get(expert_type, {}),
            display_name=TASK_DISPLAY_NAMES.get(task_type, task_type.upper()),
            description=TASK_EXPERT_DESCRIPTIONS.get(task_type, ""),
            adjudicator_role=TASK_ADJUDICATOR_ROLES.get(task_type, ""),
            output_format=TASK_OUTPUT_FORMATS.get(task_type, ""),
            default_model=DEFAULT_MODELS.get(task_type, FALLBACK_MODEL),
            always_deep=task_type in TaskTypes.ALWAYS_DEEP,
            expert_models=expert_models or {},
            sparse_topology_k=sparse_topology_k,
        )
```

- [ ] **Step 4: Run new tests to verify they pass**

```bash
python -m pytest tests/test_models.py -k "test_from_task_type" -v
```

Expected: all 4 new tests PASSED

- [ ] **Step 5: Run full suite to verify no regressions**

```bash
python -m pytest tests/ -x -q
```

Expected: all tests pass (existing `from_task_type("audit")` calls are backward-compatible — new params are optional)

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/models.py tests/test_models.py
git commit -m "refactor: add expert_models/sparse_topology_k params to TaskConfig.from_task_type()"
```

---

## Task 3 (Fix D): Rename `Supervisor.delegate()` → `execute_task()`

**Files:**

- Modify: `ai_delegate/supervisor.py:157-237`
- Test: `tests/test_supervisor.py`

- [ ] **Step 1: Write failing test for `execute_task()`**

In `tests/test_supervisor.py`, add:

```python
def test_execute_task_success(self):
    """execute_task should execute callable and return TaskResult."""
    supervisor = Supervisor()
    task = Mock(return_value={"result": "success"})

    result = supervisor.execute_task(WorkerType.CODE, task, "arg1", key="value")

    assert result.success == True
    assert result.result == {"result": "success"}
    task.assert_called_once_with("arg1", key="value")

def test_execute_task_failure(self):
    """execute_task should catch exceptions and return failed TaskResult."""
    supervisor = Supervisor()
    task = Mock(side_effect=ValueError("Task error"))

    result = supervisor.execute_task(WorkerType.CODE, task)

    assert result.success == False
    assert result.error == "Task error"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_supervisor.py -k "test_execute_task" -v
```

Expected: `AttributeError: 'Supervisor' object has no attribute 'execute_task'`

- [ ] **Step 3: Add `execute_task()` and update `delegate_parallel()`**

In `ai_delegate/supervisor.py`, replace the `delegate()` method (lines 157-199) with:

```python
def execute_task(
    self,
    task_type: WorkerType,
    task: Callable,
    *args,
    **kwargs
) -> TaskResult:
    """
    Execute a task and wrap exceptions in TaskResult.

    No AI routing is performed — the callable is responsible for its own
    model/CLI selection. Use get_worker_config(task_type) to retrieve
    the reference config if needed.

    Args:
        task_type: Worker type (used for result metadata and logging only)
        task: Callable to execute
        *args: Positional arguments forwarded to task
        **kwargs: Keyword arguments forwarded to task

    Returns:
        TaskResult with execution result or error
    """
    try:
        result = task(*args, **kwargs)
        return TaskResult(
            worker_type=task_type,
            success=True,
            result=result
        )
    except Exception as e:
        logger.error(f"Worker {task_type} failed: {e}")
        return TaskResult(
            worker_type=task_type,
            success=False,
            result=None,
            error=str(e)
        )
```

Also update line 225 in `delegate_parallel()` — change:

```python
                future = executor.submit(
                    self.delegate,
```

to:

```python
                future = executor.submit(
                    self.execute_task,
```

- [ ] **Step 4: Remove old `test_delegate_*` tests and update remaining references**

In `tests/test_supervisor.py`:

1. **Delete** the old `test_delegate_success` and `test_delegate_failure` methods (replaced by the new ones added in Step 1).
2. **Rename** `test_delegate_unknown_worker_type` → `test_execute_task_unknown_worker_type` and change `supervisor.delegate(` → `supervisor.execute_task(` inside it.
3. **Leave** `test_delegate_parallel` method name unchanged — it tests `delegate_parallel()`, which keeps its name.
4. After editing, verify no stale `.delegate(` references remain:

```bash
grep -n "supervisor\.delegate\b" tests/test_supervisor.py
```

Expected: no output (all `.delegate(` calls replaced or deleted).

- [ ] **Step 5: Run new tests to verify they pass**

```bash
python -m pytest tests/test_supervisor.py -v
```

Expected: all tests PASSED

- [ ] **Step 6: Run full suite to verify no regressions**

```bash
python -m pytest tests/ -x -q
```

Expected: all tests pass

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/supervisor.py tests/test_supervisor.py
git commit -m "refactor: rename Supervisor.delegate() -> execute_task(), remove dead WorkerConfig lookup"
```

---

## Task 4 (Fix A): Rename `OllamaClient` → `BackendClient`

**Files:**

- Modify: `ai_delegate/client.py` — class definition + factory docstring
- Modify: `ai_delegate/__init__.py` — lines 11 and 58
- Modify: `ai_delegate/debate/orchestrator.py` — import line 15
- Modify: `ai_delegate/cli.py` — import
- Modify: `tests/test_client.py`, `tests/test_orchestrator.py`, `tests/test_cli.py`, `tests/test_adjudicator.py`, `tests/test_coverage.py`, `tests/test_expert_runner.py`, `tests/test_full_coverage.py` — imports

This task is a pure rename — no logic changes. No new tests needed.

- [ ] **Step 1: Rename class and update docstring in `client.py`**

In `ai_delegate/client.py`:

1. Change line 287:

   ```python
   # Before
   class OllamaClient(AIClient):
   # After
   class BackendClient(AIClient):
   ```

2. Update the docstring (lines 288-296):

   ```python
   """
   Multi-backend AI client with routing and fallback support.

   Supports backends: ollama (default), gemini, codex, claude — selected via cli_type.

   Orchestrates the SRP components:
   - CLIExecutor: subprocess execution
   - RateLimiter: retry logic
   - OutputProcessor: output cleaning
   - ResponseParser: JSON parsing
   """
   ```

3. Update the factory function signature and docstring (line 527+):

   ```python
   def create_client(
       model: str = Models.KIMI_K25_CLOUD,
       fallback_model: str = Models.CLAUDE_SONNET,
       verbose: bool = False,
       strict_validation: bool = False,
   ) -> BackendClient:
       """
       Create a BackendClient with default configuration.
       ...
       """
       return BackendClient(
           model=model,
           fallback_model=fallback_model,
           verbose=verbose,
           strict_validation=strict_validation,
       )
   ```

- [ ] **Step 2: Update `__init__.py`**

In `ai_delegate/__init__.py`:

Line 11 — change:

```python
from .client import AIClient, OllamaClient
```

to:

```python
from .client import AIClient, BackendClient
```

Line 58 — change:

```python
    "OllamaClient",
```

to:

```python
    "BackendClient",
```

- [ ] **Step 3: Update imports in `orchestrator.py` and `cli.py`**

In `ai_delegate/debate/orchestrator.py` (line 15):

```python
# Before
from ..client import OllamaClient
# After
from ..client import BackendClient
```

Update all type annotations in the file that reference `OllamaClient` to `BackendClient` (in `_resolve_client`, `ExpertRunner.__init__`, `Adjudicator.__init__`, `DebatePhase.__init__`, `DebateOrchestrator.__init__`).

In `ai_delegate/cli.py`, find and replace `OllamaClient` import and usages.

- [ ] **Step 4: Update all test file imports**

Run this to find all occurrences:

```bash
grep -rn "OllamaClient" tests/
```

In each file listed, change:

```python
from ai_delegate.client import OllamaClient
# or
from ai_delegate import OllamaClient
```

to:

```python
from ai_delegate.client import BackendClient
# or
from ai_delegate import BackendClient
```

Also rename all variable names like `client = OllamaClient(...)` → `client = BackendClient(...)` and mock specs `Mock(spec=OllamaClient)` → `Mock(spec=BackendClient)`.

- [ ] **Step 5: Run full suite**

```bash
python -m pytest tests/ -x -q
```

Expected: all tests pass. If any fail with `ImportError: cannot import name 'OllamaClient'`, grep for the missed reference:

```bash
grep -rn "OllamaClient" ai_delegate/ tests/
```

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/client.py ai_delegate/__init__.py ai_delegate/debate/orchestrator.py ai_delegate/cli.py tests/
git commit -m "refactor: rename OllamaClient -> BackendClient (multi-backend, not Ollama-only)"
```

---

## Testing Strategy

No new behavior — only encapsulation, naming, and API surface changes. After each task, run:

```bash
python -m pytest tests/ -x -q --tb=short
```

All 500 tests must pass. If coverage drops below 97%, something was deleted unintentionally.

```bash
python -m pytest tests/ --cov=ai_delegate --cov-report=term-missing | tail -5
```
