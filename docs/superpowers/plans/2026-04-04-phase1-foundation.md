# Phase 1: Foundation & Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 critical bugs (hook false-positive, consensus integer division, finding normalization, debate output parsing, zero-findings escalation) and add hook test suite + debate output schema validation.

**Architecture:** All changes are backward-compatible fixes to existing files. No new abstractions. Three layers: (1) `hooks/validate-ai-command.sh` — replace regex with awk executable extraction, (2) `ai_delegate/debate/orchestrator.py` — fix 4 bugs, add ForcedFindingValidator, (3) `tests/test_hooks.py` — new file for hook integration tests.

**Tech Stack:** Python 3.9+, pytest, bash/awk, subprocess, hashlib.md5, math.ceil

---

## Task 1: Fix Hook False-Positive (validate-ai-command.sh)

**Files:**

- Modify: `hooks/validate-ai-command.sh`
- Create: `tests/test_hooks.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_hooks.py
import subprocess
import json
import pytest
from pathlib import Path

HOOK = Path(__file__).parent.parent / "hooks" / "validate-ai-command.sh"

def run_hook(command: str) -> dict:
    """Run hook with a fake Bash tool_input and return parsed output."""
    payload = json.dumps({"tool_input": {"command": command}})
    result = subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
    )
    try:
        return json.loads(result.stdout) if result.stdout.strip() else {}
    except json.JSONDecodeError:
        return {"exit_code": result.returncode, "stdout": result.stdout}


class TestHookAllowsNonAiDelegate:
    def test_mkdir_with_ai_delegate_in_path_is_allowed(self):
        """mkdir of a path containing 'ai-delegate' must not be blocked."""
        result = run_hook("mkdir -p /path/to/ai-delegate-plugin/docs/plans")
        assert result == {}  # empty output = allowed (exit 0, no JSON)

    def test_ls_ai_delegate_dir_is_allowed(self):
        result = run_hook("ls /Users/dev/ai-delegate-plugin/src")
        assert result == {}

    def test_cat_file_in_ai_delegate_dir_is_allowed(self):
        result = run_hook("cat /home/user/ai-delegate-plugin/README.md")
        assert result == {}

    def test_grep_inside_ai_delegate_dir_is_allowed(self):
        result = run_hook("grep -r 'pattern' /path/ai-delegate-plugin/")
        assert result == {}


class TestHookBlocksInvalidAiDelegateTask:
    def test_unknown_task_is_denied(self):
        result = run_hook("ai-delegate unknown-task --file src/main.py")
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"

    def test_ai_delegate_without_task_is_denied(self):
        result = run_hook("ai-delegate --file src/main.py")
        assert result.get("hookSpecificOutput", {}).get("permissionDecision") == "deny"


class TestHookAllowsValidAiDelegateCommands:
    @pytest.mark.parametrize("task", ["audit", "analyze", "architecture", "refactor", "migrate", "review"])
    def test_valid_task_with_file_is_allowed(self, task):
        result = run_hook(f"ai-delegate {task} --file src/main.py")
        assert result == {}

    def test_version_flag_is_allowed(self):
        result = run_hook("ai-delegate --version")
        assert result == {}

    def test_help_flag_is_allowed(self):
        result = run_hook("ai-delegate --help")
        assert result == {}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_hooks.py::TestHookAllowsNonAiDelegate::test_mkdir_with_ai_delegate_in_path_is_allowed -v
```

Expected: FAIL — hook currently denies `mkdir` with `ai-delegate` in path.

- [ ] **Step 3: Fix the hook**

Replace `hooks/validate-ai-command.sh` entirely:

```bash
#!/bin/bash
# validate-ai-command.sh - Validate ai-delegate commands before execution

# Read hook input
INPUT=$(cat)

# Extract command — empty for non-Bash tools (Grep, Read, etc.)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || COMMAND=""
COMMAND="${COMMAND:-}"

# Extract the EXECUTABLE (first token in the command, basename only)
# This correctly handles: /usr/bin/ai-delegate, ./ai-delegate, ai-delegate
EXECUTABLE=$(echo "$COMMAND" | awk '{print $1}' | awk -F'/' '{print $NF}')

# Only intercept ai-delegate commands
if [ "$EXECUTABLE" != "ai-delegate" ]; then
    exit 0
fi

# Valid tasks
VALID_TASKS="audit|analyze|architecture|refactor|migrate|review"

# Allow meta flags (--version, --help, -h, -V)
if echo "$COMMAND" | grep -qE "ai-delegate\s+(--version|--help|-h|-V)"; then
    exit 0
fi

# Check if command has a valid task
if ! echo "$COMMAND" | grep -qE "ai-delegate\s+($VALID_TASKS)(\s|$)"; then
    jq -n --arg cmd "$COMMAND" '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "Invalid ai-delegate task. Valid tasks: audit, analyze, architecture, refactor, migrate, review"
        }
    }'
    exit 0
fi

# Allow valid command
exit 0
```

- [ ] **Step 4: Run all hook tests**

```bash
pytest tests/test_hooks.py -v
```

Expected: All 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add hooks/validate-ai-command.sh tests/test_hooks.py
git commit -m "fix(hooks): use awk executable extraction to prevent false positives on paths containing 'ai-delegate'"
```

---

## Task 2: Fix Integer Division in ConsensusCalculator

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:94`
- Modify: `tests/test_consensus.py` (add boundary tests)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_consensus.py

import math
from ai_delegate.debate.orchestrator import ConsensusCalculator
from ai_delegate.models import Finding, ExpertResult

def make_result(expert: str, issue: str, severity: str = "high") -> ExpertResult:
    return ExpertResult(
        expert_name=expert,
        expert_type="audit",
        findings=[Finding(severity=severity, issue=issue)],
        raw_output="{}",
    )

class TestConsensusThresholdBoundary:
    def test_three_experts_all_agree_is_consensus(self):
        """3/3 experts agreeing should be consensus at 80% threshold."""
        results = [
            make_result("A", "SQL injection"),
            make_result("B", "SQL injection"),
            make_result("C", "SQL injection"),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 1
        assert consensus.consensus_findings[0].issue == "SQL injection"

    def test_two_of_three_experts_is_NOT_consensus(self):
        """2/3 = 66.7% should NOT be consensus at 80% threshold.
        
        Bug: old code does 3 * 80 // 100 = 2, accepting 2/3 as consensus.
        Fix: math.ceil(3 * 80 / 100) = 3, requiring 3/3.
        """
        results = [
            make_result("A", "SQL injection"),
            make_result("B", "SQL injection"),
            make_result("C", "XSS vulnerability"),  # Different finding
        ]
        consensus = ConsensusCalculator.calculate(results)
        # SQL injection appears 2/3 times = 66.7%, below 80% threshold
        assert len(consensus.consensus_findings) == 0
        assert len(consensus.disputed_findings) == 1  # 2 experts agreed, 1 didn't

    def test_five_experts_four_agree_is_consensus(self):
        """4/5 = 80% should be consensus (exactly at threshold)."""
        results = [
            make_result("A", "SQL injection"),
            make_result("B", "SQL injection"),
            make_result("C", "SQL injection"),
            make_result("D", "SQL injection"),
            make_result("E", "XSS"),  # Different
        ]
        consensus = ConsensusCalculator.calculate(results)
        # 4/5 = 80% = exactly at threshold
        assert len(consensus.consensus_findings) == 1

    def test_five_experts_three_agree_is_NOT_consensus(self):
        """3/5 = 60% should NOT be consensus."""
        results = [
            make_result("A", "SQL injection"),
            make_result("B", "SQL injection"),
            make_result("C", "SQL injection"),
            make_result("D", "XSS"),
            make_result("E", "CSRF"),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 0
```

- [ ] **Step 2: Run to verify test fails**

```bash
pytest tests/test_consensus.py::TestConsensusThresholdBoundary::test_two_of_three_experts_is_NOT_consensus -v
```

Expected: FAIL — current code passes 2/3 as consensus (integer division bug).

- [ ] **Step 3: Fix the code**

In `ai_delegate/debate/orchestrator.py`, change line 94:

```python
# OLD (BUGGY):
threshold = len(expert_results) * QualityThresholds.CONSENSUS_PERCENTAGE // 100

# NEW (CORRECT):
import math
threshold = math.ceil(len(expert_results) * QualityThresholds.CONSENSUS_PERCENTAGE / 100)
```

Also add `import math` at top of file (after existing imports).

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_consensus.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_consensus.py
git commit -m "fix(consensus): use math.ceil for threshold to prevent false consensus at boundary (e.g. 2/3 experts)"
```

---

## Task 3: Fix Finding Key Normalization

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py:87`
- Modify: `tests/test_consensus.py` (add normalization tests)

- [ ] **Step 1: Write failing test**

```python
# Add to tests/test_consensus.py

class TestFindingNormalization:
    def test_different_issues_with_same_first_50_chars_are_NOT_merged(self):
        """Two findings with same severity+first50chars but different full text must be separate."""
        long_prefix = "A" * 49  # 49 chars shared prefix
        finding_a = Finding(severity="high", issue=long_prefix + "Z_additional_context_A")
        finding_b = Finding(severity="high", issue=long_prefix + "Z_additional_context_B")
        
        results = [
            ExpertResult("Expert1", "audit", findings=[finding_a], raw_output="{}"),
            ExpertResult("Expert2", "audit", findings=[finding_b], raw_output="{}"),
        ]
        consensus = ConsensusCalculator.calculate(results)
        
        # These are different issues — should NOT be treated as consensus
        # Old code: both get key "high|" + 49*"A" + "Z" (same first 50), merged as consensus
        # New code: different hashes, treated as separate unique findings
        assert len(consensus.consensus_findings) == 0

    def test_identical_issues_ARE_merged(self):
        """Same finding from two experts should still create consensus."""
        results = [
            ExpertResult("Expert1", "audit",
                findings=[Finding(severity="high", issue="SQL injection on line 42")],
                raw_output="{}"),
            ExpertResult("Expert2", "audit",
                findings=[Finding(severity="high", issue="SQL injection on line 42")],
                raw_output="{}"),
            ExpertResult("Expert3", "audit",
                findings=[Finding(severity="high", issue="SQL injection on line 42")],
                raw_output="{}"),
        ]
        consensus = ConsensusCalculator.calculate(results)
        assert len(consensus.consensus_findings) == 1
```

- [ ] **Step 2: Run to verify first test fails**

```bash
pytest tests/test_consensus.py::TestFindingNormalization::test_different_issues_with_same_first_50_chars_are_NOT_merged -v
```

Expected: FAIL — old code uses `issue[:50]` causing collision.

- [ ] **Step 3: Fix the normalization**

In `ai_delegate/debate/orchestrator.py`, change line 87:

```python
# OLD (BUGGY):
key = f"{finding.severity}|{finding.issue[:50]}"  # truncation causes collisions

# NEW (CORRECT):
import hashlib
_raw = f"{finding.severity}|{finding.issue}"
key = hashlib.md5(_raw.encode()).hexdigest()
```

Add `import hashlib` at top of file.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_consensus.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_consensus.py
git commit -m "fix(consensus): use md5 hash for finding key normalization to prevent false collisions on truncated strings"
```

---

## Task 4: Fix Debate Output Parsing (Reuses Old Findings)

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py` (DebatePhase.run, lines 407-413)
- Create: `tests/test_debate_phase.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_debate_phase.py
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import DebatePhase
from ai_delegate.models import ExpertResult, Finding, TaskConfig

def make_task_config() -> TaskConfig:
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "You are OWASP expert."},
        display_name="AUDIT",
        description="Security audit",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
    )

class TestDebatePhaseOutputParsing:
    def test_debate_uses_new_findings_not_old_ones(self):
        """Debate phase must parse findings from the new LLM output, not reuse initial findings."""
        client = MagicMock()
        # New output from debate has a different finding
        client.run_json.return_value = {
            "findings": [
                {"severity": "critical", "issue": "New finding discovered in debate"}
            ]
        }
        
        phase = DebatePhase(client=client, task_config=make_task_config())
        
        initial_results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="Old initial finding")],
                raw_output='{"findings": [{"severity": "high", "issue": "Old initial finding"}]}',
            )
        ]
        
        debate_results = phase.run(initial_results)
        
        assert len(debate_results) == 1
        # Should have NEW finding from debate output, not old one
        assert debate_results[0].findings[0].issue == "New finding discovered in debate"
        assert debate_results[0].findings[0].severity == "critical"

    def test_debate_falls_back_to_old_findings_if_new_output_has_none(self):
        """If debate output has no findings, fall back to original findings."""
        client = MagicMock()
        client.run_json.return_value = {"analysis": "no new issues found"}  # No findings key
        
        phase = DebatePhase(client=client, task_config=make_task_config())
        
        initial_results = [
            ExpertResult(
                expert_name="OWASP",
                expert_type="audit",
                findings=[Finding(severity="high", issue="Original finding")],
                raw_output='{"findings": [{"severity": "high", "issue": "Original finding"}]}',
            )
        ]
        
        debate_results = phase.run(initial_results)
        
        # Falls back to original when new output has no findings
        assert debate_results[0].findings[0].issue == "Original finding"
```

- [ ] **Step 2: Run to verify test fails**

```bash
pytest tests/test_debate_phase.py::TestDebatePhaseOutputParsing::test_debate_uses_new_findings_not_old_ones -v
```

Expected: FAIL — current code uses `findings=result.findings` (old findings).

- [ ] **Step 3: Fix the debate phase**

In `ai_delegate/debate/orchestrator.py`, replace the `run()` method of `DebatePhase` (lines 368-418):

```python
def run(self, expert_results: List[ExpertResult]) -> List[ExpertResult]:
    """Run debate phase between experts."""
    debate_results: List[ExpertResult] = []

    for result in expert_results:
        if result.error:
            continue

        other_findings = build_findings(expert_results, exclude=result.expert_name)

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

Output your revised analysis as JSON with a "findings" array."""

        try:
            output = self.client.run_json(prompt)

            # Parse new findings from debate output (not reusing old ones)
            new_findings = []
            raw_findings = output.get("findings", [])
            if isinstance(raw_findings, list):
                for f in raw_findings:
                    if isinstance(f, dict):
                        new_findings.append(Finding.from_dict(f))

            # Fall back to original findings if debate produced none
            final_findings = new_findings if new_findings else result.findings

            debate_results.append(ExpertResult(
                expert_name=result.expert_name,
                expert_type=result.expert_type,
                findings=final_findings,
                raw_output=json.dumps(output),
            ))
        except Exception as e:
            logger.error(f"Debate failed for {result.expert_name}: {e}")
            debate_results.append(result)

    return debate_results
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_debate_phase.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_debate_phase.py
git commit -m "fix(debate): parse new findings from debate output instead of reusing initial expert findings"
```

---

## Task 5: Add ForcedFindingValidator

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py` (add class + integrate into analyze())
- Create: `tests/test_forced_finding.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_forced_finding.py
from unittest.mock import MagicMock, patch
from ai_delegate.debate.orchestrator import DebateOrchestrator
from ai_delegate.models import ExpertResult, Finding, TaskConfig, Tier

def make_task_config(always_deep: bool = False) -> TaskConfig:
    return TaskConfig(
        task_type="analyze",
        experts={"Complexity": "...", "Database": "...", "Memory": "..."},
        display_name="ANALYZE",
        description="Performance analysis",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
        always_deep=always_deep,
    )


class TestForcedFindingValidator:
    def test_zero_findings_from_all_experts_forces_deep_tier(self):
        """When all experts return 0 findings, tier must be promoted to DEEP."""
        client = MagicMock()
        # Adjudicator returns something
        client.run_json.return_value = {"findings": [], "summary": "No issues"}
        
        config = make_task_config(always_deep=False)
        orchestrator = DebateOrchestrator(client=client, task_config=config)
        
        # Patch expert runner to return experts with ZERO findings
        zero_results = [
            ExpertResult("Complexity", "analyze", findings=[], raw_output='{"findings": []}'),
            ExpertResult("Database", "analyze", findings=[], raw_output='{"findings": []}'),
            ExpertResult("Memory", "analyze", findings=[], raw_output='{"findings": []}'),
        ]
        
        with patch.object(orchestrator.expert_runner, 'run_parallel', return_value=zero_results):
            verdict = orchestrator.analyze("some code", tier=Tier.AUTO.value)
        
        # Zero findings → must use DEEP tier, not FAST
        assert verdict.tier_used == Tier.DEEP.value

    def test_nonzero_findings_allow_normal_tier_selection(self):
        """When experts find issues, normal tier selection applies."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "SQL injection"}]
        }
        
        config = make_task_config(always_deep=False)
        orchestrator = DebateOrchestrator(client=client, task_config=config)
        
        # All 3 experts agree on same finding → should be FAST tier (90%+ consensus)
        findings = [Finding(severity="high", issue="SQL injection")]
        results = [
            ExpertResult("Complexity", "analyze", findings=findings, raw_output='{}'),
            ExpertResult("Database", "analyze", findings=findings, raw_output='{}'),
            ExpertResult("Memory", "analyze", findings=findings, raw_output='{}'),
        ]
        
        with patch.object(orchestrator.expert_runner, 'run_parallel', return_value=results):
            verdict = orchestrator.analyze("some code", tier=Tier.AUTO.value)
        
        # With 3/3 consensus, should use FAST tier
        assert verdict.tier_used == Tier.FAST.value
```

- [ ] **Step 2: Run to verify test fails**

```bash
pytest tests/test_forced_finding.py::TestForcedFindingValidator::test_zero_findings_from_all_experts_forces_deep_tier -v
```

Expected: FAIL — current code uses FAST tier when all findings are empty (score=1.0, percentage=100%).

- [ ] **Step 3: Add ForcedFindingValidator and integrate**

In `ai_delegate/debate/orchestrator.py`, add this class after `ConsensusCalculator`:

```python
class ForcedFindingValidator:
    """Ensure that zero expert findings triggers deeper analysis."""

    @staticmethod
    def should_force_deep(expert_results: List[ExpertResult]) -> bool:
        """
        Return True if all non-errored experts returned zero findings.

        When all experts return nothing, we assume shallow analysis rather than
        a perfectly clean codebase. Force DEEP tier to re-examine.
        """
        successful = [r for r in expert_results if not r.error]
        if not successful:
            return False  # All errored — can't judge
        total_findings = sum(len(r.findings) for r in successful)
        return total_findings == 0
```

Then in `DebateOrchestrator.analyze()`, after the consensus calculation (after line 479), add:

```python
# Force DEEP tier if all experts returned zero findings (prevents rubber-stamp)
if ForcedFindingValidator.should_force_deep(expert_results):
    logger.warning("All experts returned 0 findings — forcing DEEP tier for deeper analysis")
    selected_tier = Tier.DEEP.value
else:
    selected_tier = self._select_tier(tier, consensus)
```

And remove the existing `selected_tier = self._select_tier(tier, consensus)` line that was there before.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_forced_finding.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_forced_finding.py
git commit -m "feat(debate): add ForcedFindingValidator to escalate to DEEP tier when all experts return 0 findings"
```

---

## Task 6: Add Debate Output Schema Validation

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py` (ExpertRunner._run_single_expert)
- Create: `tests/test_expert_output_validation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_expert_output_validation.py
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import ExpertRunner
from ai_delegate.models import TaskConfig

def make_config():
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "You are OWASP expert."},
        display_name="AUDIT",
        description="Security audit",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
    )


class TestExpertOutputValidation:
    def test_null_findings_produces_empty_list(self):
        """When expert returns {"findings": null}, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"findings": None}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "You are OWASP expert.", "some code")

        assert result.findings == []
        assert result.error is None  # not an error, just empty

    def test_missing_findings_key_produces_empty_list(self):
        """When expert returns {} with no findings key, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"analysis": "Code looks clean"}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert result.findings == []

    def test_non_list_findings_produces_empty_list(self):
        """When expert returns {"findings": "some string"}, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"findings": "No issues found"}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert result.findings == []

    def test_finding_missing_issue_field_uses_empty_string(self):
        """Finding dict without 'issue' key defaults to empty string, not crashes."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high"}]  # missing 'issue'
        }

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert len(result.findings) == 1
        assert result.findings[0].issue == ""
        assert result.findings[0].severity == "high"

    def test_valid_findings_are_parsed_correctly(self):
        """Well-formed findings are parsed into Finding objects."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [
                {"severity": "critical", "issue": "SQL injection", "location": "line 42"},
                {"severity": "high", "issue": "XSS", "recommendation": "Sanitize output"},
            ]
        }

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert len(result.findings) == 2
        assert result.findings[0].severity == "critical"
        assert result.findings[0].issue == "SQL injection"
        assert result.findings[0].location == "line 42"
        assert result.findings[1].recommendation == "Sanitize output"
```

- [ ] **Step 2: Run to verify some tests fail**

```bash
pytest tests/test_expert_output_validation.py -v
```

Expected: `test_null_findings_produces_empty_list` and `test_non_list_findings_produces_empty_list` FAIL.

- [ ] **Step 3: Fix ExpertRunner._run_single_expert**

In `ai_delegate/debate/orchestrator.py`, update the findings parsing section in `_run_single_expert` (around lines 206-212):

```python
# Parse findings from JSON — robust to null/missing/wrong-type
findings = []
raw_findings = output.get("findings", [])
if isinstance(raw_findings, list):
    for f in raw_findings:
        if isinstance(f, dict):
            findings.append(Finding.from_dict(f))
# If raw_findings is None, non-list, or missing — findings stays []
```

(This is already partially correct but needs the null guard. The `if isinstance(raw_findings, list)` already handles None since `None` is not a list — verify this passes now.)

- [ ] **Step 4: Run all tests**

```bash
pytest tests/test_expert_output_validation.py tests/test_debate_phase.py tests/test_forced_finding.py tests/test_consensus.py tests/test_hooks.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Run full suite to check for regressions**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/debate/orchestrator.py tests/test_expert_output_validation.py
git commit -m "fix(expert-runner): add robust schema validation for expert output (null/missing/wrong-type findings)"
```

---

## Task 7: Final Integration Check & Tag

- [ ] **Step 1: Run complete test suite**

```bash
pytest tests/ -v --cov=ai_delegate --cov-report=term-missing 2>&1 | tail -30
```

Expected: 330+ tests pass, coverage ≥ 97%.

- [ ] **Step 2: Verify hook fix with real scenario**

```bash
echo '{"tool_input": {"command": "mkdir -p /Users/dev/ai-delegate-plugin/docs/plans"}}' | bash hooks/validate-ai-command.sh
```

Expected: No output (exit 0 = allowed).

```bash
echo '{"tool_input": {"command": "ai-delegate unknown --file src/main.py"}}' | bash hooks/validate-ai-command.sh
```

Expected: JSON output with `permissionDecision: "deny"`.

- [ ] **Step 3: Commit & tag**

```bash
git add -A
git commit -m "chore: Phase 1 complete — all foundation bugs fixed, 330+ tests passing"
git tag v0.1.0-phase1
```
