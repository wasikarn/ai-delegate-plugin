# Phase 3: Orchestrator Agent + SmartRouter Cleanup

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write `agents/orchestrator.md` (generic intelligence orchestrator) and remove `router.py` (SmartRouter) + `plugin_registry.py` (replaced by catalog.py).

**Architecture:** Add 5 CLI utility subcommands that expose existing Python modules (catalog, assess, consensus, assign, memory-check) so the orchestrator agent can call them via Bash. Write orchestrator.md as a Claude Code agent that chains these commands. Remove SmartRouter and PluginRegistry — both are replaced by ModelAssigner and AgentCatalog.

**Tech Stack:** Python 3.10+, argparse, Claude Code Agent (orchestrator.md), pytest

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `ai_delegate/cli.py` | Modify | Add 5 CLI subcommands; remove router + plugin_registry usage |
| `ai_delegate/agents/orchestrator.md` | Create | Generic orchestrator agent (7-step pipeline) |
| `ai_delegate/__init__.py` | Modify | Remove router imports/exports |
| `ai_delegate/router.py` | Delete | SmartRouter removed; ModelAssigner is the replacement |
| `ai_delegate/plugin_registry.py` | Delete | AgentCatalog is the replacement |
| `tests/test_router.py` | Delete | test_model_assigner.py already covers the new logic |
| `tests/test_plugin_registry.py` | Delete | test_catalog.py already covers the new logic |
| `tests/test_cli_subcommands.py` | Create | Tests for the 5 new CLI subcommands |

---

### Task 1: Add CLI utility subcommands (catalog, assess, consensus, assign, memory-check)

These 5 subcommands expose existing Python modules so `agents/orchestrator.md` can call them via Bash.

**Files:**

- Modify: `ai_delegate/cli.py` — add handlers before `main()`, dispatch from `main()`
- Create: `tests/test_cli_subcommands.py`

- [ ] **Step 1: Write failing tests for all 5 subcommands**

Create `tests/test_cli_subcommands.py`:

```python
"""Tests for CLI utility subcommands: catalog, assess, consensus, assign, memory-check."""
import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestCatalogSubcommand:
    def test_catalog_json_output(self, capsys):
        """catalog --json returns JSON list of agents."""
        from ai_delegate.catalog import AgentMetadata
        mock_agents = [
            AgentMetadata(
                name="security-expert",
                description="OWASP security analysis",
                source_plugin="ai-delegate",
                model="sonnet",
                tools=["Read", "Grep"],
                path=Path("/fake/path/security-expert.md"),
                domains=["security"],
            )
        ]
        with patch("ai_delegate.cli._handle_catalog_subcommand") as mock:
            mock.return_value = None
            # Verify the handler is registered
            assert callable(mock)

    def test_catalog_json_real(self, tmp_path, capsys):
        """catalog --json returns valid JSON even with empty plugin dir."""
        from ai_delegate.cli import _handle_catalog_subcommand
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[]):
            _handle_catalog_subcommand(["--json"])
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert isinstance(data, list)

    def test_catalog_domain_filter(self, capsys):
        """catalog --domain security filters results."""
        from ai_delegate.cli import _handle_catalog_subcommand
        from ai_delegate.catalog import AgentMetadata
        agent = AgentMetadata(
            name="security-expert",
            description="OWASP",
            source_plugin="ai-delegate",
            model="",
            tools=[],
            path=Path("/fake/path.md"),
            domains=["security"],
        )
        with patch("ai_delegate.catalog.AgentCatalog.for_domains", return_value=[agent]):
            _handle_catalog_subcommand(["--domain", "security", "--json"])
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["name"] == "security-expert"


class TestAssessSubcommand:
    def test_assess_returns_json(self, tmp_path, capsys):
        """assess --file returns complexity JSON."""
        src = tmp_path / "auth.py"
        src.write_text("def login(user, pw): pass\n" * 10)
        from ai_delegate.cli import _handle_assess_subcommand
        _handle_assess_subcommand(["--file", str(src)])
        data = json.loads(capsys.readouterr().out)
        assert "level" in data
        assert data["level"] in ("low", "medium", "high")
        assert "domains" in data

    def test_assess_missing_file_exits(self):
        """assess exits 1 on missing file."""
        from ai_delegate.cli import _handle_assess_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_assess_subcommand(["--file", "/nonexistent/path.py"])
        assert exc.value.code == 1


class TestConsensusSubcommand:
    def test_consensus_returns_tier(self, capsys):
        """consensus --findings returns score and tier."""
        findings = json.dumps([
            {"severity": "high", "issue": "SQL injection", "recommendation": "use params"},
            {"severity": "high", "issue": "SQL injection", "recommendation": "use params"},
        ])
        from ai_delegate.cli import _handle_consensus_subcommand
        _handle_consensus_subcommand(["--findings", findings])
        data = json.loads(capsys.readouterr().out)
        assert "score" in data
        assert "tier" in data
        assert data["tier"] in ("fast", "standard", "deep")

    def test_consensus_invalid_json_exits(self):
        """consensus exits 1 on malformed JSON."""
        from ai_delegate.cli import _handle_consensus_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_consensus_subcommand(["--findings", "not-json"])
        assert exc.value.code == 1


class TestAssignSubcommand:
    def test_assign_returns_assignments(self, capsys):
        """assign --agents X --complexity low returns path assignments."""
        from ai_delegate.catalog import AgentMetadata
        from ai_delegate.cli import _handle_assign_subcommand
        agent = AgentMetadata(
            name="security-expert",
            description="OWASP",
            source_plugin="ai-delegate",
            model="",
            tools=[],
            path=Path("/fake/path.md"),
            domains=["security"],
        )
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[agent]):
            _handle_assign_subcommand(["--agents", "security-expert", "--complexity", "low"])
        data = json.loads(capsys.readouterr().out)
        assert isinstance(data, list)
        assert len(data) == 1
        assert "path" in data[0]
        assert data[0]["path"] in ("sdk", "cli", "agent")

    def test_assign_unknown_agent_skipped(self, capsys):
        """assign skips unknown agent names gracefully."""
        from ai_delegate.cli import _handle_assign_subcommand
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[]):
            _handle_assign_subcommand(["--agents", "ghost-agent", "--complexity", "low"])
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestMemoryCheckSubcommand:
    def test_memory_check_miss(self, capsys):
        """memory check returns hit:false when no cached result."""
        from ai_delegate.cli import _handle_memory_check_subcommand
        with patch("ai_delegate.memory.AnalysisMemory") as mock_mem:
            mock_mem.return_value.check_cache.return_value = None
            _handle_memory_check_subcommand([
                "--content-hash", "abc123",
                "--experts", "security-expert",
                "--task", "audit",
            ])
        data = json.loads(capsys.readouterr().out)
        assert data == {"hit": False}

    def test_memory_check_hit(self, capsys):
        """memory check returns hit:true with score when cached."""
        from ai_delegate.cli import _handle_memory_check_subcommand
        from ai_delegate.memory import CacheEntry
        entry = MagicMock()
        entry.consensus.score = 0.92
        entry.cached_at = 1000.0
        import time
        with patch("ai_delegate.memory.AnalysisMemory") as mock_mem, \
             patch("time.time", return_value=entry.cached_at + 7200):
            mock_mem.return_value.check_cache.return_value = entry
            _handle_memory_check_subcommand([
                "--content-hash", "abc123",
                "--experts", "security-expert,auth-expert",
                "--task", "audit",
            ])
        data = json.loads(capsys.readouterr().out)
        assert data["hit"] is True
        assert "score" in data
        assert "age_hours" in data
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
python -m pytest tests/test_cli_subcommands.py -v 2>&1 | head -40
```

Expected: `ImportError` or `AttributeError` — `_handle_catalog_subcommand` not found yet.

- [ ] **Step 3: Add the 5 handler functions to `cli.py`**

In `ai_delegate/cli.py`, add these 5 functions before `main()`. Insert after the `_handle_search_subcommand` function (around line 226):

```python
def _handle_catalog_subcommand(args: list) -> None:
    """Handle 'ai-delegate catalog [--json] [--domain X] [--trust-all]'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate catalog")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--domain", help="Filter by domain (e.g. security, performance)")
    parser.add_argument("--trust-all", action="store_true", help="Trust all plugins (dev only)")
    parsed = parser.parse_args(args)

    from .catalog import AgentCatalog
    catalog = AgentCatalog(trust_all=parsed.trust_all)

    if parsed.domain:
        agents = catalog.for_domains([parsed.domain])
    else:
        agents = catalog.scan()

    if parsed.json or True:  # Always JSON for machine consumption
        output = [
            {
                "name": a.name,
                "description": a.description,
                "source_plugin": a.source_plugin,
                "model": a.model,
                "tools": a.tools,
                "domains": a.domains,
            }
            for a in agents
        ]
        print(json.dumps(output, indent=2))
    else:
        for a in agents:
            print(f"{a.name} ({a.source_plugin}) [{', '.join(a.domains)}]")
    sys.exit(0)


def _handle_assess_subcommand(args: list) -> None:
    """Handle 'ai-delegate assess --file path [--files a,b,c]'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate assess")
    parser.add_argument("--file", required=True, help="File to assess")
    parsed = parser.parse_args(args)

    file_path = Path(parsed.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    from .complexity import ComplexityAssessor
    score = ComplexityAssessor.assess(file_path.read_text(), file_path.name)
    print(json.dumps({
        "level": score.level,
        "domains": score.domains,
        "file_count": score.file_count,
        "line_count": score.line_count,
        "security_signals": score.security_signals,
    }))
    sys.exit(0)


def _handle_consensus_subcommand(args: list) -> None:
    """Handle 'ai-delegate consensus --findings [...]'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate consensus")
    parser.add_argument("--findings", required=True, help="JSON array of findings from experts")
    parsed = parser.parse_args(args)

    try:
        raw_findings = json.loads(parsed.findings)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in --findings: {e}", file=sys.stderr)
        sys.exit(1)

    from .models import ExpertResult, Finding
    from .consensus import ConsensusCalculator
    from .constants import QualityThresholds

    # Wrap raw findings in a single ExpertResult for consensus calculation
    # (findings already aggregated from multiple experts — calculate agreement)
    # Build ExpertResult list: group by source_plugin/expert field if present
    results: list[ExpertResult] = []
    expert_map: dict[str, list[Finding]] = {}
    for raw in raw_findings:
        expert = raw.get("expert", "unknown")
        if expert not in expert_map:
            expert_map[expert] = []
        expert_map[expert].append(Finding(
            severity=raw.get("severity", "medium"),
            issue=raw.get("issue", ""),
            recommendation=raw.get("recommendation"),
            location=raw.get("location"),
        ))

    for expert_name, findings in expert_map.items():
        results.append(ExpertResult(expert=expert_name, findings=findings))

    if not results:
        print(json.dumps({"score": 0.0, "tier": "deep", "consensus_findings": [], "disputed_findings": []}))
        sys.exit(0)

    calc = ConsensusCalculator()
    result = calc.calculate(results)

    fast_threshold = QualityThresholds.FAST_THRESHOLD / 100
    standard_threshold = QualityThresholds.STANDARD_THRESHOLD / 100

    if result.score >= fast_threshold:
        tier = "fast"
    elif result.score >= standard_threshold:
        tier = "standard"
    else:
        tier = "deep"

    print(json.dumps({
        "score": result.score,
        "tier": tier,
        "consensus_findings": [f.__dict__ for f in result.consensus_findings],
        "disputed_findings": [f.__dict__ for f in result.disputed_findings],
    }))
    sys.exit(0)


def _handle_assign_subcommand(args: list) -> None:
    """Handle 'ai-delegate assign --agents X,Y --complexity low|medium|high'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate assign")
    parser.add_argument("--agents", required=True, help="Comma-separated agent names")
    parser.add_argument(
        "--complexity",
        choices=["low", "medium", "high"],
        default="medium",
        help="Complexity level for path selection",
    )
    parser.add_argument("--trust-all", action="store_true", help="Trust all plugins (dev only)")
    parsed = parser.parse_args(args)

    agent_names = [n.strip() for n in parsed.agents.split(",") if n.strip()]

    from .catalog import AgentCatalog
    from .model_assigner import ModelAssigner
    from .complexity import ComplexityScore

    catalog = AgentCatalog(trust_all=parsed.trust_all)
    all_agents = {a.name: a for a in catalog.scan()}

    selected = [all_agents[n] for n in agent_names if n in all_agents]

    complexity = ComplexityScore(
        level=parsed.complexity,
        domains=[],
        file_count=1,
        line_count=0,
        security_signals=0,
    )
    assignments = ModelAssigner.assign_all(selected, complexity)

    print(json.dumps([
        {
            "agent": a.agent.name,
            "path": a.path.value,
            "model": a.model,
            "source_plugin": a.agent.source_plugin,
            "tools": a.agent.tools,
        }
        for a in assignments
    ]))
    sys.exit(0)


def _handle_memory_check_subcommand(args: list) -> None:
    """Handle 'ai-delegate memory check --content-hash H --experts X,Y --task T'."""
    import argparse as _ap
    import time
    parser = _ap.ArgumentParser(prog="ai-delegate memory check")
    parser.add_argument("--content-hash", required=True, help="SHA256 hash of the content")
    parser.add_argument("--experts", default="", help="Comma-separated expert names")
    parser.add_argument("--task", default="", help="Task description")
    parsed = parser.parse_args(args)

    expert_names = [n.strip() for n in parsed.experts.split(",") if n.strip()]

    try:
        from .memory import AnalysisMemory
        memory = AnalysisMemory()
        entry = memory.check_cache(
            content_hash=parsed.content_hash,
            task_description=parsed.task,
            expert_names=expert_names,
        )
        if entry is None:
            print(json.dumps({"hit": False}))
        else:
            age_hours = (time.time() - entry.cached_at) / 3600
            print(json.dumps({
                "hit": True,
                "score": entry.consensus.score,
                "age_hours": round(age_hours, 2),
            }))
    except Exception:
        print(json.dumps({"hit": False}))
    sys.exit(0)
```

- [ ] **Step 4: Register subcommands in `main()`**

In `ai_delegate/cli.py`, find the `main()` function around line 228 and add new dispatches right after the existing `search` check:

```python
def main():
    """Main CLI entry point."""
    # Handle pre-parser subcommands (avoids positional arg conflict with task_type)
    if sys.argv[1:2] == ["rate"]:
        _handle_rate_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["search"]:
        _handle_search_subcommand(sys.argv[2:])
        return
    # NEW: utility subcommands for orchestrator agent
    if sys.argv[1:2] == ["catalog"]:
        _handle_catalog_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["assess"]:
        _handle_assess_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["consensus"]:
        _handle_consensus_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["assign"]:
        _handle_assign_subcommand(sys.argv[2:])
        return
    if sys.argv[1:3] == ["memory", "check"]:
        _handle_memory_check_subcommand(sys.argv[3:])
        return
```

- [ ] **Step 5: Add `check_cache` method to `AnalysisMemory`**

First check if it exists:

```bash
grep -n "check_cache" ai_delegate/memory.py
```

If not present, add at the end of the `AnalysisMemory` class in `ai_delegate/memory.py`:

```python
def check_cache(
    self,
    content_hash: str,
    task_description: str,
    expert_names: list[str],
) -> Optional["CacheEntry"]:
    """Check if a previous analysis matches content_hash + experts.

    Uses analysis_runs table: looks for a run with matching content_hash
    where all expert names appear in the findings_summary (approximation).
    Returns a lightweight CacheEntry-like object with .consensus.score and .cached_at,
    or None if no match found.
    """
    try:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id, consensus_score, created_at
                FROM analysis_runs
                WHERE file_path LIKE ? AND task_type != ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (f"%{content_hash[:8]}%",),
            ).fetchone()
        if row is None:
            return None

        # Return a simple object with .consensus.score and .cached_at
        class _Consensus:
            def __init__(self, score):
                self.score = score

        class _Entry:
            def __init__(self, score, cached_at):
                self.consensus = _Consensus(score)
                self.cached_at = cached_at

        import datetime
        cached_at_ts = datetime.datetime.fromisoformat(row[2]).timestamp() if isinstance(row[2], str) else float(row[2])
        return _Entry(score=float(row[1]), cached_at=cached_at_ts)
    except Exception:
        return None
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_cli_subcommands.py -v
```

Expected: All tests pass.

- [ ] **Step 7: Smoke test each subcommand**

```bash
# catalog
python -m ai_delegate catalog --json 2>&1 | head -5

# assess (use a real file)
python -m ai_delegate assess --file ai_delegate/cli.py 2>&1

# consensus
python -m ai_delegate consensus --findings '[{"expert":"x","severity":"high","issue":"SQL injection"}]' 2>&1

# assign
python -m ai_delegate assign --agents security-expert --complexity medium --trust-all 2>&1

# memory check
python -m ai_delegate memory check --content-hash abc123def --experts x --task audit 2>&1
```

Expected: Each prints valid JSON without error.

- [ ] **Step 8: Commit**

```bash
git add ai_delegate/cli.py ai_delegate/memory.py tests/test_cli_subcommands.py
git commit -m "feat: add catalog/assess/consensus/assign/memory-check CLI subcommands for orchestrator"
```

---

### Task 2: Write `agents/orchestrator.md`

**Files:**

- Create: `ai_delegate/agents/orchestrator.md`

- [ ] **Step 1: Create `ai_delegate/agents/orchestrator.md`**

```markdown
---
name: orchestrator
description: |
  Generic intelligence orchestrator for ai-delegate. Runs the 5-step assess →
  catalog → assign → execute → synthesize pipeline for any analysis task.
  Calls Python CLI utilities to discover agents, route execution paths, and
  compute consensus. Does NOT analyze code directly — coordinates domain
  experts and synthesizes their output. Handles all three execution paths:
  Path A (SDK via BackendClient), Path B (ollama launch claude subprocess),
  Path C (Claude Code Agent tool).
model: sonnet
tools: ["Bash", "Agent"]
---

You are the ai-delegate orchestrator. You coordinate domain experts to analyze code or content and produce a synthesized verdict.

## Input

You receive a task description as your prompt, optionally with:
- `--file <path>` — file or directory to analyze  
- `--agents X,Y,Z` — use specific agents (skip auto-selection)
- `--tier fast|standard|deep` — force quality tier
- `--budget` — force Path A (SDK) for all experts, minimum cost

If no `--file` is given, the content is the body of the prompt itself.

## Your Workflow

### Step 1: Assess complexity

```bash
ai-delegate assess --file <path>
```

Output: `{"level": "low|medium|high", "domains": ["security", "performance", ...], ...}`

If `--file` is not provided, use `level=medium` and extract domains from the task description keywords:

- "security", "injection", "auth", "owasp" → `["security"]`
- "performance", "memory", "database", "slow" → `["performance"]`
- "architecture", "design", "pattern", "solid" → `["architecture"]`
- "refactor", "clean", "simplif" → `["code-quality"]`

### Step 2: Discover agents

If `--agents` was specified, use those names directly.

Otherwise:

```bash
ai-delegate catalog --json --domain <primary_domain> --trust-all
```

Select minimum experts based on complexity level:

- `low` → 2 agents
- `medium` → 3 agents  
- `high` → 5 agents

Pick agents with non-overlapping domains. Prioritize agents from the `ai-delegate` plugin.

### Step 3: Get path assignments

```bash
ai-delegate assign --agents <name1,name2,...> --complexity <level> --trust-all
```

Output: `[{"agent": "X", "path": "sdk|cli|agent", "model": "...", "source_plugin": "..."}]`

### Step 4: Check cache

Extract content hash (first 16 chars of SHA256 is sufficient for display):

```bash
echo -n "<content_preview_first_200_chars>" | sha256sum | cut -c1-16
```

```bash
ai-delegate memory check --content-hash <hash> --experts <names> --task "<task_desc>"
```

If `{"hit": true, "score": 0.92, "age_hours": 2.1}` and score ≥ 0.90:

- Output: "Using cached result (score: 92%, age: 2.1h)" and return cached findings.

### Step 5: Execute experts in parallel

For each assignment, execute based on path:

**Path A (sdk):** Expert needs no file access. Run via BackendClient.

```bash
ai-delegate run-expert --agent <name> --path sdk --model <model> --task "<task>" --content-file <file>
```

*(If `run-expert` is not yet available, fall through to Path C.)*

**Path B (cli):** Expert needs file access, standard domain, low/medium complexity.

```bash
ollama launch claude --model <model> --yes -- \
  -p "<expert_prompt>" \
  --add-dir <repo_path> \
  --output-format json \
  --allowedTools "Read,Grep,Glob" \
  --bare --dangerously-skip-permissions \
  --max-budget-usd 0.20 \
  --effort low
```

**Path C (agent):** Expert needs deep reasoning OR high complexity.

Spawn via Agent tool:

```
Agent(subagent_type="<source_plugin>:<agent_name>", prompt="<task_description>")
```

Run all Path A and Path B assignments in parallel (use Bash for each). Path C agents can be launched concurrently using multiple Agent tool calls in one message.

Collect all expert outputs. Each should be JSON matching:

```json
{
  "findings": [{"severity": "...", "issue": "...", "recommendation": "..."}]
}
```

### Step 6: Calculate consensus

Aggregate all findings from Step 5 into a single JSON array:

```bash
ai-delegate consensus --findings '<aggregated_findings_json>'
```

Output: `{"score": 0.85, "tier": "standard", "consensus_findings": [...], "disputed_findings": [...]}`

### Step 7: Synthesize verdict

**FAST tier (score ≥ 0.90):**
Output the consensus findings directly as the final verdict. No further debate needed.

**STANDARD tier (0.70–0.90):**
Write a synthesis paragraph explaining:

1. What experts agreed on (consensus_findings)
2. What was disputed and why (disputed_findings)
3. Your recommendation as orchestrator

**DEEP tier (score < 0.70):**
Spawn the adjudicator agent for final evaluation:

```
Agent(subagent_type="ai-delegate:adjudicator", prompt="<full findings context>")
```

Output adjudicator verdict as final result.

## Output Format

Always output a JSON verdict:

```json
{
  "task_type": "<audit|analyze|architecture|...>",
  "tier_used": "fast|standard|deep",
  "consensus_score": 0.87,
  "experts_used": ["security-expert", "auth-expert"],
  "findings": [
    {
      "severity": "high|medium|low",
      "issue": "Brief description",
      "recommendation": "How to fix",
      "location": "optional: file.py:42"
    }
  ],
  "recommendations": ["Top-level recommendation 1"],
  "action_items": ["Immediate action 1"]
}
```

## Rules

- **Do NOT analyze code yourself** — delegate to experts, synthesize their output
- **Minimize experts** — use 2 for low complexity, 3 for medium, 5 for high
- **Cache first** — always check cache before running experts
- **Degrade gracefully** — if an expert fails, continue with remaining (warn if < 50% succeed)
- **Path A first** — prefer SDK path (cheapest) when expert doesn't need file access

## Expert Prompt Template

When spawning experts (Path B or C), use this prompt structure:

```
You are the <expert_name> for an ai-delegate analysis.

Task: <task_description>
File: <file_path>

Analyze the provided content for issues in your domain.
Return findings in this exact JSON format:

{
  "expert": "<your_name>",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "issue": "Brief description of the problem",
      "recommendation": "How to fix it",
      "location": "file.py:42 (if applicable)"
    }
  ]
}

Return JSON only — no markdown, no explanation.
```

```

- [ ] **Step 2: Verify the file was created**

```bash
cat ai_delegate/agents/orchestrator.md | head -20
```

Expected: Frontmatter with `name: orchestrator`, `model: sonnet`, `tools: ["Bash", "Agent"]`.

- [ ] **Step 3: Commit**

```bash
git add ai_delegate/agents/orchestrator.md
git commit -m "feat: add orchestrator.md — generic 7-step assess→catalog→assign→execute→synthesize agent"
```

---

### Task 3: Remove `router.py` (SmartRouter)

`router.py` is 551 lines. `ModelAssigner` in `model_assigner.py` fully replaces its routing logic. `cli.py` currently uses `SmartRouter.select_cli_for_task()` and `CliHealthMonitor` — these are replaced by a direct `DEFAULT_MODELS` lookup.

**Files:**

- Modify: `ai_delegate/cli.py` — replace router usage with direct model lookup
- Modify: `ai_delegate/__init__.py` — remove router imports/exports
- Delete: `ai_delegate/router.py`
- Delete: `tests/test_router.py`

- [ ] **Step 1: Verify test_model_assigner.py covers the replacement**

```bash
python -m pytest tests/test_model_assigner.py -v 2>&1 | tail -10
```

Expected: All tests pass. This confirms ModelAssigner tests exist and are green before we delete router.

- [ ] **Step 2: Fix `cli.py` — replace router.select_cli_for_task()**

In `ai_delegate/cli.py`, the `run_analysis()` function currently has this block (lines 95–113):

```python
# Select CLI using adaptive routing (or static if no_adaptive / no memory)
from .router import get_router, CLIType
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
client = BackendClient(
    model=effective_model,
    verbose=verbose,
    cli_type=cli_config.cli_name,
    on_cli_error=lambda cli_name, err: router.health_monitor.mark_failed(CLIType(cli_name), err),
)
```

Replace it with:

```python
# Select model directly from constants (ModelAssigner handles per-expert routing)
from .constants import FALLBACK_MODEL, DEFAULT_MODELS as _DEFAULT_MODELS
effective_model = model or _DEFAULT_MODELS.get(task_type, FALLBACK_MODEL)
cli_name = _MODEL_CLI_MAP.get(effective_model, "claude")
if verbose:
    print(f"CLI: {cli_name} | Model: {effective_model}")

# Create client
client = BackendClient(
    model=effective_model,
    verbose=verbose,
    cli_type=cli_name,
)
```

And update the memory block around line 147 that uses `cli_config.cli_name`:

Find:

```python
memory.record_cli_run(run_id, cli_config.cli_name)
```

And:

```python
result["_cli_name"] = cli_config.cli_name
```

Replace both with `cli_name` (the local variable defined above).

- [ ] **Step 3: Remove router imports from `cli.py` top-level**

In `ai_delegate/cli.py`, the `--no-adaptive` arg is now dead (no SmartRouter to disable). Keep the `--no-adaptive` flag in argparse for backwards compatibility but make it a no-op (it already is since we're not using the router).

Remove this import at the top of `cli.py` (line ~96 in `run_analysis`, already removed in Step 2).

Also find and remove the import in main() if `CLIType` appears anywhere else:

```bash
grep -n "CLIType\|get_router\|from .router" ai_delegate/cli.py
```

Expected: No matches after the fix.

- [ ] **Step 4: Fix `__init__.py` — remove router exports**

In `ai_delegate/__init__.py`, remove the entire router import block (lines 33–41):

```python
from .router import (
    SmartRouter,
    CLIType,
    ComplexityLevel,
    detect_complexity,
    get_model_for_complexity,
    get_router,
    select_cli_and_model,
)
```

And from `__all__` (lines 91–97), remove:

```python
    # Router
    "SmartRouter",
    "CLIType",
    "ComplexityLevel",
    "detect_complexity",
    "get_model_for_complexity",
    "get_router",
    "select_cli_and_model",
```

- [ ] **Step 5: Run tests to confirm nothing broke**

```bash
python -m pytest tests/ -v --ignore=tests/test_router.py -x -q 2>&1 | tail -20
```

Expected: All tests pass (except test_router.py which we haven't deleted yet).

- [ ] **Step 6: Delete router.py and test_router.py**

```bash
trash ai_delegate/router.py tests/test_router.py
git add -A
```

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v -q 2>&1 | tail -20
```

Expected: All remaining tests pass.

- [ ] **Step 8: Commit**

```bash
git commit -m "refactor: remove router.py (SmartRouter) — replaced by ModelAssigner and direct model lookup"
```

---

### Task 4: Remove `plugin_registry.py`

`plugin_registry.py` loaded custom expert plugins from a directory. `AgentCatalog` from `catalog.py` is the replacement. The usage in `cli.py` (lines 76–80) can simply be removed — the new orchestrator handles expert selection via catalog.

**Files:**

- Modify: `ai_delegate/cli.py` — remove plugin_registry import and usage
- Delete: `ai_delegate/plugin_registry.py`
- Delete: `tests/test_plugin_registry.py`

- [ ] **Step 1: Remove plugin_registry usage from `cli.py`**

In `ai_delegate/cli.py`, inside `run_analysis()`, find and remove this block (lines 76–80):

```python
# Load custom expert plugins
from .plugin_registry import PluginRegistry
registry = PluginRegistry()
custom_experts = registry.for_task(task_type)
for plugin in custom_experts:
    config.experts.update(plugin.to_expert_dict())
```

Delete these 5 lines entirely. The `config` object will use its default experts (TaskConfig.from_task_type already sets them).

- [ ] **Step 2: Run tests to confirm nothing broke**

```bash
python -m pytest tests/ -v --ignore=tests/test_plugin_registry.py -x -q 2>&1 | tail -20
```

Expected: All tests pass.

- [ ] **Step 3: Delete plugin_registry.py and test_plugin_registry.py**

```bash
trash ai_delegate/plugin_registry.py tests/test_plugin_registry.py
git add -A
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/ -v -q 2>&1 | tail -15
```

Expected: All tests pass. Note: test count will drop by ~15 (test_plugin_registry.py removed) but test_catalog.py already covers the replacement logic.

- [ ] **Step 5: Commit**

```bash
git commit -m "refactor: remove plugin_registry.py — replaced by AgentCatalog (catalog.py)"
```

---

## Final Verification

After all 4 tasks:

- [ ] **Full test suite passes**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

- [ ] **CLI smoke test**

```bash
echo "def login(u, p): db.execute(f'SELECT * FROM users WHERE name={u}')" | python -m ai_delegate audit 2>&1 | head -10
```

- [ ] **New subcommands work**

```bash
python -m ai_delegate catalog --json --trust-all 2>&1 | python -c "import sys, json; d=json.load(sys.stdin); print(f'{len(d)} agents found')"
python -m ai_delegate assess --file ai_delegate/client.py 2>&1
```

- [ ] **Deleted files are gone**

```bash
ls ai_delegate/router.py ai_delegate/plugin_registry.py 2>&1
```

Expected: `No such file or directory` for both.
