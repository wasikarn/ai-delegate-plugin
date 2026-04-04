# Generic Orchestration Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Transform ai-delegate from a domain-specific debate framework into a generic intelligence layer for Claude Code orchestration — reducing token usage without reducing output quality.

**Architecture:** Thin Python utilities + smart Claude Code orchestrator agent that discovers experts from any installed plugin, selects the minimum set needed, routes each to the right model and execution path, and synthesizes findings via consensus math.

**Tech Stack:** Python 3.10+, Claude Code agents, Anthropic SDK, Ollama (v0.15.0+), `ollama launch claude`

---

## Mission & Core Principles

### Mission

ai-delegate is the **intelligence layer** for Claude Code multi-agent orchestration:

- **Reduce token usage** by selecting minimum experts, routing to budget models, and exiting early
- **Maintain output quality** by matching the right expert to the right task
- **"Push the right man to the right job"** = right Agent × right Model × right Execution Path

### Core Principles

1. **Minimum experts for maximum coverage** — never spawn agents with overlapping domains
2. **Progressive escalation** — cheap/fast first, escalate only when needed
3. **Early exit** — stop as soon as consensus is achieved (don't wait for all experts)
4. **Cache-first** — check memory before re-analyzing unchanged content
5. **No hardcoded presets** — orchestrator decides dynamically, not config files
6. **No plugin coupling** — works with any plugin's agents (devflow, atlassian-pm, etc.)

---

## Architecture Overview

```
User: /ai-delegate "review this PR diff"
              │
              ▼
   agents/orchestrator.md          ← Claude Code agent (brain, runs once)
         │
         ├─ 1. ai-delegate catalog --json
         │      scan ~/.claude/plugins/*/agents/*.md
         │      returns: [{name, description, source_plugin, tools}]
         │
         ├─ 2. Assess complexity + select experts
         │      "push the right man to the right job"
         │      assign model tier + execution path per expert
         │
         ├─ 3. Execute experts in parallel
         │      ┌─ Claude Code agents (Agent tool)  ← deep reasoning
         │      ├─ ollama launch claude --agent X   ← real tools, budget model
         │      └─ Anthropic SDK → Ollama           ← fast, no tools
         │
         ├─ 4. ai-delegate consensus --findings <json>
         │      returns: {score, tier, consensus_findings, disputed_findings}
         │
         └─ 5. FAST (≥90%) → output directly
               STANDARD/DEEP → synthesis pass → final verdict
```

---

## Intelligence Layer — Orchestrator Agent

### File: `agents/orchestrator.md`

The orchestrator is a Claude Code agent (NOT a Python class). It runs once per task and makes all routing decisions.

### Step 1 — Complexity Assessment

Before selecting experts, assess:

- **Content type**: code / markdown / YAML / SQL / diff / prose
- **Size**: line count, file count
- **Domain signals**: auth code → security, SQL → database, architecture files → patterns
- **Task description**: explicit keywords ("security", "review", "explain")

Output: `complexity = {level: low|medium|high, domains: [...], file_count: N}`

### Step 2 — Expert Selection

Call `ai-delegate catalog --json` to get all available agents. Select experts by:

1. **Domain match**: expert `description` covers the detected domains
2. **No overlap**: don't select two experts with the same domain focus
3. **Count by complexity**:
   - LOW → 2 experts max
   - MEDIUM → 3 experts
   - HIGH → 4-5 experts
4. **User override**: if `--agents` specified, use that list directly (skip selection)

### Step 3 — Model & Path Assignment

Per expert, assign:

| Task type | Execution path | Model |
|-----------|---------------|-------|
| Pattern matching, secret detection | SDK path | GLM-5 / Kimi via Ollama |
| Code exploration (needs file access) | Launch path | Kimi via `ollama launch claude` |
| Deep reasoning, architecture | Claude Code agent | Sonnet |
| Fast multimodal | Gemini CLI | gemini-2.0-flash |

**Decision rule:**

- Does the expert need to READ files itself? → Launch path
- Is it pattern/text analysis on content we provide? → SDK path
- Does it require Claude-level reasoning? → Claude Code agent

### Step 4 — Progressive Escalation

```
Round 1: 2 cheapest experts → consensus ≥90%? → FAST exit
Round 2: add more experts → consensus ≥70%? → STANDARD exit
Round 3: adjudicator synthesis → DEEP verdict
```

**Early exit**: if first 2 experts agree 100% → don't spawn remaining experts.

### Step 5 — Cache Check (before execution)

Call `ai-delegate memory check --content-hash <hash>` — if unchanged from last run, reuse findings (skip expert execution entirely).

---

## Expert Execution Paths

### Path A: Anthropic SDK (fast, no tools)

Use for: pattern matching, text analysis, when content is passed directly.

```python
# client.py BackendClient (keep)
client = anthropic.Anthropic(base_url="http://localhost:11434", api_key="ollama")
response = client.messages.create(
    model="kimi-k2.5:cloud",
    messages=[{"role": "user", "content": expert_prompt + content}],
    tools=[...],  # Ollama supports tool calling (v0.15.0+)
)
```

CLI: `ai-delegate run-expert --agent security-expert --path sdk --model kimi-k2.5:cloud`

### Path B: ollama launch claude (real tools, budget model)

Use for: code exploration, when expert needs to READ files, navigate repo structure.

```bash
ollama launch claude --model kimi-k2.5:cloud --yes -- \
  --agent security-expert \
  --output-format json \
  --allowedTools "Read,Grep,Glob,Bash" \
  -p "Analyze this repository for security vulnerabilities. Return JSON findings."
```

Expert gets: full file system access + Kimi as the model (cheap, not Claude Sonnet).

### Path C: Claude Code Agent (deep reasoning)

Use for: architecture review, complex security, anything requiring multi-step reasoning.

```python
# Orchestrator spawns via Agent tool
Agent(subagent_type="ai-delegate:architecture-expert", prompt="...")
```

Expert gets: full Claude intelligence + all tools.

---

## Agent Catalog

### File: `ai_delegate/catalog.py`

Scans all installed plugins for agent definitions.

```python
class AgentCatalog:
    def scan(self) -> list[AgentMetadata]:
        """Scan ~/.claude/plugins/*/agents/*.md for all available agents."""

    def for_domains(self, domains: list[str]) -> list[AgentMetadata]:
        """Return agents whose description covers given domains."""

@dataclass
class AgentMetadata:
    name: str           # e.g. "security-expert"
    description: str    # from frontmatter
    source_plugin: str  # e.g. "devflow", "ai-delegate"
    model: str          # from frontmatter (default model)
    tools: list[str]    # declared tools
    path: Path          # absolute path to .md file
```

CLI: `ai-delegate catalog [--json] [--domain security]`

Reuses logic from existing `plugin_registry.py` (frontmatter parsing).

---

## Consensus & Verdict

### File: `ai_delegate/consensus.py`

Extracted from current `debate/orchestrator.py` — pure math, no agent logic.

```python
class ConsensusCalculator:
    @staticmethod
    def calculate(results: list[ExpertResult]) -> ConsensusResult:
        """Calculate agreement score between expert findings."""
```

CLI: `ai-delegate consensus --findings '[...]'`

Returns: `{score: 0.85, tier: "standard", consensus_findings: [...], disputed_findings: [...]}`

### Quality Tiers

| Consensus | Tier | Action |
|-----------|------|--------|
| ≥ 90% | FAST | Output immediately, no adjudication |
| 70-90% | STANDARD | Orchestrator synthesis pass |
| < 70% | DEEP | Spawn adjudicator agent |

---

## Findings Contract (JSON Schema v1.0)

All experts MUST return findings in this format:

```json
{
  "schema_version": "1.0",
  "expert": "security-expert",
  "source_plugin": "ai-delegate",
  "findings": [
    {
      "severity": "critical|high|medium|low",
      "issue": "Brief description of the problem",
      "recommendation": "How to fix it",
      "location": "optional: file.py:42"
    }
  ]
}
```

- `schema_version` required for forward compatibility
- `severity` and `issue` required; all other fields optional
- Unknown fields ignored (forward compatible)

---

## Python Utilities — What Changes

### Keep (modified)

| File | Change |
|------|--------|
| `client.py` | Keep BackendClient — used for SDK path execution |
| `models.py` | Simplify — remove TaskConfig preset fields, keep Finding/ExpertResult/ConsensusResult/Verdict |
| `constants.py` | Remove TaskTypes, keep QualityThresholds/TimeoutConfig/RetryConfig |
| `memory.py` | Keep — cache-first + regression detection |
| `party_mode.py` | Keep — reframe as DebateStrategy variant |

### Add (new)

| File | Purpose |
|------|---------|
| `catalog.py` | Agent discovery from all installed plugins |
| `consensus.py` | Extracted ConsensusCalculator (pure math) |
| `agents/orchestrator.md` | The brain — Claude Code orchestrator agent |

### Remove

| File | Reason |
|------|--------|
| `config.py` | All hardcoded task presets removed |
| `debate/orchestrator.py` ExpertRunner, DebatePhase | Python no longer spawns experts directly |
| `supervisor.py` | Dead code (confirmed unused) |
| `router.py` SmartRouter | Orchestrator agent handles routing decisions |
| `plugin_registry.py` | Replaced by catalog.py (logic reused) |

---

## CLI Interface

```bash
# User-facing (via skill or direct)
ai-delegate "review this PR diff"
ai-delegate "audit src/auth.py for security issues"
ai-delegate --agents security-expert,code-reviewer "check this PR"

# Internal utilities (called by orchestrator)
ai-delegate catalog --json
ai-delegate catalog --domain security --json
ai-delegate consensus --findings '[...]'
ai-delegate memory check --content-hash <sha256>
ai-delegate run-expert --agent X --path sdk|launch --model Y --content-file F
```

---

## Skill Interface

### File: `skills/ai-delegate/SKILL.md`

Updated to reflect generic interface:

```
/ai-delegate <task description>
/ai-delegate --agents X,Y,Z <task description>
/ai-delegate --tier deep <task description>
/ai-delegate --budget <task description>   # force SDK path for all experts
```

---

## Implementation Phases

### Phase 1 — Foundation (non-breaking)

- Extract `ConsensusCalculator` → `ai_delegate/consensus.py`
- Add `catalog.py` with agent discovery
- Write `agents/orchestrator.md` skeleton
- Add `ai-delegate catalog` and `ai-delegate consensus` CLI commands
- All existing functionality still works

### Phase 2 — Orchestrator

- Implement full `agents/orchestrator.md` with complexity assessment + expert selection
- Implement `ollama launch claude` execution path (Launch path B)
- Connect orchestrator → catalog → consensus pipeline
- Add memory cache-check integration

### Phase 3 — Cleanup

- Remove `config.py` task presets
- Remove `supervisor.py`, `plugin_registry.py`, `router.py` SmartRouter
- Simplify `models.py`, `constants.py`
- Update skill SKILL.md
- Update all tests

---

## Token Savings (expected)

| Optimization | Savings |
|---|---|
| Minimum experts (2 instead of 5 for simple tasks) | ~60% |
| Budget model routing (GLM/Kimi instead of Sonnet) | ~80% |
| Early exit on consensus | ~30-50% |
| Cache-first (skip re-analysis) | ~100% on repeat |
| SDK path vs Claude agent for pattern matching | ~70% |

**Combined target: 70-95% token reduction vs naive "spawn all Claude agents"**
