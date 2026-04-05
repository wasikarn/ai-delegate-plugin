# Path D — Agent Teams Peer Debate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Path D — true peer-to-peer expert debate using Claude Code Agent Teams — so disputed findings are resolved by expert consensus before reaching the Adjudicator.

**Architecture:** Python layer adds `ExpertResult.from_dict()` and two new dataclasses (`DisputedFindingsBundle`, `DebateResult`) as a clean JSON handoff boundary. Claude Code skill layer gets two agent definitions (`debate-lead.md`, `debate-expert.md`) that use Agent Teams mailbox protocol to run 1-round debate on disputed findings. All failure modes fall back to existing Adjudicator behavior.

**Tech Stack:** Python 3.10+ dataclasses, `json`, Claude Code Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"`), kimi-k2.5:cloud (debate experts), Sonnet (debate lead), pytest.

> **⚠️ Agent Teams Article Update (2026-04-05):** Claude Code Agent Teams use a **Shared Task List + Mailbox** for peer-to-peer communication — distinct from parent-child sub-agents. Key mechanics:
>
> - **TeammateIdle hook**: fires when a teammate stops responding — use to enforce the "silent = non-AGREE" timeout policy (see `scenario_teammate_timeout.md`). Without this hook, the lead must busy-poll, which wastes tokens.
> - **TaskCompleted hook**: fires when a teammate marks a task done — use to validate `AGREE|CHALLENGE|WITHDRAW` format before the lead reads the result. Prevents malformed verdicts from silently passing.
> - **Cost**: Agent Teams cost ~4-5× tokens vs single session. Path D MUST only trigger for `always_deep` tasks (audit, architecture, migrate) when `consensus.score < 0.90`.
> - **No nested teams**: debate-lead cannot spawn sub-teams. Single-level team only.
> - **Separate context**: each teammate (kimi-k2.5:cloud) has its own context window — they do NOT share the lead's session history.
>
> **Task 8** below adds the hooks that enforce these policies in the agent files.

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `ai_delegate/models.py` | Modify (line ~110) | Add `ExpertResult.from_dict()` classmethod |
| `ai_delegate/debate_runner.py` | Create | `DisputedFindingsBundle` + `DebateResult` dataclasses |
| `ai_delegate/__init__.py` | Modify | Export new types |
| `ai_delegate/agents/debate-lead.md` | Create | Agent Teams lead — orchestrates 1-round debate |
| `ai_delegate/agents/debate-expert.md` | Create | Teammate template — AGREE/CHALLENGE/WITHDRAW |
| `tests/test_debate_runner.py` | Create | Unit tests for both dataclasses |
| `tests/agents/scenario_all_agree.md` | Create | Scenario fixture: all experts agree |
| `tests/agents/scenario_one_challenged.md` | Create | Scenario fixture: 1 challenge, 2 agree (resolved) |
| `tests/agents/scenario_split_verdict.md` | Create | Scenario fixture: split → unresolved |
| `tests/agents/scenario_teammate_timeout.md` | Create | Scenario fixture: expert silent → unresolved |

---

## Task 1: Add `ExpertResult.from_dict()` to `models.py`

**Files:**

- Modify: `ai_delegate/models.py:101-110`
- Test: `tests/test_models.py` (existing, add 2 tests)

- [ ] **Step 1: Write the failing test**

Open `tests/test_models.py` and add this test class at the bottom:

```python
class TestExpertResultFromDict:
    def test_from_dict_roundtrip(self):
        original = ExpertResult(
            expert_name="owasp",
            expert_type="security",
            findings=[Finding(severity="high", issue="SQL injection", recommendation="use params")],
            raw_output='{"findings": []}',
            error=None,
            duration_ms=150.0,
        )
        restored = ExpertResult.from_dict(original.to_dict())
        assert restored.expert_name == "owasp"
        assert restored.expert_type == "security"
        assert len(restored.findings) == 1
        assert restored.findings[0].severity == "high"
        assert restored.findings[0].issue == "SQL injection"
        assert restored.raw_output == '{"findings": []}'
        assert restored.duration_ms == 150.0

    def test_from_dict_missing_optional_fields(self):
        result = ExpertResult.from_dict({
            "expert_name": "auth",
            "expert_type": "security",
        })
        assert result.expert_name == "auth"
        assert result.findings == []
        assert result.error is None
        assert result.raw_output is None
        assert result.duration_ms is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
python -m pytest tests/test_models.py::TestExpertResultFromDict -v
```

Expected: `FAILED` — `AttributeError: type object 'ExpertResult' has no attribute 'from_dict'`

- [ ] **Step 3: Add `from_dict()` to `ExpertResult` in `models.py`**

In `ai_delegate/models.py`, after the `to_dict()` method of `ExpertResult` (after line 110), add:

```python
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpertResult":
        """Create from dictionary (inverse of to_dict)."""
        return cls(
            expert_name=data.get("expert_name", ""),
            expert_type=data.get("expert_type", ""),
            findings=[Finding.from_dict(f) for f in data.get("findings", [])],
            raw_output=data.get("raw_output"),
            error=data.get("error"),
            duration_ms=data.get("duration_ms"),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_models.py::TestExpertResultFromDict -v
```

Expected: `2 passed`

- [ ] **Step 5: Run full models test suite to verify no regressions**

```bash
python -m pytest tests/test_models.py -v --no-header
```

Expected: all existing tests still pass (was 27 before this task)

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/models.py tests/test_models.py
git commit -m "feat: add ExpertResult.from_dict() for DisputedFindingsBundle deserialization"
```

---

## Task 2: Create `debate_runner.py`

**Files:**

- Create: `ai_delegate/debate_runner.py`
- Create: `tests/test_debate_runner.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_debate_runner.py`:

```python
"""Tests for ai_delegate/debate_runner.py — DisputedFindingsBundle and DebateResult."""
import json
import pytest
from ai_delegate.models import Finding, ExpertResult
from ai_delegate.debate_runner import DisputedFindingsBundle, DebateResult


def _finding(severity="high", issue="SQL injection", recommendation="use params"):
    return Finding(severity=severity, issue=issue, recommendation=recommendation)


def _expert_result(name="owasp", findings=None):
    return ExpertResult(
        expert_name=name,
        expert_type="security",
        findings=findings or [_finding()],
    )


class TestDisputedFindingsBundle:
    def test_roundtrip_with_findings_and_experts(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[_finding()],
            expert_results=[_expert_result("owasp"), _expert_result("auth")],
            task_type="audit",
            file_context="src/auth.py",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())

        assert restored.task_type == "audit"
        assert restored.file_context == "src/auth.py"
        assert len(restored.disputed_findings) == 1
        assert restored.disputed_findings[0].severity == "high"
        assert restored.disputed_findings[0].issue == "SQL injection"
        assert len(restored.expert_results) == 2
        assert restored.expert_results[0].expert_name == "owasp"

    def test_empty_disputed_findings_roundtrip(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[],
            expert_results=[_expert_result()],
            task_type="architecture",
            file_context="src/",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())
        assert restored.disputed_findings == []

    def test_to_json_is_valid_json(self):
        bundle = DisputedFindingsBundle(
            disputed_findings=[_finding(severity="medium", issue="missing rate limit")],
            expert_results=[],
            task_type="migrate",
            file_context="src/api.py",
        )
        parsed = json.loads(bundle.to_json())
        assert parsed["task_type"] == "migrate"
        assert parsed["file_context"] == "src/api.py"
        assert len(parsed["disputed_findings"]) == 1
        assert parsed["disputed_findings"][0]["severity"] == "medium"

    def test_from_json_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            DisputedFindingsBundle.from_json("NOT VALID JSON {{{{")

    def test_multiple_findings_preserved_in_order(self):
        findings = [
            _finding("high", "SQL injection"),
            _finding("medium", "missing rate limit"),
            _finding("low", "verbose logging"),
        ]
        bundle = DisputedFindingsBundle(
            disputed_findings=findings,
            expert_results=[],
            task_type="audit",
            file_context="src/auth.py",
        )
        restored = DisputedFindingsBundle.from_json(bundle.to_json())
        issues = [f.issue for f in restored.disputed_findings]
        assert issues == ["SQL injection", "missing rate limit", "verbose logging"]


class TestDebateResult:
    def test_from_json_resolved_and_unresolved(self):
        raw = json.dumps({
            "resolved_findings": [{"severity": "low", "issue": "minor style issue"}],
            "unresolved_findings": [{"severity": "high", "issue": "SQL injection"}],
            "debate_summary": "experts agreed on style, disagreed on SQL",
        })
        result = DebateResult.from_json(raw)

        assert len(result.resolved_findings) == 1
        assert result.resolved_findings[0].severity == "low"
        assert len(result.unresolved_findings) == 1
        assert result.unresolved_findings[0].issue == "SQL injection"
        assert "SQL" in result.debate_summary

    def test_from_json_empty_fields_use_defaults(self):
        result = DebateResult.from_json(json.dumps({}))
        assert result.resolved_findings == []
        assert result.unresolved_findings == []
        assert result.debate_summary == ""

    def test_from_json_invalid_raises(self):
        with pytest.raises(json.JSONDecodeError):
            DebateResult.from_json("NOT VALID JSON")

    def test_all_resolved_no_unresolved(self):
        raw = json.dumps({
            "resolved_findings": [
                {"severity": "high", "issue": "SQL injection"},
                {"severity": "medium", "issue": "missing rate limit"},
            ],
            "unresolved_findings": [],
            "debate_summary": "full consensus reached",
        })
        result = DebateResult.from_json(raw)
        assert len(result.resolved_findings) == 2
        assert result.unresolved_findings == []

    def test_all_unresolved_no_resolved(self):
        raw = json.dumps({
            "resolved_findings": [],
            "unresolved_findings": [{"severity": "high", "issue": "disputed finding"}],
            "debate_summary": "no consensus reached",
        })
        result = DebateResult.from_json(raw)
        assert result.resolved_findings == []
        assert len(result.unresolved_findings) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_debate_runner.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'ai_delegate.debate_runner'`

- [ ] **Step 3: Create `ai_delegate/debate_runner.py`**

```python
"""
debate_runner.py — Data models for Path D Agent Teams peer debate.

DisputedFindingsBundle: Python → Claude Code skill layer handoff (JSON).
DebateResult: DebateTeamRunner → Adjudicator (resolved vs unresolved findings).

These are pure data containers. All Agent Teams orchestration happens at the
Claude Code skill layer (debate-lead.md), not here.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from .models import Finding, ExpertResult


@dataclass
class DisputedFindingsBundle:
    """Serializable handoff from Python layer to Claude Code skill layer.

    Created when task.always_deep is True and consensus.score < 0.90.
    Passed as JSON string to DebateTeamRunner (debate-lead agent).
    """
    disputed_findings: list[Finding]
    expert_results: list[ExpertResult]
    task_type: str        # "audit", "architecture", or "migrate"
    file_context: str     # file path(s) being analyzed

    def to_json(self) -> str:
        """Serialize to JSON string for handoff to Claude Code skill layer."""
        return json.dumps({
            "disputed_findings": [f.to_dict() for f in self.disputed_findings],
            "expert_results": [r.to_dict() for r in self.expert_results],
            "task_type": self.task_type,
            "file_context": self.file_context,
        })

    @classmethod
    def from_json(cls, raw: str) -> "DisputedFindingsBundle":
        """Deserialize from JSON string. Raises json.JSONDecodeError on invalid input."""
        data = json.loads(raw)
        return cls(
            disputed_findings=[Finding.from_dict(f) for f in data["disputed_findings"]],
            expert_results=[ExpertResult.from_dict(r) for r in data["expert_results"]],
            task_type=data["task_type"],
            file_context=data["file_context"],
        )


@dataclass
class DebateResult:
    """Returned by DebateTeamRunner → consumed by Adjudicator.

    resolved_findings: ≥80% experts agreed — skip Adjudicator entirely.
    unresolved_findings: still disputed — escalate to Adjudicator.
    debate_summary: human-readable transcript for logging.
    """
    resolved_findings: list[Finding] = field(default_factory=list)
    unresolved_findings: list[Finding] = field(default_factory=list)
    debate_summary: str = ""

    @classmethod
    def from_json(cls, raw: str) -> "DebateResult":
        """Deserialize from JSON string. Raises json.JSONDecodeError on invalid input."""
        data = json.loads(raw)
        return cls(
            resolved_findings=[
                Finding.from_dict(f) for f in data.get("resolved_findings", [])
            ],
            unresolved_findings=[
                Finding.from_dict(f) for f in data.get("unresolved_findings", [])
            ],
            debate_summary=data.get("debate_summary", ""),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_debate_runner.py -v
```

Expected: `9 passed`

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/debate_runner.py tests/test_debate_runner.py
git commit -m "feat: add DisputedFindingsBundle and DebateResult for Path D handoff"
```

---

## Task 3: Export new types from `__init__.py`

**Files:**

- Modify: `ai_delegate/__init__.py`

- [ ] **Step 1: Add imports to `__init__.py`**

In `ai_delegate/__init__.py`, after the `from .catalog import ...` line (currently line 23), add:

```python
from .debate_runner import DisputedFindingsBundle, DebateResult
```

Then in the `__all__` list, after `"DOMAIN_KEYWORDS",` add:

```python
    # Debate Runner (Path D)
    "DisputedFindingsBundle",
    "DebateResult",
```

- [ ] **Step 2: Verify import works**

```bash
python -c "from ai_delegate import DisputedFindingsBundle, DebateResult; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add ai_delegate/__init__.py
git commit -m "feat: export DisputedFindingsBundle and DebateResult from ai_delegate"
```

---

## Task 4: Create `debate-lead.md` agent definition

**Files:**

- Create: `ai_delegate/agents/debate-lead.md`

> Note: `ai_delegate/agents/` directory does not exist yet — create it.

- [ ] **Step 1: Create the directory and agent file**

```bash
mkdir -p ai_delegate/agents
```

Create `ai_delegate/agents/debate-lead.md`:

```markdown
---
name: debate-lead
description: |
  Debate lead for ai-delegate peer review round. Receives DisputedFindingsBundle JSON,
  creates expert teammates via Agent Teams, coordinates 1-round debate via shared task
  list and mailbox, returns DebateResult JSON. Triggered for always_deep tasks
  (audit, architecture, migrate) when consensus score < 0.90.
model: sonnet
tools: ["Agent", "TaskCreate", "TaskUpdate", "TaskList", "SendMessage"]
---

You are the debate lead for an ai-delegate peer review round.

## Input

You receive a `DisputedFindingsBundle` JSON with this structure:
```json
{
  "disputed_findings": [{"severity": "...", "issue": "...", "recommendation": "..."}],
  "expert_results": [{"expert_name": "...", "findings": [...]}],
  "task_type": "audit|architecture|migrate",
  "file_context": "src/path/to/file.py"
}
```

## Your Job

1. **Create teammates** — one teammate per expert in `expert_results`, using model kimi-k2.5:cloud
2. **Post shared tasks** — one task per disputed finding. Each task must include:
   - The finding details (severity, issue, recommendation)
   - Each expert's original position on this finding (from expert_results)
3. **Wait for responses** — each teammate will send you a mailbox message with their verdict:
   - `AGREE` — expert confirms this is a genuine issue
   - `CHALLENGE: [1-2 sentence reason]` — expert disputes the finding
   - `WITHDRAW` — expert retracts their own finding (only for findings they raised)
4. **Classify each finding**:
   - ≥80% AGREE responses → `resolved_findings` (Adjudicator not needed)
   - <80% AGREE → `unresolved_findings` (escalate to Adjudicator)
   - No response received (timeout) → `unresolved_findings` (safe over-escalation)
5. **Return DebateResult JSON only** — no markdown, no explanation.

## Output Format

```json
{
  "resolved_findings": [{"severity": "...", "issue": "...", "recommendation": "..."}],
  "unresolved_findings": [{"severity": "...", "issue": "...", "recommendation": "..."}],
  "debate_summary": "Brief description of what was agreed/disputed"
}
```

## Rules

- Do NOT re-analyze the codebase yourself
- Do NOT add new findings not present in disputed_findings
- Output MUST be valid JSON — no markdown fences, no explanation text
- If a teammate is silent after reasonable wait, treat their finding as unresolved
- Use CONSENSUS_PERCENTAGE = 80% (≥80% of experts must AGREE for resolution)

```

- [ ] **Step 2: Verify the file is valid markdown with correct frontmatter**

```bash
python -c "
import re
text = open('ai_delegate/agents/debate-lead.md').read()
assert text.startswith('---'), 'Missing frontmatter'
end = text.find('\n---', 3)
assert end != -1, 'Unclosed frontmatter'
print('Frontmatter OK, length:', end)
"
```

Expected: `Frontmatter OK, length: <some number>`

- [ ] **Step 3: Commit**

```bash
git add ai_delegate/agents/debate-lead.md
git commit -m "feat: add debate-lead.md agent definition (Agent Teams lead, Sonnet)"
```

---

## Task 5: Create `debate-expert.md` agent definition

**Files:**

- Create: `ai_delegate/agents/debate-expert.md`

- [ ] **Step 1: Create `ai_delegate/agents/debate-expert.md`**

```markdown
---
name: debate-expert
description: |
  Expert teammate in ai-delegate peer debate round. Reads disputed findings and
  peer analyses from shared task list, sends AGREE/CHALLENGE/WITHDRAW verdict
  per finding via mailbox to debate lead. Does NOT re-read codebase — works
  entirely from original findings as context.
model: kimi-k2.5:cloud
tools: ["TaskList", "TaskGet", "SendMessage"]
---

You are an expert teammate in a peer debate round.

## Context

The debate lead has posted disputed findings as shared tasks. You have been
assigned a specific expert role (e.g., OWASP, Auth, Input) based on your
original analysis.

## Input (per shared task)

Each task contains:
- The finding details: severity, issue, recommendation
- Original positions from all experts, including your own

## Your Job

For **each** disputed finding task:

1. Read the finding and all expert positions
2. Decide your verdict — one of:
   - `AGREE` — you confirm this is a genuine issue that should be fixed
   - `CHALLENGE: [1-2 sentence reason]` — you dispute the finding with specific reasoning
   - `WITHDRAW` — you retract your own finding (use only if you originally raised it)
3. Send your verdict to the debate lead via `SendMessage`

## Rules

- **Do NOT re-analyze the codebase** — work from the findings and peer context provided
- **Respond to every finding** — no silent abstentions
- **Be concise** — AGREE is fine alone; CHALLENGE needs 1-2 sentences of reasoning
- **One message per finding** — format: `Finding: [issue text] | Verdict: AGREE`
  or `Finding: [issue text] | Verdict: CHALLENGE: [reason]`

## Example Messages

```

Finding: SQL injection in auth.py:45 | Verdict: AGREE
Finding: Missing rate limiting | Verdict: CHALLENGE: rate limiting is outside the scope of auth module; should be handled at API gateway layer
Finding: Verbose logging of passwords | Verdict: WITHDRAW

```
```

- [ ] **Step 2: Verify frontmatter**

```bash
python -c "
text = open('ai_delegate/agents/debate-expert.md').read()
assert text.startswith('---'), 'Missing frontmatter'
end = text.find('\n---', 3)
assert end != -1, 'Unclosed frontmatter'
print('Frontmatter OK')
"
```

Expected: `Frontmatter OK`

- [ ] **Step 3: Commit**

```bash
git add ai_delegate/agents/debate-expert.md
git commit -m "feat: add debate-expert.md agent definition (Agent Teams teammate, kimi)"
```

---

## Task 6: Create scenario test fixtures

**Files:**

- Create: `tests/agents/scenario_all_agree.md`
- Create: `tests/agents/scenario_one_challenged.md`
- Create: `tests/agents/scenario_split_verdict.md`
- Create: `tests/agents/scenario_teammate_timeout.md`

These are Claude Code level fixtures for manually testing the debate-lead protocol. They are not pytest tests.

- [ ] **Step 1: Create `tests/agents/` directory and scenario files**

```bash
mkdir -p tests/agents
```

Create `tests/agents/scenario_all_agree.md`:

```markdown
# Scenario: All Experts Agree

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "high", "issue": "SQL injection in login query", "recommendation": "use parameterized queries"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]},
    {"expert_name": "input", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: SQL injection in login query | Verdict: AGREE`
- auth: `Finding: SQL injection in login query | Verdict: AGREE`
- input: `Finding: SQL injection in login query | Verdict: AGREE`

## Expected DebateResult

```json
{
  "resolved_findings": [{"severity": "high", "issue": "SQL injection in login query", "recommendation": "use parameterized queries"}],
  "unresolved_findings": [],
  "debate_summary": "All 3 experts agreed on SQL injection finding (100% consensus)"
}
```

**Assertion:** `unresolved_findings` must be empty — Adjudicator should NOT be called.

```

Create `tests/agents/scenario_one_challenged.md`:

```markdown
# Scenario: One Challenged, Two Agree (Resolved — 80% threshold met)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "medium", "issue": "Missing input sanitization on username field", "recommendation": "add regex validation"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Missing input sanitization on username field"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Missing input sanitization on username field"}]},
    {"expert_name": "input", "expert_type": "security", "findings": []}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Missing input sanitization on username field | Verdict: AGREE`
- auth: `Finding: Missing input sanitization on username field | Verdict: AGREE`
- input: `Finding: Missing input sanitization on username field | Verdict: CHALLENGE: username field already sanitized by ORM layer before reaching auth module`

## Expected DebateResult

2 AGREE out of 3 = 67% — below 80% threshold → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "medium", "issue": "Missing input sanitization on username field", "recommendation": "add regex validation"}],
  "debate_summary": "2 agreed, 1 challenged (ORM sanitization argument) — escalating to Adjudicator"
}
```

**Assertion:** finding is `unresolved_findings` because 67% < 80%.

```

Create `tests/agents/scenario_split_verdict.md`:

```markdown
# Scenario: Split Verdict (1 AGREE, 1 CHALLENGE, 1 WITHDRAW — Unresolved)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "high", "issue": "Insecure direct object reference in user profile endpoint", "recommendation": "add authorization check"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]},
    {"expert_name": "input", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]}
  ],
  "task_type": "audit",
  "file_context": "src/user_profile.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Insecure direct object reference in user profile endpoint | Verdict: AGREE`
- auth: `Finding: Insecure direct object reference in user profile endpoint | Verdict: CHALLENGE: auth middleware already enforces ownership check at route level`
- input: `Finding: Insecure direct object reference in user profile endpoint | Verdict: WITHDRAW`

## Expected DebateResult

1 AGREE out of 3 = 33% — below 80% → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint", "recommendation": "add authorization check"}],
  "debate_summary": "Split verdict: 1 agree, 1 challenge, 1 withdraw — escalating to Adjudicator"
}
```

**Assertion:** finding is `unresolved_findings`. Adjudicator receives this for final judgment.

```

Create `tests/agents/scenario_teammate_timeout.md`:

```markdown
# Scenario: Teammate Timeout (Silent Expert → Unresolved)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "medium", "issue": "Session token not invalidated on logout", "recommendation": "call session.invalidate() in logout handler"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Session token not invalidated on logout"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Session token not invalidated on logout"}]},
    {"expert_name": "input", "expert_type": "security", "findings": []}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Session token not invalidated on logout | Verdict: AGREE`
- auth: `Finding: Session token not invalidated on logout | Verdict: AGREE`
- input: *(no response — timeout)*

## Expected DebateResult

Lead receives 2 responses. Input expert silent. Safe policy: treat silent expert
as non-vote (not AGREE). 2 AGREE out of 3 = 67% < 80% → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "medium", "issue": "Session token not invalidated on logout", "recommendation": "call session.invalidate() in logout handler"}],
  "debate_summary": "2 agreed, 1 timeout (safe: treated as non-vote) — escalating to Adjudicator"
}
```

**Assertion:** Timeout is treated as non-AGREE. Finding escalates to Adjudicator.
**Design note:** This ensures timeouts never silently resolve findings.

```

- [ ] **Step 2: Verify all 4 scenario files exist**

```bash
ls tests/agents/
```

Expected: `scenario_all_agree.md  scenario_one_challenged.md  scenario_split_verdict.md  scenario_teammate_timeout.md`

- [ ] **Step 3: Commit**

```bash
git add tests/agents/
git commit -m "docs: add debate protocol scenario test fixtures (4 scenarios)"
```

---

## Task 7: Update CHANGELOG

**Files:**

- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add Path D entry to `[Unreleased]` section in `CHANGELOG.md`**

In `CHANGELOG.md`, under `## [Unreleased]` → `### Added`, append after the existing Phase 1A entries:

```markdown
#### Phase 1C Foundation — Path D Agent Teams Peer Debate

- **debate_runner.py** — Data models for Path D Agent Teams peer debate handoff
  - `DisputedFindingsBundle` — serializable Python → Claude Code skill layer handoff
    - `to_json()` / `from_json()` — full roundtrip serialization
    - Carries: disputed_findings, expert_results, task_type, file_context
  - `DebateResult` — DebateTeamRunner → Adjudicator result container
    - `from_json()` — deserializes lead agent output
    - resolved_findings: ≥80% AGREE — skip Adjudicator
    - unresolved_findings: <80% AGREE — escalate to Adjudicator
- **ExpertResult.from_dict()** — inverse of `to_dict()`, required for bundle deserialization
- **ai_delegate/agents/debate-lead.md** — Agent Teams lead (Sonnet)
  - Creates expert teammates (kimi-k2.5:cloud), coordinates 1-round debate
  - AGREE/CHALLENGE/WITHDRAW protocol via mailbox
  - 80% consensus threshold for resolution
- **ai_delegate/agents/debate-expert.md** — Agent teammate template (kimi-k2.5:cloud)
  - Responds to disputed findings from shared task list
  - Does NOT re-analyze codebase — works from findings context only
- **tests/agents/** — 4 scenario fixtures for manual debate protocol validation
  - scenario_all_agree, scenario_one_challenged, scenario_split_verdict, scenario_teammate_timeout
```

- [ ] **Step 2: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: update CHANGELOG with Phase 1C Path D peer debate components"
```

---

## Task 8: Add Agent Teams Hooks — Timeout Enforcement + Verdict Validation

**Files:**

- Modify: `ai_delegate/agents/debate-lead.md` — add `TeammateIdle` + `TaskCompleted` hook guidance
- Modify: `ai_delegate/agents/debate-expert.md` — add format enforcement note
- Modify: `tests/agents/scenario_teammate_timeout.md` — update design note to reference TeammateIdle

**Context:** Claude Code fires `TeammateIdle` when a teammate stops responding and `TaskCompleted` when a teammate marks a task done. These are the correct enforcement points — not busy-polling in the lead prompt.

- [ ] **Step 1: Add TeammateIdle policy to `debate-lead.md`**

In `ai_delegate/agents/debate-lead.md`, add this section after the existing "Timeout Handling" (or "Failure Modes") section:

```markdown
## Agent Teams Hook Policy

### TeammateIdle (timeout enforcement)
When a teammate goes idle without responding to their finding task:
- Do NOT wait or retry — treat as non-vote (same as WITHDRAW)
- Mark the finding as unresolved if remaining AGREE count drops below 80%
- Proceed with adjudication for unresolved findings

This ensures: silent experts never silently inflate consensus score.

### TaskCompleted (verdict validation)
Before accepting a teammate's completed task, validate format:
- Must contain one of: `AGREE`, `CHALLENGE`, `WITHDRAW`
- Must include `Finding:` label with the finding text
- If malformed: reject and treat as WITHDRAW (finding → unresolved)

Valid format examples:
  Finding: <exact issue text> | Verdict: AGREE
  Finding: <exact issue text> | Verdict: CHALLENGE: <reason>
  Finding: <exact issue text> | Verdict: WITHDRAW
```

- [ ] **Step 2: Add format enforcement note to `debate-expert.md`**

In `ai_delegate/agents/debate-expert.md`, update the output section to add:

```markdown
## CRITICAL: Output Format

Non-conforming responses will be rejected by the lead's TaskCompleted hook
and treated as WITHDRAW (finding → unresolved). Your response MUST use exactly:

  Finding: <exact issue text copied from task> | Verdict: AGREE
  Finding: <exact issue text> | Verdict: CHALLENGE: <one-sentence reason>
  Finding: <exact issue text> | Verdict: WITHDRAW
```

- [ ] **Step 3: Update `scenario_teammate_timeout.md` to reference TeammateIdle hook**

In `tests/agents/scenario_teammate_timeout.md`, replace the last `**Design note:**` line with:

```markdown
**Design note:** `TeammateIdle` hook fires when input expert stops responding.
Hook policy: idle = non-vote. 2 AGREE out of 3 = 67% < 80% → unresolved.
This prevents silent experts from inflating consensus scores.
```

- [ ] **Step 4: Commit**

```bash
git add ai_delegate/agents/debate-lead.md ai_delegate/agents/debate-expert.md tests/agents/scenario_teammate_timeout.md
git commit -m "docs: add Agent Teams hook policies to debate agent files (TeammateIdle + TaskCompleted)"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
python -m pytest tests/test_models.py tests/test_debate_runner.py tests/test_catalog.py -v --no-header
```

Expected: all tests pass (was 628 before this plan; Task 8 adds no new Python tests)

- [ ] **Verify exports work end-to-end**

```bash
python -c "
from ai_delegate import DisputedFindingsBundle, DebateResult
from ai_delegate.models import Finding, ExpertResult

f = Finding(severity='high', issue='SQL injection', recommendation='use params')
e = ExpertResult(expert_name='owasp', expert_type='security', findings=[f])
bundle = DisputedFindingsBundle(
    disputed_findings=[f],
    expert_results=[e],
    task_type='audit',
    file_context='src/auth.py',
)
restored = DisputedFindingsBundle.from_json(bundle.to_json())
assert restored.task_type == 'audit'
assert len(restored.disputed_findings) == 1
print('Path D dataclasses: OK')
"
```

Expected: `Path D dataclasses: OK`
