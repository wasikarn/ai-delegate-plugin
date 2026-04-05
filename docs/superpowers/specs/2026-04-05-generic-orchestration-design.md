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
         │      ┌─ Path A: Anthropic SDK → Ollama   ← fast, no tools, pattern analysis
         │      └─ Path C: Claude Code Agent tool   ← deep reasoning + file access
         │
         ├─ 4. ai-delegate consensus --findings <json>
         │      returns: {score, tier, consensus_findings, disputed_findings}
         │
         └─ 5. FAST (≥90%) → output directly
               STANDARD/DEEP → synthesis pass → final verdict
```

---

## Security Requirements

These requirements apply to `catalog.py` implementation (Phase 1). All four must be implemented; omitting any is a critical vulnerability.

### S1 — Agent Name Validation (Command Injection Prevention)

Any agent name passed to a subprocess or used in a shell command MUST be validated:

```python
import re

AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')

def validate_agent_name(name: str) -> str:
    """Validate agent name is safe for subprocess use. Raises ValueError if invalid."""
    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid agent name {name!r}: must match [a-zA-Z0-9_-]+"
        )
    return name
```

Called in `catalog.py` during scan:

```python
for md_file in plugin_agents_dir.glob("*.md"):
    name = parse_frontmatter(md_file).get("name", "")
    try:
        validate_agent_name(name)
    except ValueError:
        logger.warning("Skipping agent with unsafe name: %s in %s", name, md_file)
        continue
```

**Also:** Never use `shell=True` when passing agent names to subprocess. Always use list args:

```python
# BAD
subprocess.run(f"some-cmd --agent {agent_name}", shell=True)
# GOOD
subprocess.run(["some-cmd", "--agent", agent_name], shell=False)
```

### S2 — Plugin Trust Boundary

Catalog scan MUST enforce a plugin allowlist. Agents from unknown plugins are skipped.

Default allowlist file: `~/.claude/ai-delegate-trust.json`

```json
{
  "trusted_plugins": ["ai-delegate", "devflow", "atlassian-pm"]
}
```

```python
class AgentCatalog:
    def __init__(self, trust_file: Path | None = None, trust_all: bool = False):
        self._trust_all = trust_all
        self._trusted = self._load_trust(trust_file)

    def _load_trust(self, trust_file: Path | None) -> set[str]:
        default = Path.home() / ".claude" / "ai-delegate-trust.json"
        path = trust_file or default
        if path.exists():
            data = json.loads(path.read_text())
            return set(data.get("trusted_plugins", []))
        # If no trust file exists, trust only ai-delegate (self)
        return {"ai-delegate"}

    def _is_trusted(self, source_plugin: str) -> bool:
        return self._trust_all or source_plugin in self._trusted
```

CLI: `ai-delegate catalog --trust-all` to opt-in to all plugins.

### S3 — Path Traversal Prevention

All agent file paths MUST be resolved to canonical form before use:

```python
def _safe_agent_path(self, candidate: Path, plugin_dir: Path) -> Path | None:
    """Return canonical path only if it is under plugin_dir. Returns None otherwise."""
    resolved = candidate.resolve()
    plugin_dir_resolved = plugin_dir.resolve()
    if resolved.is_relative_to(plugin_dir_resolved):
        return resolved
    logger.warning("Path traversal rejected: %s → %s", candidate, resolved)
    return None
```

Use `follow_symlinks=False` in glob to skip symlinks:

```python
for md_file in agents_dir.glob("*.md"):
    safe = self._safe_agent_path(md_file, plugin_dir)
    if safe is None:
        continue
    # proceed with safe path
```

### S4 — Catalog DoS Protection

```python
MAX_AGENTS_PER_PLUGIN = 100
SCAN_TIMEOUT_SECONDS = 5
MAX_FRONTMATTER_SIZE_BYTES = 4096  # ignore suspiciously large files
```

Catalog scan enforces all three limits:

```python
import signal

def _scan_with_timeout(self) -> list[AgentMetadata]:
    def handler(signum, frame):
        raise TimeoutError("Catalog scan exceeded 5 seconds")
    signal.signal(signal.SIGALRM, handler)
    signal.alarm(SCAN_TIMEOUT_SECONDS)
    try:
        return self._scan_all()
    finally:
        signal.alarm(0)
```

---

## Intelligence Layer

The orchestrator has two layers:

1. **Python services** (testable, deterministic) — handle all decision logic
2. **`agents/orchestrator.md`** (Claude Code agent) — coordinates services, synthesizes results

The orchestrator agent calls Python CLI commands and the Agent tool. It does NOT implement decision logic itself — that lives in Python.

### Python Services (New Files)

#### `ai_delegate/complexity.py` — ComplexityAssessor

Assesses content complexity using deterministic rules (no AI reasoning).

```python
@dataclass
class ComplexityScore:
    level: str           # "low" | "medium" | "high"
    domains: list[str]   # detected domain keywords
    file_count: int
    line_count: int
    security_signals: int  # count of security-relevant terms

class ComplexityAssessor:
    # Domain keyword detection (same as AgentCatalog)
    SECURITY_TERMS = {"password", "token", "secret", "crypto", "hash", "jwt", "oauth",
                      "auth", "session", "cookie", "cert", "ssl", "tls"}
    PERF_TERMS     = {"query", "n+1", "cache", "index", "latency", "timeout", "async"}
    ARCH_TERMS     = {"interface", "abstract", "factory", "singleton", "dependency",
                      "coupling", "cohesion", "pattern", "service", "repository"}

    @staticmethod
    def assess(content: str, filename: str = "") -> ComplexityScore:
        lines = content.splitlines()
        line_count = len(lines)
        content_lower = content.lower()

        # Level by line count (from ComplexityThresholds in constants.py)
        if line_count < ComplexityThresholds.LOW_LINES:       # 100
            level = "low"
        elif line_count < ComplexityThresholds.MEDIUM_LINES:  # 500
            level = "medium"
        else:
            level = "high"

        # Domain detection
        domains = []
        sec_count = sum(content_lower.count(t) for t in ComplexityAssessor.SECURITY_TERMS)
        if sec_count > 0:
            domains.append("security")
            if sec_count > 5:
                level = max(level, "medium", key=lambda l: ["low","medium","high"].index(l))
        if any(t in content_lower for t in ComplexityAssessor.PERF_TERMS):
            domains.append("performance")
        if any(t in content_lower for t in ComplexityAssessor.ARCH_TERMS):
            domains.append("architecture")

        return ComplexityScore(
            level=level,
            domains=domains,
            file_count=1,
            line_count=line_count,
            security_signals=sec_count,
        )

    @staticmethod
    def assess_files(paths: list[Path]) -> ComplexityScore:
        """Aggregate complexity across multiple files."""
        scores = [ComplexityAssessor.assess(p.read_text(), p.name) for p in paths]
        all_domains = list({d for s in scores for d in s.domains})
        levels = ["low", "medium", "high"]
        max_level = max((s.level for s in scores), key=lambda l: levels.index(l))
        return ComplexityScore(
            level=max_level,
            domains=all_domains,
            file_count=len(paths),
            line_count=sum(s.line_count for s in scores),
            security_signals=sum(s.security_signals for s in scores),
        )
```

CLI: `ai-delegate assess --file src/auth.py` → `{"level": "medium", "domains": ["security"]}`

#### `ai_delegate/selector.py` — ExpertSelector

Selects minimum expert set for given complexity + domains.

```python
MAX_EXPERTS_BY_LEVEL = {"low": 2, "medium": 3, "high": 5}

class ExpertSelector:
    def __init__(self, catalog: AgentCatalog):
        self._catalog = catalog

    def select(
        self,
        complexity: ComplexityScore,
        user_agents: list[str] | None = None,
    ) -> list[AgentMetadata]:
        """Select minimum experts for maximum coverage.

        If user_agents is given, use those directly (skip selection).
        Otherwise, select by domain match + no overlap + count cap.
        """
        if user_agents is not None:
            all_agents = {a.name: a for a in self._catalog.scan()}
            return [all_agents[n] for n in user_agents if n in all_agents]

        candidates = self._catalog.for_domains(complexity.domains)
        if not candidates:
            candidates = self._catalog.scan()  # fallback: all agents

        # Deduplicate by domain: one expert per domain group
        seen_domains: set[str] = set()
        selected: list[AgentMetadata] = []
        for agent in candidates:
            new_domains = set(agent.domains) - seen_domains
            if new_domains:
                selected.append(agent)
                seen_domains.update(new_domains)

        # Cap by complexity level
        max_count = MAX_EXPERTS_BY_LEVEL[complexity.level]
        return selected[:max_count]
```

#### `ai_delegate/path_selector.py` — ModelAssigner

Assigns execution path (A or C) and model per expert. Replaces `SmartRouter` routing logic.

```python
class ExecutionPath(str, Enum):
    SDK    = "sdk"    # Path A: fast, no file access
    AGENT  = "agent"  # Path C: deep reasoning + tools

@dataclass
class ExpertAssignment:
    agent: AgentMetadata
    path: ExecutionPath
    model: str

FILE_ACCESS_TOOLS = {"Read", "Glob", "Grep", "Bash"}
DEEP_DOMAINS = {"architecture", "migration"}

class ModelAssigner:
    @staticmethod
    def assign(
        agent: AgentMetadata,
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> ExpertAssignment:
        """Assign execution path + model for one expert.

        Decision rules (in order):
        1. If agent.tools intersects FILE_ACCESS_TOOLS → Path C (needs file system)
        2. If agent.domains intersects DEEP_DOMAINS → Path C (deep reasoning)
        3. If complexity.level == "high" → Path C (escalate for complex content)
        4. Otherwise → Path A (SDK, fast pattern analysis)
        """
        overrides = model_overrides or {}

        needs_file_access = bool(set(agent.tools) & FILE_ACCESS_TOOLS)
        needs_deep_reasoning = bool(set(agent.domains) & DEEP_DOMAINS)
        is_complex = complexity.level == "high"

        if needs_file_access or needs_deep_reasoning or is_complex:
            path = ExecutionPath.AGENT
            default_model = agent.model or Models.SONNET
        else:
            path = ExecutionPath.SDK
            default_model = agent.model or Models.KIMI_K25_CLOUD

        model = overrides.get(agent.name, default_model)
        return ExpertAssignment(agent=agent, path=path, model=model)

    @staticmethod
    def assign_all(
        agents: list[AgentMetadata],
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> list[ExpertAssignment]:
        return [ModelAssigner.assign(a, complexity, model_overrides) for a in agents]
```

CLI: `ai-delegate assign --agents security-expert,arch-expert --complexity medium --json`

#### Progressive Escalation State Machine

```python
ESCALATION_ROUNDS = [
    {"count": 2, "budget_tokens": 4000},   # Round 1: cheapest 2
    {"count": 2, "budget_tokens": 8000},   # Round 2: +2 more
    {"count": 999, "budget_tokens": 16000}, # Round 3: all remaining
]
CONSENSUS_FAST_THRESHOLD = QualityThresholds.FAST_THRESHOLD / 100  # 0.90

def run_progressive(
    assignments: list[ExpertAssignment],
    executor: Callable,
    consensus_calc: ConsensusCalculator,
) -> tuple[ConsensusResult, list[ExpertResult]]:
    """Run experts progressively. Exit early on FAST consensus."""
    results: list[ExpertResult] = []
    remaining = list(assignments)

    for round_cfg in ESCALATION_ROUNDS:
        batch = remaining[:round_cfg["count"]]
        remaining = remaining[round_cfg["count"]:]

        for assignment in batch:
            result = executor(assignment)
            results.append(result)

        consensus = consensus_calc.calculate(results)
        if consensus.score >= CONSENSUS_FAST_THRESHOLD:
            return consensus, results  # Early exit

        if not remaining:
            break

    return consensus_calc.calculate(results), results
```

### `agents/orchestrator.md` — Claude Code Agent

The orchestrator agent coordinates Python services. It does **not** implement decision logic.

**Step 1:** Call `ai-delegate assess` → get `complexity`
**Step 2:** Call `ai-delegate catalog --json` → get agent list
**Step 3:** Call `ai-delegate assign --json` → get assignments (path + model per expert)
**Step 4:** Check cache: `ai-delegate memory check --content-hash <hash>`
**Step 5:** Execute experts via `run_progressive`:

- Path A assignments → `ai-delegate run-expert --path sdk --agent X --model Y`
- Path C assignments → `Agent(subagent_type="<plugin>:<name>", prompt="...")`

**Step 6:** Call `ai-delegate consensus --findings <json>` → get tier
**Step 7:** FAST → output directly; STANDARD/DEEP → synthesis pass

---

## Expert Execution Paths

Two active paths. Path B (`ollama launch claude`) is NOT YET IMPLEMENTED — requires verification that the CLI supports `--agent` and `--output-format json` flags before adding.

### Path A: Anthropic SDK (fast, no tools) — ACTIVE

Use for: pattern matching, text analysis, when content is passed directly (no file access needed).

```python
# client.py BackendClient (keep)
client = anthropic.Anthropic(base_url="http://localhost:11434", api_key="ollama")
response = client.messages.create(
    model="kimi-k2.5:cloud",
    messages=[{"role": "user", "content": expert_prompt + content}],
    max_tokens=4096,
)
```

CLI: `ai-delegate run-expert --agent security-expert --path sdk --model kimi-k2.5:cloud`

**Decision rule:** Does the expert need to READ files itself? → Use Path C instead.

### Path B: ollama launch claude (real tools, budget model) — NOT YET IMPLEMENTED

> **BLOCKED:** `ollama launch claude --agent X --output-format json` flags are unverified.
> Verify these flags exist before implementing. Do not add this path until confirmed.

Intended use: code exploration when expert needs real file access but cheaper than Claude Sonnet.

### Path C: Claude Code Agent (deep reasoning) — ACTIVE

Use for: architecture review, complex security, anything requiring multi-step reasoning or file access.

```python
# Orchestrator spawns via Agent tool
Agent(subagent_type="ai-delegate:architecture-expert", prompt="...")
```

Expert gets: full Claude intelligence + all tools (Read, Grep, Glob, Bash).

**Decision rule:** Requires Claude-level reasoning OR needs to read files → Path C.

---

## Agent Catalog

### File: `ai_delegate/catalog.py`

Scans all installed plugins for agent definitions. Enforces security requirements S1-S4 (see Security Requirements).

#### Agent Frontmatter Schema

Agents at `~/.claude/plugins/*/agents/*.md` use this frontmatter (matches existing agents in `agents/`):

```yaml
---
name: security-expert           # Required. Matches [a-zA-Z0-9_-]+
description: |                  # Required. Used for domain matching.
  Security domain expert for multi-agent debate. Analyzes OWASP Top 10...
model: sonnet                   # Optional. Default model for Path C.
color: red                      # Optional. Display hint.
tools: ["Read", "Grep", "Glob", "Bash"]  # Optional. Used for path selection.
---
```

**Required fields:** `name`, `description`
**Optional fields:** `model`, `color`, `tools` — missing fields use defaults

#### Domain Matching Algorithm

Domain matching is keyword-based (case-insensitive substring match on `description`):

```python
DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "security":      ["security", "owasp", "vulnerabilit", "injection", "auth", "crypto"],
    "performance":   ["performance", "complexity", "database", "memory", "bottleneck", "query"],
    "architecture":  ["architecture", "design", "pattern", "solid", "coupling", "cohesion"],
    "code-quality":  ["quality", "maintainab", "readab", "code smell", "refactor", "clean"],
    "testing":       ["test", "coverage", "mock", "assertion", "spec"],
    "migration":     ["migration", "migrate", "breaking change", "api contract", "deprecat"],
    "database":      ["database", "sql", "migration", "schema", "index", "query"],
}

def _detect_domains(description: str) -> list[str]:
    """Return list of domain keys whose keywords appear in description (lowercase)."""
    desc_lower = description.lower()
    return [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(kw in desc_lower for kw in keywords)
    ]
```

An agent with `description = "OWASP Top 10 security analysis"` maps to domains `["security"]`.
An agent with `description = "Code quality and architecture patterns"` maps to `["architecture", "code-quality"]`.

#### Error Handling Rules

| Condition | Action |
|-----------|--------|
| YAML frontmatter malformed | Log warning, skip file |
| `name` field missing | Log warning, skip file |
| `name` fails S1 validation | Log warning, skip file |
| `description` field missing | Use `""` — agent is discoverable but matches no domains |
| `tools` field missing | Default to `[]` — ModelAssigner routes to Path A |
| Plugin not in trust list | Skip silently (no warning to avoid info leak) |
| Plugin dir has > 100 agents | Log warning, load first 100, skip rest |
| Scan exceeds 5 seconds | Raise `TimeoutError`, propagate to caller |

#### Source Plugin Name Extraction

Plugin name is derived from the directory path: `~/.claude/plugins/<PLUGIN_NAME>/agents/<agent>.md`

```python
def _extract_plugin_name(agent_path: Path) -> str:
    """Extract plugin name from path structure ~/.claude/plugins/<name>/agents/*.md"""
    # Expected: .../<plugin_name>/agents/<agent_file>.md
    # agent_path.parents[0] = agents/
    # agent_path.parents[1] = <plugin_name>/
    try:
        return agent_path.parents[1].name
    except IndexError:
        return "unknown"
```

#### AgentMetadata Dataclass

```python
@dataclass
class AgentMetadata:
    name: str            # e.g. "security-expert" — validated [a-zA-Z0-9_-]+
    description: str     # raw description from frontmatter
    source_plugin: str   # e.g. "ai-delegate", "devflow"
    model: str           # default model from frontmatter; "" if not specified
    tools: list[str]     # e.g. ["Read", "Grep", "Glob", "Bash"]
    path: Path           # resolved canonical path (from _safe_agent_path)
    domains: list[str]   # detected via _detect_domains(description)
```

#### AgentCatalog Class

```python
class AgentCatalog:
    def __init__(
        self,
        plugins_dir: Path | None = None,
        trust_file: Path | None = None,
        trust_all: bool = False,
    ):
        self._plugins_dir = plugins_dir or Path.home() / ".claude" / "plugins"
        self._trust_all = trust_all
        self._trusted = self._load_trust(trust_file)
        self._cache: list[AgentMetadata] | None = None  # In-memory per-session

    def scan(self) -> list[AgentMetadata]:
        """Scan all trusted plugins for agents. Returns cached result if already scanned."""
        if self._cache is not None:
            return self._cache
        self._cache = self._scan_with_timeout()
        return self._cache

    def for_domains(self, domains: list[str]) -> list[AgentMetadata]:
        """Return agents whose detected domains overlap with the given domains list."""
        all_agents = self.scan()
        domains_set = set(domains)
        return [a for a in all_agents if domains_set & set(a.domains)]

    def invalidate(self) -> None:
        """Clear in-memory cache (call if plugins installed during session)."""
        self._cache = None
```

CLI: `ai-delegate catalog [--json] [--domain security] [--trust-all]`

---

## Consensus & Verdict

### File: `ai_delegate/consensus.py`

Extracted from `debate/orchestrator.py:ConsensusCalculator`. Pure aggregation — reads ExpertResult list, returns ConsensusResult. No mutations on inputs.

```python
class ConsensusCalculator:
    @staticmethod
    def calculate(results: list[ExpertResult]) -> ConsensusResult:
        """Calculate agreement score between expert findings.

        Contract:
        - Input: list[ExpertResult] — not modified
        - Output: ConsensusResult — new object, findings are references (not copies)
        - Thread-safe: reads only

        Deduplication key: (finding.severity.lower(), finding.issue.lower())
        Agreement: finding_count / len(results)
        """
```

### Consensus Role (Pre vs Post-Debate)

| Phase | Consensus Used For | Action |
|-------|-------------------|--------|
| Pre-debate (after experts run) | **Tier selection only** | Determines FAST / STANDARD / DEEP |
| Post-debate (after adjudicator) | **Not used** | Adjudicator output is the final verdict |

**FAST tier** exits before debate — returns pre-debate consensus findings directly.
**STANDARD/DEEP** tiers use adjudicator output (consensus is stale after debate changes findings).

**Sparse topology note:** If `sparse_topology_k` is set (defer to Phase 2), experts see only k peers during debate. Pre-debate consensus is still the correct input to tier selection. Adjudicator output is always the final verdict regardless.

### Quality Tiers

| Consensus Score | Tier | Action |
|----------------|------|--------|
| ≥ 90% | FAST | Return pre-debate consensus findings immediately |
| 70–90% | STANDARD | Orchestrator synthesis pass on adjudicator output |
| < 70% | DEEP | Spawn adjudicator agent for deep evaluation |

CLI: `ai-delegate consensus --findings '[...]'`

Returns: `{"score": 0.85, "tier": "standard", "consensus_findings": [...], "disputed_findings": [...]}`

---

## FindingsCache

### File: `ai_delegate/cache.py`

Cache key captures content + task + expert selection + models (invalidated if any changes).

```python
@dataclass
class CacheKey:
    content_hash: str          # SHA256(content bytes)
    task_description: str      # Normalized task description
    expert_names_hash: str     # SHA256(":".join(sorted(expert_names)))
    model_versions: str        # SHA256(json.dumps(sorted model assignments))

    def to_str(self) -> str:
        combined = f"{self.content_hash}:{self.task_description}:{self.expert_names_hash}:{self.model_versions}"
        return hashlib.sha256(combined.encode()).hexdigest()

@dataclass
class CacheEntry:
    consensus: ConsensusResult
    expert_results: list[ExpertResult]
    cached_at: float  # time.time()

class FindingsCache:
    CACHE_DIR = Path.home() / ".cache" / "ai-delegate" / "findings"
    MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 days

    def get(self, key: CacheKey) -> CacheEntry | None:
        path = self.CACHE_DIR / key.to_str() / "findings.json"
        if not path.exists():
            return None
        entry = json.loads(path.read_text())
        age = time.time() - entry["cached_at"]
        if age > self.MAX_AGE_SECONDS:
            path.unlink()
            return None
        return CacheEntry(
            consensus=ConsensusResult(**entry["consensus"]),
            expert_results=[ExpertResult(**r) for r in entry["results"]],
            cached_at=entry["cached_at"],
        )

    def set(self, key: CacheKey, entry: CacheEntry) -> None:
        path = self.CACHE_DIR / key.to_str() / "findings.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "consensus": entry.consensus.__dict__,
            "results": [r.to_dict() for r in entry.expert_results],
            "cached_at": entry.cached_at,
        }))
```

CLI: `ai-delegate memory check --content-hash <sha256> --experts X,Y,Z --task "audit"`

Returns: `{"hit": true, "score": 0.92, "age_hours": 2.1}` or `{"hit": false}`

---

## Error Handling Strategy

Orchestrator uses **degraded execution** by default: analysis continues with successful experts, warns if too many fail.

```python
@dataclass
class PartialResult:
    consensus: ConsensusResult
    expert_results: list[ExpertResult]       # Successful only
    failed_experts: dict[str, str]           # {name: error_message}
    success_rate: float                      # len(succeeded) / len(attempted)
    warning: str | None                      # Set if success_rate < 0.5
```

Rules:

- If **0 experts succeed** → raise `RuntimeError("All experts failed: ...")`
- If **< 50% succeed** → return result with `warning = "Only N/M experts succeeded"`
- If **≥ 50% succeed** → return result normally, no warning
- Per-expert timeout: 120 seconds (SDK path: 60s from `TimeoutConfig.SDK_CLOUD`)

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
