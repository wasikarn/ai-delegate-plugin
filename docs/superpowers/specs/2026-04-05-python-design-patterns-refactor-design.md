# Python Design Patterns Refactor — Design Spec

**Date:** 2026-04-05  
**Scope:** 4 targeted fixes across `client.py`, `debate/orchestrator.py`, `models.py`, `supervisor.py`  
**Method:** 3-expert debate (refactor, architecture, code-quality) → synthesized verdict

---

## Problem Summary

The codebase is generally well-structured. Four specific smells were identified:

| # | File | Smell | Severity |
|---|------|-------|----------|
| A | `client.py` | `OllamaClient` name implies Ollama-only, handles 4 backends | Medium |
| B | `debate/orchestrator.py:533` | `DebatePhase` accesses `ExpertRunner._executor` (private ClassVar) | High |
| C | `models.py:203` | `TaskConfig.from_task_type()` silently drops `expert_models` + `sparse_topology_k` | High |
| D | `supervisor.py:157` | `delegate()` fetches `WorkerConfig` but never uses it during execution | Medium |

---

## Fix A — Rename `OllamaClient` → `BackendClient`

### What

- Rename class `OllamaClient` → `BackendClient` in `client.py`
- Update factory function: `create_client() -> BackendClient`
- Update docstring to reflect multi-backend responsibility
- `AIClient` ABC and all SRP components (`CLIExecutor`, `RateLimiter`, `OutputProcessor`, `ResponseParser`) stay unchanged

### Why

All 3 experts flagged that `OllamaClient` is misleading — the class routes to Ollama, Gemini, Codex, and Claude via `cli_type`. The ABC is already correctly named `AIClient`. The concrete class name should match its actual scope.

### Affected files

- `ai_delegate/client.py` — class definition + factory
- `ai_delegate/__init__.py` — line 11 (import) + line 58 (`__all__` export)
- `ai_delegate/debate/orchestrator.py` — import
- `ai_delegate/cli.py` — import
- `tests/test_client.py`, `tests/test_orchestrator.py`, `tests/test_cli.py`, `tests/test_adjudicator.py`, `tests/test_coverage.py`, `tests/test_expert_runner.py`, `tests/test_full_coverage.py` — imports

### What does NOT change

- No logic changes
- `cli_type` string routing (Ollama → Gemini → Codex → Claude) stays as-is
- No backend splitting (premature; backends share rate limiting, output processing, validation)

---

## Fix B — Add `ExpertRunner.get_executor()` classmethod

### What

Add a public classmethod to `ExpertRunner`:

```python
@classmethod
def get_executor(cls) -> ThreadPoolExecutor:
    """Get the shared thread pool for external use."""
    return cls._executor
```

Replace line 533 in `DebatePhase.run()`:

```python
# Before
ExpertRunner._executor.submit(_debate_one, result)

# After
ExpertRunner.get_executor().submit(_debate_one, result)
```

### Why

`DebatePhase` accessing `ExpertRunner._executor` violates encapsulation — underscore prefix signals private. If `ExpertRunner`'s threading model changes, `DebatePhase` silently breaks. The classmethod fix restores the public/private boundary with 1 new method and 1 changed line.

The alternative (SharedThreadPool singleton) is cleaner architecturally but introduces a 3rd class for a 2-user relationship — over-engineered at current scale. Constructor injection adds verbosity at every call site.

### Affected files

- `ai_delegate/debate/orchestrator.py` — add classmethod to `ExpertRunner`, update `DebatePhase.run()` line 533

---

## Fix C — Add optional params to `TaskConfig.from_task_type()`

### What

Update signature:

```python
@classmethod
def from_task_type(
    cls,
    task_type: str,
    expert_models: Optional[Dict[str, str]] = None,
    sparse_topology_k: Optional[int] = None,
) -> "TaskConfig":
```

Pass through to constructor:

```python
return cls(
    ...,  # existing fields
    expert_models=expert_models or {},
    sparse_topology_k=sparse_topology_k,
)
```

### Why

CLAUDE.md documents `TaskConfig.from_task_type("audit", expert_models={...})` as the intended API, but current code raises `TypeError` on that call. Users either get a confusing error or discover the 2-step post-construction pattern from tests. The 2-step pattern also allows silent typos (`config.expert_models = {"owas": "gpt-4"}` — no error, no effect).

Explicit params (not `**kwargs`) are preferred for type safety and IDE autocomplete.

### What updates

- `ai_delegate/models.py` — factory signature + return statement (5 lines)
- `tests/` — ~34 `from_task_type()` call sites across all test files; sites using 2-step post-construction can optionally be simplified to 1-line
- Note: `None` is preserved for `sparse_topology_k` (meaningful = full topology); `expert_models or {}` coerces `None` to empty dict

### What does NOT change

- Post-construction pattern (`config.expert_models = {...}`) remains valid — dataclass fields are mutable

---

## Fix D — Simplify `Supervisor.delegate()`

### What

- Rename method `delegate()` → `execute_task()`
- Remove the dead `worker_config = self.workers.get(task_type)` lookup (it was only used for existence check, then discarded)
- Keep `get_worker_config()` public for callers who want reference config
- Update docstring to be honest: "executes callable and wraps errors; no AI routing"

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
    """
    try:
        result = task(*args, **kwargs)
        return TaskResult(worker_type=task_type, success=True, result=result)
    except Exception as e:
        logger.error(f"Worker {task_type} failed: {e}")
        return TaskResult(worker_type=task_type, success=False, result=None, error=str(e))
```

### Why

The current `delegate()` promises routing (fetches `WorkerConfig`) but delivers nothing (ignores it). Code Quality expert's "pass config as first arg to callable" breaks caller API. Architecture expert's "delete the class" loses the error-wrapping + parallel execution utility. Renaming + honest docstring is the minimal honest fix.

`delegate_parallel()` wraps `delegate()` via an explicit `self.delegate` reference at line 225 — **must be updated to `self.execute_task`** as part of Fix D.

### Affected files

- `ai_delegate/supervisor.py` — rename `delegate()` → `execute_task()`, update `delegate_parallel()` line 225 (`self.delegate` → `self.execute_task`), remove dead `worker_config` lookup, update docstring
- `tests/test_supervisor.py` — rename all `delegate()` call sites to `execute_task()`

---

## Testing Strategy

No new tests required — all 4 fixes are refactors with no behavior change.

Existing test suite (500 tests, 97% coverage) must pass before and after each fix.

Run after each fix:

```bash
python -m pytest tests/ -v --cov=ai_delegate
```

---

## Implementation Order

Each fix is independent. Suggested order to minimize import churn:

1. **Fix B** (orchestrator internal — no import changes)
2. **Fix C** (models internal — update test call sites)
3. **Fix D** (supervisor internal — rename call sites)
4. **Fix A** (cross-cutting rename — update all imports last)

---

## Out of Scope

- Backend splitting (`OllamaBackend`, `GeminiBackend`, etc.) — premature, all backends share components
- `SharedThreadPool` extraction — over-engineered for current 2-user relationship
- `Supervisor` completion (real AI routing) — no concrete use case requiring it
- Any changes to `constants.py`, `config.py`, `router.py`, or `debate/` logic
