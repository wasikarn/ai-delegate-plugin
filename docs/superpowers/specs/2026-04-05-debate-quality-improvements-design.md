# Debate Quality Improvements: Heterogeneous Models + Sparse Topology

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve multi-agent debate quality and efficiency by (1) assigning different models to different experts, and (2) limiting each expert's peer visibility to k neighbors.

**Architecture:** Both features are opt-in via new `TaskConfig` fields with backward-compatible defaults. No existing call sites break. Python API only — no CLI arg changes in this iteration.

**Tech Stack:** Python 3.10+, `concurrent.futures.ThreadPoolExecutor`, `OllamaClient`, `dataclasses`

---

## Feature 1: Heterogeneous Models

Each expert in `ExpertRunner` and `DebatePhase` can use a different AI model. When `expert_models` is populated in `TaskConfig`, the system creates a per-expert `OllamaClient` with the specified model. When empty (default), all experts share the session-wide client.

**Expected accuracy improvement:** 82% → 91% (multi-agent debate literature).

### Data Model

**File:** `ai_delegate/models.py`

Add to `TaskConfig` dataclass (after `always_deep: bool = False`):

```python
expert_models: Dict[str, str] = field(default_factory=dict)
# Maps expert_name -> model_name
# Example: {"owasp": "gpt-4o", "auth": "gemini-2.5-pro", "input": "kimi-k2.5:cloud"}
# Empty dict (default) = all experts share the session-wide client
```

### ExpertRunner Changes

**File:** `ai_delegate/debate/orchestrator.py`

1. **New method** `_get_client_for_expert(expert_name: str) -> AIClient`:

```python
def _get_client_for_expert(self, expert_name: str) -> AIClient:
    """Return per-expert client if model override exists, else shared client."""
    model = self.task_config.expert_models.get(expert_name)
    if not model or model == getattr(self.client, 'model', None):
        return self.client
    return OllamaClient(
        model=model,
        fallback_model=getattr(self.client, 'fallback_model', None),
        verbose=self.verbose,
        cli_type=getattr(self.client, 'cli_type', 'ollama'),
    )
```

1. **Update** `_run_single_expert()` (line ~249): replace `self.client.run_json(prompt)` with:

```python
client = self._get_client_for_expert(expert_name)
raw_output = client.run_json(prompt)
```

### DebatePhase Changes

**File:** `ai_delegate/debate/orchestrator.py`

`DebatePhase` already stores `self.task_config`. Apply same pattern in the debate round loop where `self.client.run_json(debate_prompt)` is called — use `_get_client_for_expert()` equivalent inline or extract shared helper.

---

## Feature 2: Sparse Topology

Each expert sees only `k` peers' findings during debate instead of all N-1 peers. Uses deterministic round-robin selection for reproducibility.

**Expected token reduction:** N÷(k+1) — for N=6, k=2: 50% reduction.

### Data Model

**File:** `ai_delegate/models.py`

Add to `TaskConfig` dataclass (after `expert_models`):

```python
sparse_topology_k: Optional[int] = None
# None = full visibility (all N-1 peers, existing behavior)
# 2 = each expert sees 2 peers (round-robin)
```

### DebatePhase Changes

**File:** `ai_delegate/debate/orchestrator.py`

1. **New method** `_select_peers(expert_idx: int, total: int, k: int) -> List[int]`:

```python
def _select_peers(self, expert_idx: int, total: int, k: int) -> List[int]:
    """Select k peer indices using deterministic round-robin."""
    actual_k = min(k, total - 1)
    return sorted((expert_idx + i + 1) % total for i in range(actual_k))
```

1. **Update** `DebatePhase.run()` — in the parallel debate loop, conditionally build per-expert findings:

```python
k = self.task_config.sparse_topology_k
if k is not None:
    # Sparse: each expert sees only k peers
    peer_idxs = self._select_peers(expert_idx, len(expert_results), k)
    findings_str = build_findings([expert_results[i] for i in peer_idxs])
else:
    # Full topology: use pre-built shared string (O(n) optimization)
    findings_str = all_findings_str
```

Note: `all_findings_str` is still built once before the loop (existing O(n) optimization). Sparse topology bypasses it per-expert when `k` is set, building N separate strings at O(k) each instead of sharing O(N).

---

## Backward Compatibility

| Scenario | Behavior |
|----------|----------|
| `expert_models = {}` (default) | All experts use session client — no change |
| `sparse_topology_k = None` (default) | All experts see all peers — no change |
| `expert_models` partially populated | Unspecified experts fall back to session client |
| `sparse_topology_k > N-1` | `_select_peers` caps at N-1 (full visibility) |

---

## Testing

### Heterogeneous Models Tests

- **Unit**: `_get_client_for_expert()` returns session client when model not in map; returns new client when model differs
- **Integration**: `ExpertRunner.run_parallel()` with `expert_models` set — verify different clients used per expert (mock `OllamaClient.__init__` and track calls)

### Sparse Topology Tests

- **Unit**: `_select_peers(0, 3, 2)` → `[1, 2]`; `_select_peers(2, 3, 2)` → `[0, 1]` (wraps around)
- **Unit**: `k >= N-1` → returns all peers (cap behavior)
- **Integration**: `DebatePhase.run()` with `sparse_topology_k=2` — verify each expert's prompt contains exactly 2 peers' findings, not all

---

## Files to Touch

| File | Change |
|------|--------|
| `ai_delegate/models.py` | Add `expert_models` + `sparse_topology_k` to `TaskConfig` |
| `ai_delegate/debate/orchestrator.py` | Add `_get_client_for_expert()` to `ExpertRunner`; add `_select_peers()` to `DebatePhase`; update 2 call sites |
| `tests/test_orchestrator.py` | Add tests for both features |
