# Debate Quality Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add heterogeneous models (per-expert model assignment) and sparse topology (each expert sees k peers) to the multi-agent debate system.

**Architecture:** Two new optional fields on `TaskConfig` drive both features. A module-level `_resolve_client()` helper in `orchestrator.py` handles per-expert client selection for heterogeneous models. `DebatePhase` gets a `_select_peers()` method and conditional findings routing for sparse topology. All defaults maintain backward compatibility.

**Tech Stack:** Python 3.10+, dataclasses, `concurrent.futures.ThreadPoolExecutor`, `OllamaClient`

---

## File Structure

| File | Change |
|------|--------|
| `ai_delegate/models.py` | Add 2 fields to `TaskConfig` |
| `ai_delegate/debate/orchestrator.py` | Add `_resolve_client()` module helper; add `_select_peers()` to `DebatePhase`; update `ExpertRunner._run_single_expert()` and `DebatePhase.run()` |
| `tests/test_orchestrator.py` | Add tests for both features |

---

## Task 1: Extend TaskConfig with Two New Fields

**Files:**

- Modify: `ai_delegate/models.py:196`
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for new TaskConfig fields**

Add to `tests/test_orchestrator.py` inside a new class `TestTaskConfigNewFields`:

```python
class TestTaskConfigNewFields:
    """Tests for new TaskConfig debate quality fields."""

    def test_expert_models_defaults_to_empty_dict(self):
        config = TaskConfig.from_task_type("audit")
        assert config.expert_models == {}

    def test_sparse_topology_k_defaults_to_none(self):
        config = TaskConfig.from_task_type("audit")
        assert config.sparse_topology_k is None

    def test_expert_models_can_be_set(self):
        config = TaskConfig.from_task_type("audit")
        config.expert_models = {"owasp": "gpt-4o", "auth": "gemini-2.5-pro"}
        assert config.expert_models["owasp"] == "gpt-4o"

    def test_sparse_topology_k_can_be_set(self):
        config = TaskConfig.from_task_type("audit")
        config.sparse_topology_k = 2
        assert config.sparse_topology_k == 2
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_orchestrator.py::TestTaskConfigNewFields -v
```

Expected: `FAILED` — `TaskConfig` has no `expert_models` attribute.

- [ ] **Step 3: Add two fields to TaskConfig**

In `ai_delegate/models.py`, after line 196 (`always_deep: bool = False`):

```python
    always_deep: bool = False  # Some tasks always use DEEP tier
    expert_models: Dict[str, str] = field(default_factory=dict)
    # Maps expert_name -> model_name override.
    # Empty dict (default) means all experts share the session-wide client.
    # Example: {"owasp": "gpt-4o", "auth": "gemini-2.5-pro"}
    sparse_topology_k: Optional[int] = None
    # None = full peer visibility (default). Integer = each expert sees k peers (round-robin).
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_orchestrator.py::TestTaskConfigNewFields -v
```

Expected: 4 PASSED.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/models.py tests/test_orchestrator.py
git commit -m "feat: add expert_models and sparse_topology_k fields to TaskConfig"
```

---

## Task 2: Heterogeneous Models

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:55` (after `build_findings` function)
- Modify: `ai_delegate/debate/orchestrator.py:249` (`_run_single_expert` client call)
- Modify: `ai_delegate/debate/orchestrator.py:455` (`DebatePhase._debate_one` client call)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for heterogeneous models**

Add to `tests/test_orchestrator.py`:

```python
class TestHeterogeneousModels:
    """Tests for per-expert model assignment."""

    @pytest.fixture
    def audit_config_with_models(self) -> TaskConfig:
        config = TaskConfig.from_task_type("audit")
        config.expert_models = {"owasp": "gpt-4o"}
        return config

    def test_resolve_client_returns_base_when_no_override(self):
        """_resolve_client returns base_client when expert not in expert_models."""
        from ai_delegate.debate.orchestrator import _resolve_client

        base_client = Mock(spec=OllamaClient)
        base_client.model = "kimi-k2.5:cloud"
        config = TaskConfig.from_task_type("audit")  # expert_models = {}

        result = _resolve_client(base_client, config, "owasp")

        assert result is base_client

    def test_resolve_client_returns_base_when_same_model(self):
        """_resolve_client returns base_client when expert model matches base."""
        from ai_delegate.debate.orchestrator import _resolve_client

        base_client = Mock(spec=OllamaClient)
        base_client.model = "gpt-4o"
        config = TaskConfig.from_task_type("audit")
        config.expert_models = {"owasp": "gpt-4o"}  # Same as base

        result = _resolve_client(base_client, config, "owasp")

        assert result is base_client

    def test_resolve_client_creates_new_client_for_different_model(self):
        """_resolve_client creates new OllamaClient when expert has different model."""
        from ai_delegate.debate.orchestrator import _resolve_client

        base_client = Mock(spec=OllamaClient)
        base_client.model = "kimi-k2.5:cloud"
        base_client.fallback_model = "sonnet"
        base_client.cli_type = "ollama"
        base_client.verbose = False
        config = TaskConfig.from_task_type("audit")
        config.expert_models = {"owasp": "gpt-4o"}

        with patch("ai_delegate.debate.orchestrator.OllamaClient") as MockClient:
            MockClient.return_value = Mock(spec=OllamaClient)
            result = _resolve_client(base_client, config, "owasp")

            MockClient.assert_called_once_with(
                model="gpt-4o",
                fallback_model="sonnet",
                verbose=False,
                cli_type="ollama",
            )
            assert result is not base_client

    def test_expert_runner_uses_per_expert_client(self, audit_config_with_models):
        """ExpertRunner uses different client for owasp expert."""
        call_models = []

        def track_model(prompt):
            return {"findings": []}

        base_client = Mock(spec=OllamaClient)
        base_client.model = "kimi-k2.5:cloud"
        base_client.fallback_model = "sonnet"
        base_client.cli_type = "ollama"
        base_client.verbose = False
        base_client.run_json.side_effect = track_model

        with patch("ai_delegate.debate.orchestrator.OllamaClient") as MockClient:
            per_expert_client = Mock(spec=OllamaClient)
            per_expert_client.run_json.return_value = {"findings": []}
            MockClient.return_value = per_expert_client

            runner = ExpertRunner(base_client, audit_config_with_models)
            runner.run_parallel("test code")

            # OllamaClient should have been constructed once (for owasp override)
            MockClient.assert_called_once_with(
                model="gpt-4o",
                fallback_model="sonnet",
                verbose=False,
                cli_type="ollama",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_orchestrator.py::TestHeterogeneousModels -v
```

Expected: `FAILED` — `_resolve_client` does not exist.

- [ ] **Step 3: Add `_resolve_client()` module-level helper**

In `ai_delegate/debate/orchestrator.py`, after `build_findings()` (after line 54, before `class ConsensusCalculator`):

```python
def _resolve_client(
    base_client: "OllamaClient",
    task_config: "TaskConfig",
    expert_name: str,
) -> "OllamaClient":
    """
    Return the appropriate client for an expert.

    If task_config.expert_models has a model override for this expert AND it
    differs from the base client's model, create and return a new OllamaClient
    with the override model. Otherwise return base_client unchanged.

    Args:
        base_client: Session-wide client (default for all experts)
        task_config: Task config that may contain expert_models overrides
        expert_name: Name of the expert (e.g., "owasp", "auth")

    Returns:
        base_client if no override; new OllamaClient if override differs
    """
    model = task_config.expert_models.get(expert_name)
    if not model or model == getattr(base_client, "model", None):
        return base_client
    return OllamaClient(
        model=model,
        fallback_model=getattr(base_client, "fallback_model", "sonnet"),
        verbose=getattr(base_client, "verbose", False),
        cli_type=getattr(base_client, "cli_type", "ollama"),
    )
```

- [ ] **Step 4: Update `ExpertRunner._run_single_expert()` to use per-expert client**

In `ai_delegate/debate/orchestrator.py` at line 249, replace:

```python
        try:
            output = self.client.run_json(prompt)
```

with:

```python
        try:
            client = _resolve_client(self.client, self.task_config, expert_name)
            output = client.run_json(prompt)
```

- [ ] **Step 5: Update `DebatePhase._debate_one()` closure to use per-expert client**

In `ai_delegate/debate/orchestrator.py` inside `DebatePhase.run()`, the `_debate_one` closure (around line 454-455):

Replace:

```python
            try:
                output = self.client.run_json(prompt)
```

with:

```python
            try:
                client = _resolve_client(self.client, self.task_config, result.expert_name)
                output = client.run_json(prompt)
```

- [ ] **Step 6: Run tests to verify they pass**

```bash
pytest tests/test_orchestrator.py::TestHeterogeneousModels -v
```

Expected: All PASSED.

- [ ] **Step 7: Run full suite to verify no regressions**

```bash
pytest tests/ -x -q
```

Expected: All existing tests pass.

- [ ] **Step 8: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: heterogeneous models — per-expert model assignment via expert_models"
```

---

## Task 3: Sparse Topology

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:416` (`DebatePhase` class)
- Test: `tests/test_orchestrator.py`

- [ ] **Step 1: Write failing tests for `_select_peers()`**

Add to `tests/test_orchestrator.py`:

```python
class TestSparseTopology:
    """Tests for sparse topology peer selection and debate filtering."""

    @pytest.fixture
    def mock_client(self) -> Any:
        client = Mock(spec=OllamaClient)
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "Test"}]
        }
        return client

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        return TaskConfig.from_task_type("audit")

    # --- _select_peers unit tests ---

    def test_select_peers_basic(self, mock_client, audit_config):
        """Expert 0 with k=2, N=3 sees peers 1 and 2."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(0, 3, 2) == [1, 2]

    def test_select_peers_wraps_around(self, mock_client, audit_config):
        """Expert 2 with k=2, N=3 wraps around to peers 0 and 1."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(2, 3, 2) == [0, 1]

    def test_select_peers_middle(self, mock_client, audit_config):
        """Expert 1 with k=2, N=4 sees peers 2 and 3."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(1, 4, 2) == [2, 3]

    def test_select_peers_caps_at_n_minus_1(self, mock_client, audit_config):
        """k >= N-1 returns all peers (full visibility)."""
        phase = DebatePhase(mock_client, audit_config)
        # k=5 with N=3: only 2 peers exist
        result = phase._select_peers(0, 3, 5)
        assert sorted(result) == [1, 2]

    def test_select_peers_k_equals_1(self, mock_client, audit_config):
        """k=1 returns exactly 1 peer."""
        phase = DebatePhase(mock_client, audit_config)
        result = phase._select_peers(0, 3, 1)
        assert len(result) == 1
        assert result == [1]

    # --- Integration: DebatePhase.run() with sparse topology ---

    def test_debate_phase_full_topology_by_default(self, mock_client, audit_config):
        """sparse_topology_k=None uses shared all_findings_str (full visibility)."""
        assert audit_config.sparse_topology_k is None

        expert_results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="audit",
                findings=[Finding(severity="high", issue="SQL injection")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="audit",
                findings=[Finding(severity="medium", issue="Auth bypass")],
                raw_output='{"findings": []}',
            ),
        ]

        phase = DebatePhase(mock_client, audit_config)
        results = phase.run(expert_results)

        assert len(results) == 2

    def test_debate_phase_sparse_topology_k2(self, mock_client, audit_config, sample_code):
        """sparse_topology_k=2 each expert sees exactly 2 peers' findings in prompt."""
        audit_config.sparse_topology_k = 2

        prompts_seen = []

        def capture_prompt(prompt):
            prompts_seen.append(prompt)
            return {"findings": [{"severity": "high", "issue": "Test"}]}

        mock_client.run_json.side_effect = capture_prompt

        expert_results = [
            ExpertResult(
                expert_name=name,
                expert_type="audit",
                findings=[Finding(severity="medium", issue=f"Issue from {name}")],
                raw_output=f'{{"findings": [{{"severity": "medium", "issue": "Issue from {name}"}}]}}',
            )
            for name in ["owasp", "auth", "input"]
        ]

        phase = DebatePhase(mock_client, audit_config)
        results = phase.run(expert_results)

        assert len(results) == 3
        # Each prompt should be called — 3 experts × 1 round
        assert len(prompts_seen) == 3

    def test_debate_phase_sparse_k1_each_expert_sees_one_peer(
        self, mock_client, audit_config
    ):
        """sparse_topology_k=1: each expert prompt contains exactly 1 peer heading."""
        audit_config.sparse_topology_k = 1

        prompts_by_expert = {}

        def capture_by_expert(prompt):
            # Track which expert this was called for based on prompt content
            prompts_by_expert[len(prompts_by_expert)] = prompt
            return {"findings": []}

        mock_client.run_json.side_effect = capture_by_expert

        expert_results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="audit",
                findings=[],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="audit",
                findings=[],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="input",
                expert_type="audit",
                findings=[],
                raw_output='{"findings": []}',
            ),
        ]

        phase = DebatePhase(mock_client, audit_config)
        results = phase.run(expert_results)

        assert len(results) == 3
        # Each prompt should contain exactly 1 "### X Expert:" heading
        for prompt in prompts_by_expert.values():
            expert_section_count = prompt.count("### ")
            assert expert_section_count == 1, (
                f"Expected 1 peer section (k=1), got {expert_section_count}"
            )
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_orchestrator.py::TestSparseTopology -v
```

Expected: `FAILED` — `DebatePhase` has no `_select_peers` method.

- [ ] **Step 3: Add `_select_peers()` to `DebatePhase`**

In `ai_delegate/debate/orchestrator.py` inside `DebatePhase`, add after `__init__` (after line 414):

```python
    def _select_peers(self, expert_idx: int, total: int, k: int) -> List[int]:
        """
        Select k peer indices for an expert using deterministic round-robin.

        Each expert sees the k experts that follow it in the list (wrapping around).
        This ensures every expert pair has symmetric visibility when k = total-1
        and gives consistent, reproducible debate topology for any k.

        Args:
            expert_idx: Index of the current expert (0 to total-1)
            total: Total number of experts
            k: Desired number of peers to see

        Returns:
            Sorted list of peer indices (length min(k, total-1))
        """
        actual_k = min(k, total - 1)
        return sorted((expert_idx + i + 1) % total for i in range(actual_k))
```

- [ ] **Step 4: Update `DebatePhase.run()` to support sparse topology**

In `ai_delegate/debate/orchestrator.py`, inside `DebatePhase.run()`:

Replace the current block (lines ~432-452):

```python
        # Build ONE shared findings string — O(n) total, O(1) lookup per expert.
        # Each expert sees all findings including their own in "other experts" section,
        # but their own findings are already in "Your initial findings" so LLM handles this fine.
        all_findings_str = build_findings(expert_results)

        def _debate_one(result: ExpertResult) -> ExpertResult:
            prompt = f"""You are the {result.expert_name} Expert.

Your initial findings:
{result.raw_output}

Other experts' findings:
{all_findings_str}

Instructions:
1. Compare your findings with other experts
2. Identify duplicate or related issues
3. Validate ratings
4. Propose consolidated findings

Output your revised analysis as JSON."""

            try:
                client = _resolve_client(self.client, self.task_config, result.expert_name)
                output = client.run_json(prompt)
```

with:

```python
        # Build shared findings string for full topology (O(n) total).
        all_findings_str = build_findings(expert_results)

        # Sparse topology: pre-compute per-expert findings map if k is set.
        k = self.task_config.sparse_topology_k
        if k is not None:
            peer_findings: Dict[str, str] = {}
            for idx, r in enumerate(valid_results):
                peer_idxs = self._select_peers(idx, len(valid_results), k)
                peer_findings[r.expert_name] = build_findings(
                    [valid_results[i] for i in peer_idxs]
                )
        else:
            peer_findings = {r.expert_name: all_findings_str for r in valid_results}

        def _debate_one(result: ExpertResult) -> ExpertResult:
            findings_str = peer_findings[result.expert_name]
            prompt = f"""You are the {result.expert_name} Expert.

Your initial findings:
{result.raw_output}

Other experts' findings:
{findings_str}

Instructions:
1. Compare your findings with other experts
2. Identify duplicate or related issues
3. Validate ratings
4. Propose consolidated findings

Output your revised analysis as JSON."""

            try:
                client = _resolve_client(self.client, self.task_config, result.expert_name)
                output = client.run_json(prompt)
```

Note: Also add `Dict` to the imports at the top of the `run()` method if not already present in the function body. `Dict` is already imported at module level from `typing`.

- [ ] **Step 5: Run sparse topology tests**

```bash
pytest tests/test_orchestrator.py::TestSparseTopology -v
```

Expected: All PASSED.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -x -q
```

Expected: All tests pass. Count should be ≥ 489 (485 existing + new tests).

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: sparse topology — each expert sees k peers in debate (round-robin)"
```
