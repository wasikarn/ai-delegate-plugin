# AgentExecutor (Path B) Design

**Goal:** Add Path B execution — `ollama launch claude --model kimi-k2.5:cloud` — so domain experts can self-explore the codebase with real tool access at budget model cost.

**Architecture:** `AgentExecutor` wraps a single subprocess call. `AgentPool` runs N executors in parallel with `ThreadPoolExecutor`. `ModelAssigner` routes each expert to the right path (A/B/C) based on tool requirements and complexity.

**Tech Stack:** Python 3.10+, `subprocess`, `ThreadPoolExecutor`, `ollama launch claude`, kimi-k2.5:cloud

---

## Context: Three Execution Paths

| Path | Mechanism | Model | Tools | Use When |
|------|-----------|-------|-------|----------|
| A | Anthropic SDK → localhost:11434 | kimi/glm | None | Expert receives content as text — no file access needed |
| **B (NEW)** | `ollama launch claude` subprocess | kimi-k2.5:cloud | Read, Grep, Glob | Expert self-explores repo — file access needed, standard reasoning |
| C | Claude Code `Agent` tool | Sonnet | All | Architecture, migration, complex security — Claude-level reasoning required |

**Adjudicator:** Always Sonnet — synthesizes final verdict across all expert findings.

---

## Routing Decision (ModelAssigner)

```
agent.tools ∩ {Read, Glob, Grep, Bash} = ∅
    → Path A (SDK, no tools)

agent.tools ∩ {Read, Glob, Grep, Bash} ≠ ∅
    AND (domain ∈ {architecture, migration} OR complexity.level == "high")
    → Path C (Agent tool, Sonnet)

agent.tools ∩ {Read, Glob, Grep, Bash} ≠ ∅
    AND domain ∉ {architecture, migration} AND complexity.level ∈ {low, medium}
    → Path B (ollama launch claude, kimi)
```

---

## Components

### `AgentExecutorConfig`

```python
@dataclass
class AgentExecutorConfig:
    repo_path: Path
    allowed_tools: list[str] = field(default_factory=lambda: ["Read", "Grep", "Glob"])
    budget_usd: float = 0.20
    timeout_sec: int = 120
    effort: str = "low"          # 58% fewer tokens vs default
```

**Rationale for defaults:**

- `allowed_tools`: Read/Grep/Glob cover 95% of analysis needs. No Bash (security).
- `budget_usd=0.20`: Hard cap per expert. At $0.06/run with `--effort low`, gives 3× headroom.
- `effort="low"`: Validated to reduce tokens from ~23k → ~10k without quality loss on analysis tasks.
- `--bare`: Skips hooks/plugins/CLAUDE.md — reduces tokens ~6× vs normal mode.

---

### `AgentExecutor`

Single responsibility: run one Path B expert and return `ExpertResult`.

```python
class AgentExecutor:
    def __init__(self, config: AgentExecutorConfig) -> None:
        self.config = config

    def run(self, assignment: ExpertAssignment, task: str) -> ExpertResult:
        """Run one Path B agent. Returns ExpertResult. Raises on subprocess failure."""
        cmd = self._build_cmd(assignment, task)
        raw = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_sec,
        )
        if raw.returncode != 0:
            raise RuntimeError(f"Agent {assignment.agent.name} failed: {raw.stderr[:200]}")

        result_text = json.loads(raw.stdout)["result"]
        findings = self._parse_findings(result_text, assignment.agent.name)
        return ExpertResult(
            expert_name=assignment.agent.name,
            expert_type=assignment.agent.domains[0] if assignment.agent.domains else "general",
            findings=findings,
        )

    def _build_cmd(self, assignment: ExpertAssignment, task: str) -> list[str]:
        return [
            "ollama", "launch", "claude",
            "--model", assignment.model,
            "--yes", "--",
            "-p", task,
            "--add-dir", str(self.config.repo_path),
            "--output-format", "json",
            "--allowedTools", ",".join(self.config.allowed_tools),
            "--bare",
            "--dangerously-skip-permissions",
            "--system-prompt", self._system_prompt(assignment.agent),
            "--max-budget-usd", str(self.config.budget_usd),
            "--effort", self.config.effort,
        ]

    def _system_prompt(self, agent: AgentMetadata) -> str:
        return (
            f"You are {agent.name}. {agent.description}\n"
            "Respond with valid JSON only — no markdown, no explanation.\n"
            'Format: {"findings": [{"severity": "high|medium|low", '
            '"issue": "...", "recommendation": "..."}]}'
        )

    def _parse_findings(self, result_text: str, agent_name: str) -> list[Finding]:
        """Parse JSON findings from result text. Returns [] on parse failure.

        normalize_finding is imported from consensus.py (already in codebase).
        """
        try:
            data = json.loads(result_text)
            raw_findings = data.get("findings", [])
            return [normalize_finding(f) for f in raw_findings if isinstance(f, dict)]
        except Exception as e:
            logger.warning("Could not parse findings from %s: %s", agent_name, e)
            return []
```

**Security note:** `_build_cmd` always uses list args (never `shell=True`). `assignment.model` comes from `AgentMetadata.model` which was validated by `validate_agent_name()` in `catalog.py`.

---

### `AgentPool`

Single responsibility: run N `AgentExecutor` calls in parallel, skip failures.

```python
class AgentPool:
    def __init__(
        self,
        executor: AgentExecutor,
        max_workers: int = WorkerConstants.DEFAULT_MAX_WORKERS,
    ) -> None:
        self._executor = executor
        self._max_workers = max_workers

    def run_parallel(
        self,
        assignments: list[ExpertAssignment],
        task: str,
    ) -> list[ExpertResult]:
        """Run all Path B assignments in parallel. Failed agents are skipped (logged)."""
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._executor.run, assignment, task): assignment
                for assignment in assignments
            }
            results: list[ExpertResult] = []
            for future in as_completed(futures):
                assignment = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.warning(
                        "Expert %s failed — skipping: %s",
                        assignment.agent.name, e,
                    )
        return results
```

**Design decision:** Failed experts are skipped, not re-raised. A partial result set is better than crashing the entire debate. Caller (orchestrator) must handle `results == []`.

---

### `ExpertAssignment` (data model)

Returned by `ModelAssigner.assign()`. Lives in `model_assigner.py`.

```python
@dataclass
class ExpertAssignment:
    agent: AgentMetadata
    path: ExecutionPath
    model: str          # resolved model name, after overrides applied
```

### `ExecutionPath` (enum)

Lives in `model_assigner.py` (not `models.py`).

```python
class ExecutionPath(str, Enum):
    SDK   = "sdk"    # Path A — Anthropic SDK → localhost:11434
    CLI   = "cli"    # Path B — ollama launch claude subprocess
    AGENT = "agent"  # Path C — Claude Code Agent tool (Sonnet)
```

---

### `ModelAssigner`

Routes each agent to Path A, B, or C.

```python
FILE_ACCESS_TOOLS = frozenset({"Read", "Glob", "Grep", "Bash"})
DEEP_DOMAINS = frozenset({"architecture", "migration"})


class ModelAssigner:
    @staticmethod
    def assign(
        agent: AgentMetadata,
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> ExpertAssignment:
        overrides = model_overrides or {}
        needs_file_access = bool(set(agent.tools) & FILE_ACCESS_TOOLS)
        needs_deep = bool(set(agent.domains) & DEEP_DOMAINS)
        is_complex = complexity.level == "high"

        if not needs_file_access:
            path = ExecutionPath.SDK
            default_model = agent.model or Models.KIMI_K25_CLOUD
        elif needs_deep or is_complex:
            path = ExecutionPath.AGENT
            default_model = agent.model or Models.CLAUDE_SONNET
        else:
            path = ExecutionPath.CLI        # Path B
            default_model = agent.model or Models.KIMI_K25_CLOUD

        return ExpertAssignment(
            agent=agent,
            path=path,
            model=overrides.get(agent.name, default_model),
        )

    @staticmethod
    def assign_all(
        agents: list[AgentMetadata],
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> list[ExpertAssignment]:
        return [ModelAssigner.assign(a, complexity, model_overrides) for a in agents]
```

---

## Data Flow (end-to-end)

```
task = "audit src/auth.py for security issues"
repo_path = Path("/Users/.../my-project")

ComplexityAssessor.assess_files([src/auth.py])
→ ComplexityScore(level="medium", domains=["security"], line_count=180)

AgentCatalog.for_domains(["security"])
→ [AgentMetadata(name="owasp-expert", tools=["Read","Grep"], domains=["security"]),
   AgentMetadata(name="auth-expert",  tools=["Read"],        domains=["security"])]

ModelAssigner.assign_all(agents, complexity)
→ [ExpertAssignment(agent=owasp-expert, path=CLI, model="kimi-k2.5:cloud"),
   ExpertAssignment(agent=auth-expert,  path=CLI, model="kimi-k2.5:cloud")]

AgentPool.run_parallel(assignments, task)   # ~15s wall time
→ [ExpertResult(expert_name="owasp-expert", findings=[...]),
   ExpertResult(expert_name="auth-expert",  findings=[...])]

ConsensusCalculator.calculate(results)
→ ConsensusResult(score=0.85, tier=STANDARD)

score < 0.90 → Adjudicator(model=Sonnet).synthesize(results, consensus)
→ Final Verdict
```

---

## Error Handling

| Scenario | Behaviour |
|----------|-----------|
| subprocess timeout (>120s) | `ExpertResult` skipped, warning logged, consensus runs with remaining experts |
| `ollama` not in PATH | `RuntimeError("ollama not found")` raised before any agent is spawned |
| `--max-budget-usd` exceeded | Agent exits naturally, result may be partial — `_parse_findings` returns `[]` |
| JSON parse failure | Warning logged, `ExpertResult(findings=[])` returned — no crash |
| All experts fail | `ConsensusCalculator.calculate([])` → score=0.0 — orchestrator handles empty result |
| returncode != 0 | `RuntimeError` raised from `AgentExecutor.run()`, caught by `AgentPool` |

---

## Testing Strategy

### `tests/test_agent_executor.py`

Unit tests with `subprocess.run` patched:

```python
def test_run_returns_expert_result(mock_subprocess):
    mock_subprocess.return_value.stdout = json.dumps({
        "result": '{"findings": [{"severity": "high", "issue": "SQL injection", "recommendation": "use params"}]}'
    })
    mock_subprocess.return_value.returncode = 0
    result = executor.run(assignment, task="audit src/")
    assert result.expert_name == "owasp-expert"
    assert len(result.findings) == 1
    assert result.findings[0].severity == "high"

def test_run_raises_on_nonzero_returncode(mock_subprocess):
    mock_subprocess.return_value.returncode = 1
    mock_subprocess.return_value.stderr = "model not found"
    with pytest.raises(RuntimeError, match="failed"):
        executor.run(assignment, task="audit")

def test_run_returns_empty_findings_on_parse_failure(mock_subprocess):
    mock_subprocess.return_value.stdout = json.dumps({"result": "not json"})
    mock_subprocess.return_value.returncode = 0
    result = executor.run(assignment, task="audit")
    assert result.findings == []

def test_build_cmd_includes_required_flags(executor, assignment):
    cmd = executor._build_cmd(assignment, task="audit src/")
    assert "--bare" in cmd
    assert "--dangerously-skip-permissions" in cmd
    assert "--output-format" in cmd
    assert "json" in cmd
    assert "ollama" == cmd[0]
    assert "shell=True" not in str(cmd)   # never shell=True
```

### `tests/test_agent_pool.py`

```python
def test_run_parallel_skips_failed_agent(mock_executor):
    mock_executor.run.side_effect = [
        ExpertResult(expert_name="ok", expert_type="security", findings=[]),
        RuntimeError("timeout"),
    ]
    results = pool.run_parallel([assignment1, assignment2], task="audit")
    assert len(results) == 1

def test_run_parallel_returns_all_on_success(mock_executor):
    mock_executor.run.return_value = ExpertResult(...)
    results = pool.run_parallel([a1, a2, a3], task="audit")
    assert len(results) == 3

def test_run_parallel_empty_assignments(pool):
    assert pool.run_parallel([], task="audit") == []
```

### `tests/test_model_assigner.py`

```python
def test_no_file_tools_routes_to_sdk():
    agent = AgentMetadata(tools=[])
    assignment = ModelAssigner.assign(agent, ComplexityScore(level="high"))
    assert assignment.path == ExecutionPath.SDK

def test_file_tools_medium_complexity_routes_to_cli():
    agent = AgentMetadata(tools=["Read", "Grep"], domains=["security"])
    assignment = ModelAssigner.assign(agent, ComplexityScore(level="medium"))
    assert assignment.path == ExecutionPath.CLI

def test_deep_domain_routes_to_agent():
    agent = AgentMetadata(tools=["Read"], domains=["architecture"])
    assignment = ModelAssigner.assign(agent, ComplexityScore(level="low"))
    assert assignment.path == ExecutionPath.AGENT

def test_high_complexity_with_file_tools_routes_to_agent():
    agent = AgentMetadata(tools=["Read"], domains=["security"])
    assignment = ModelAssigner.assign(agent, ComplexityScore(level="high"))
    assert assignment.path == ExecutionPath.AGENT

def test_model_override_applied():
    agent = AgentMetadata(name="owasp-expert", tools=["Read"], domains=["security"])
    assignment = ModelAssigner.assign(
        agent, ComplexityScore(level="medium"),
        model_overrides={"owasp-expert": "claude-sonnet-4-6"}
    )
    assert assignment.model == "claude-sonnet-4-6"
```

---

## File Structure

```
ai_delegate/
  agent_executor.py     # AgentExecutorConfig, AgentExecutor, AgentPool (NEW)
  model_assigner.py     # ExecutionPath, ExpertAssignment, ModelAssigner (NEW)
  catalog.py            # AgentCatalog (Phase 1A — done)
  consensus.py          # ConsensusCalculator (Phase 1A — done)
  complexity.py         # ComplexityAssessor (Phase 1A — done)
  client.py             # BackendClient (Path A — unchanged)

tests/
  test_agent_executor.py   # NEW
  test_agent_pool.py       # NEW
  test_model_assigner.py   # NEW
```

`ExecutionPath` and `ExpertAssignment` live in `model_assigner.py` (NOT `models.py`).

---

## Constants to Add

```python
# constants.py
class Models:
    KIMI_K25_CLOUD = "kimi-k2.5:cloud"   # already exists
    CLAUDE_SONNET = "sonnet"              # already exists

class AgentExecutorDefaults:
    ALLOWED_TOOLS = ["Read", "Grep", "Glob"]
    BUDGET_USD = 0.20
    TIMEOUT_SEC = 120
    EFFORT = "low"
```

---

## What Does NOT Change

- `BackendClient` — Path A unchanged
- `ConsensusCalculator` — unchanged
- `AgentCatalog` — unchanged
- `ComplexityAssessor` — unchanged
- Orchestrator agent prompt — will need `path=cli` branch added (separate task)
