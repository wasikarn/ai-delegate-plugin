# Path D — Agent Teams Peer Debate Design

**Goal:** Add Path D execution — true peer-to-peer expert debate using Claude Code Agent Teams — so disputed findings are resolved by expert consensus before reaching the Adjudicator.

**Architecture:** Python layer (Path B) produces `DisputedFindingsBundle`. Claude Code skill layer runs `DebateTeamRunner` (debate-lead Agent) which creates an Agent Team of expert teammates (kimi-k2.5:cloud) that message each other via mailbox. Resolved findings skip Adjudicator. Unresolved findings escalate. All failures gracefully fall back to Adjudicator.

**Tech Stack:** Claude Code Agent Teams (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"`), Agent mailbox + shared task list, Python dataclasses for handoff, Sonnet for debate lead + Adjudicator, kimi-k2.5:cloud for expert teammates.

---

## Context: Four Execution Paths

| Path | Mechanism | Model | Tools | Use When |
|------|-----------|-------|-------|----------|
| A | Anthropic SDK → localhost:11434 | kimi/glm | None | Text-only analysis, no file access |
| B | `ollama launch claude` subprocess | kimi-k2.5:cloud | Read, Grep, Glob | Budget parallel analysis |
| C | Claude Code `Agent` tool | Sonnet | All | Architecture/migration, high complexity |
| **D (NEW)** | Claude Code Agent Teams | Lead: Sonnet · Experts: kimi | TaskList, SendMessage | DEEP tier dispute resolution |

**Trigger:** Path D activates when `task.always_deep = True` AND `consensus.score < 0.90`. Tasks: audit, architecture, migrate.

---

## Two-Layer Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Code Skill Layer                                     │
│  SKILL.md → DebateTeamRunner (Agent Teams) → Adjudicator   │
│                    ↑ DisputedFindingsBundle                  │
│                    ↓ DebateResult                            │
├─────────────────────────────────────────────────────────────┤
│  Python Package (ai_delegate)                               │
│  AgentPool (Path B) → ConsensusCalculator → bundle          │
└─────────────────────────────────────────────────────────────┘
```

**Key insight:** Agent Teams is a Claude Code native feature — it cannot be spawned from Python subprocess. The Python layer produces findings; the Claude Code skill layer orchestrates the debate.

---

## Complete Flow (always_deep tasks)

```
1. Input    user: ai-delegate audit --file src/auth.py

2. Path B   Python: N experts run parallel → findings
            ConsensusCalculator → score + disputed_findings

3. Path D   if always_deep AND score < 0.90:
              DisputedFindingsBundle → DebateTeamRunner
              Agent Teams: Lead creates team → experts debate (1 round)
              → DebateResult(resolved_findings, unresolved_findings)

4. Adjudicate  Adjudicator(Sonnet) synthesizes unresolved_findings only

5. Output   Final Verdict
```

---

## Data Models

```python
# ai_delegate/debate_runner.py

@dataclass
class DisputedFindingsBundle:
    """Serializable handoff from Python → Claude Code skill layer."""
    disputed_findings: list[Finding]    # from ConsensusCalculator
    expert_results: list[ExpertResult]  # original analyses (peer context)
    task_type: str                      # "audit", "architecture", "migrate"
    file_context: str                   # file path(s) being analyzed

    def to_json(self) -> str:
        return json.dumps({
            "disputed_findings": [f.to_dict() for f in self.disputed_findings],
            "expert_results": [r.to_dict() for r in self.expert_results],
            "task_type": self.task_type,
            "file_context": self.file_context,
        })

    @classmethod
    def from_json(cls, raw: str) -> "DisputedFindingsBundle":
        data = json.loads(raw)
        return cls(
            disputed_findings=[Finding.from_dict(f) for f in data["disputed_findings"]],
            # NOTE: ExpertResult.from_dict() must be added to models.py (currently only has to_dict())
            expert_results=[ExpertResult.from_dict(r) for r in data["expert_results"]],
            task_type=data["task_type"],
            file_context=data["file_context"],
        )


@dataclass
class DebateResult:
    """Returned by DebateTeamRunner → consumed by Adjudicator."""
    resolved_findings: list[Finding]    # ≥80% experts agreed — skip Adjudicator
    unresolved_findings: list[Finding]  # still disputed — escalate to Adjudicator
    debate_summary: str                 # human-readable transcript for logging
```

---

## Agent Definitions

### `ai_delegate/agents/debate-lead.md`

```markdown
---
name: debate-lead
description: |
  Debate lead for ai-delegate peer review round. Receives DisputedFindingsBundle,
  creates expert teammates, coordinates 1-round debate via shared task list and
  mailbox, returns DebateResult JSON.
model: sonnet
tools: ["Agent", "TaskCreate", "TaskUpdate", "TaskList", "SendMessage"]
---

You are the debate lead for an ai-delegate peer review round.

## Input
You receive a DisputedFindingsBundle JSON with disputed findings and original
expert analyses.

## Your Job
1. Create a teammate for each expert in expert_results (kimi-k2.5:cloud model)
2. Create one shared task per disputed finding — include the finding details and
   all experts' original positions
3. Wait for all teammates to post their verdict via SendMessage to you:
   - AGREE — expert agrees this is a real issue
   - CHALLENGE: [reason] — expert disputes the finding with reasoning
   - WITHDRAW — expert retracts their own finding
4. Classify each finding:
   - ≥80% AGREE → resolved_findings (no Adjudicator needed)
   - <80% AGREE → unresolved_findings (escalate to Adjudicator)
5. Return DebateResult as JSON only — no markdown, no explanation.

## Output Format
{"resolved_findings": [...], "unresolved_findings": [...], "debate_summary": "..."}
```

### `ai_delegate/agents/debate-expert.md`

```markdown
---
name: debate-expert
description: |
  Expert teammate in ai-delegate peer debate round. Reads disputed findings and
  peer analyses, sends AGREE/CHALLENGE/WITHDRAW per finding via mailbox.
  Does NOT re-read codebase — works from original findings as context.
model: kimi-k2.5:cloud
tools: ["TaskList", "TaskGet", "SendMessage"]
---

You are an expert teammate in a peer debate round.

## Input
The debate lead has posted disputed findings as shared tasks. Each task contains:
- The finding details (severity, issue, recommendation)
- Original positions from all experts including your own

## Your Job
For each disputed finding task:
1. Read the finding and all expert positions
2. Decide your verdict:
   - AGREE — you confirm this is a genuine issue
   - CHALLENGE: [1-2 sentence reason] — you dispute the finding
   - WITHDRAW — you retract your own finding (if you originally raised it)
3. Send your verdict to the debate lead via SendMessage

Do NOT re-analyze the codebase. Work from the findings and peer context provided.
Respond for every finding. Be concise.
```

---

## Debate Protocol (1 Round)

```
Lead creates team:
  teammate-owasp  (kimi-k2.5:cloud)
  teammate-auth   (kimi-k2.5:cloud)
  teammate-input  (kimi-k2.5:cloud)

Lead posts shared tasks:
  Task 1: "SQL injection in auth.py:45 [high]"
    - OWASP original: "confirmed, use parameterized queries"
    - Auth original:  "confirmed, affects login flow"
    - Input original: "uncertain, may be false positive"
  Task 2: "Missing rate limiting [medium]"
    ...

Experts respond via mailbox (concurrent):
  teammate-owasp  → AGREE (Task 1), CHALLENGE: rate limiting is out of scope (Task 2)
  teammate-auth   → AGREE (Task 1), AGREE (Task 2)
  teammate-input  → WITHDRAW (Task 1), AGREE (Task 2)

Lead classifies:
  Task 1: 2 AGREE, 1 WITHDRAW → 67% → unresolved (escalate)
  Task 2: 2 AGREE, 1 CHALLENGE → 67% → unresolved (escalate)
  → DebateResult(resolved=[], unresolved=[Task1, Task2])
```

---

## SKILL.md Integration (Pseudocode)

```python
# In SKILL.md orchestration logic

if task.always_deep and consensus.score < 0.90:
    bundle = DisputedFindingsBundle(
        disputed_findings=consensus.disputed_findings,
        expert_results=expert_results,
        task_type=task.task_type,
        file_context=file_path,
    )
    try:
        # Path D: invoke Agent Teams debate lead
        debate = run_agent("debate-lead", input=bundle.to_json())
        debate_result = DebateResult.from_json(debate.output)
        verdict = Adjudicator.synthesize(debate_result.unresolved_findings)
    except DebateUnavailable:
        # Graceful fallback: skip debate, send all disputed to Adjudicator
        verdict = Adjudicator.synthesize(bundle.disputed_findings)
else:
    verdict = Adjudicator.synthesize(consensus.disputed_findings)
```

---

## Error Handling

| Scenario | Behaviour | Fallback |
|----------|-----------|----------|
| Agent Teams unavailable (flag off / old version) | `TeamCreate` try/except at startup | skip Path D → disputed → Adjudicator |
| Expert teammate crash or timeout | Lead marks finding unresolved after timeout | Adjudicator receives unresolved |
| 0 disputed findings (consensus ≥ 90%) | `bundle.disputed_findings == []` → skip debate | output consensus findings directly |
| `DebateResult` parse failure (malformed JSON) | warning logged, all disputed → unresolved | Adjudicator receives all disputed (safe over-escalation) |
| Lead session crash (no session resumption) | outer 300s timeout catches | skip Path D → Adjudicator receives disputed |

**Design principle:** Path D failure must never crash overall analysis. Every error path falls back to existing Adjudicator behavior.

---

## Testing Strategy

### `tests/test_debate_runner.py`

Unit tests for Python dataclasses — no Agent Teams needed:

```python
def test_empty_disputed_skips_debate():
    bundle = DisputedFindingsBundle(disputed_findings=[], ...)
    assert bundle.disputed_findings == []
    # caller skips Path D — no DebateResult needed

def test_bundle_serialization_roundtrip():
    bundle = DisputedFindingsBundle(
        disputed_findings=[Finding(severity="high", issue="SQL injection")],
        expert_results=[ExpertResult(expert_name="owasp", ...)],
        task_type="audit",
        file_context="src/auth.py",
    )
    assert DisputedFindingsBundle.from_json(bundle.to_json()) == bundle

def test_parse_failure_fallback():
    """When DebateResult JSON is malformed, all disputed treated as unresolved."""
    with pytest.raises(json.JSONDecodeError):
        DebateResult.from_json("NOT VALID JSON")
    # caller catches and escalates all to Adjudicator

def test_debate_result_resolved_unresolved_merge():
    result = DebateResult(
        resolved_findings=[Finding(severity="low", issue="minor")],
        unresolved_findings=[Finding(severity="high", issue="SQL injection")],
        debate_summary="...",
    )
    assert len(result.resolved_findings) == 1
    assert len(result.unresolved_findings) == 1
```

### `tests/agents/` — Scenario Files (Claude Code level)

Agent tests invoke `debate-lead.md` directly with fixture bundles:

| File | Scenario | Expected |
|------|----------|----------|
| `scenario_all_agree.md` | 3 experts AGREE on all findings | `unresolved == []` |
| `scenario_one_challenged.md` | 1 CHALLENGE, 2 AGREE (80%) | finding resolved |
| `scenario_split_verdict.md` | 1 AGREE, 1 CHALLENGE, 1 WITHDRAW (33%) | finding unresolved |
| `scenario_teammate_timeout.md` | 1 expert silent | finding unresolved (safe) |

---

## File Structure

```
ai_delegate/
  agents/
    debate-lead.md        # Agent Teams lead (NEW)
    debate-expert.md      # Teammate template (NEW)
  debate_runner.py        # DisputedFindingsBundle, DebateResult (NEW)
  debate/
    orchestrator.py       # unchanged — Path D added at SKILL.md level

tests/
  test_debate_runner.py   # NEW
  agents/
    scenario_all_agree.md         # NEW
    scenario_one_challenged.md    # NEW
    scenario_split_verdict.md     # NEW
    scenario_teammate_timeout.md  # NEW
```

---

## Cost Estimate

| Phase | Model | Est. Cost (N=3 experts) |
|-------|-------|------------------------|
| Path B analysis | kimi-k2.5:cloud × 3 | ~$0.18 |
| Path D debate (1 round) | kimi × 3 + Sonnet lead overhead | ~$0.05–0.10 |
| Adjudicator (unresolved only) | Sonnet | ~$0.05–0.15 |
| **Total DEEP tier** | | **~$0.28–0.43** |

Debate experts do NOT re-read codebase — they respond from original findings context. This keeps Path D cost low despite using Agent Teams.

---

## What Does NOT Change

- `BackendClient` — unchanged
- `ConsensusCalculator` — unchanged (produces disputed_findings)
- `AgentCatalog` — unchanged
- `AgentExecutor` / `AgentPool` — unchanged
- `Adjudicator` in debate/orchestrator.py — unchanged (receives smaller input now)
- Existing Path A / B / C routing — unchanged
