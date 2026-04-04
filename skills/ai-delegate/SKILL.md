---
name: ai-delegate
description: Multi-agent debate system for code analysis. Domain experts analyze in parallel, debate findings, and adjudicator synthesizes final verdict. Automatically selects best available AI CLI (Ollama, Gemini, Codex, Claude). TRIGGER when you need code review, security audit, performance analysis, or architecture review.
license: MIT
compatibility: Requires Python 3.10+. Supports Ollama, Gemini CLI, Codex CLI, and Claude CLI.
metadata:
  author: KoBig
  version: "2.3.0"
  tests: 164 tests, 97% coverage
---

# AI Delegation Framework

Multi-agent adaptive delegation framework with smart CLI routing and domain expert debate system.

## Setup

One-time installation:

```bash
pip install -e "${CLAUDE_PLUGIN_ROOT}" --break-system-packages
```

Verify: `ai-delegate --version`

## Smart Router

**"Push to the right man for the right job"** — Automatically selects the best available CLI and model:

| Available CLIs | Detection | Fallback |
|---------------|-----------|----------|
| Ollama | `which ollama` | Gemini |
| Gemini | `which gemini` | Codex |
| Codex | `which codex` | Claude |
| Claude | `which claude` | Last resort |

**Task-CLI Mapping:**

| Task | Primary CLI | Model |
|------|-------------|-------|
| `audit` | Ollama | glm-5:cloud |
| `analyze` | Ollama | glm-5:cloud |
| `architecture` | Codex | o3-mini |
| `review` | Ollama | kimi-k2.5:cloud |

## Quick Start

```bash
# Auto-selects best available CLI
ai-delegate audit --file src/auth.py
ai-delegate analyze --file src/api.py
ai-delegate architecture --file ./src/

# Override model (uses detected CLI)
ai-delegate audit --model gemini-2.0-flash --file src/auth.py
```

## Architecture

```
SmartRouter (CLI selection)
    ↓
DebateOrchestrator (thin coordinator)
├── ExpertRunner        # Parallel execution (pooled threads)
├── ConsensusCalculator # Consensus calculation
├── DebatePhase         # Debate rounds
└── Adjudicator         # Verdict synthesis + judge
```

**Patterns:** Strategy, Single Responsibility, Composition, Dependency Injection

## Domain Experts

| Domain | Experts | Focus |
|--------|---------|-------|
| security | OWASP, Auth, Input | Vulnerabilities, secrets |
| performance | Complexity, Database, Memory | Bottlenecks, queries |
| architecture | Patterns, SOLID, Scalability | Design, coupling |
| refactor | Simplification, Patterns | Code improvements |
| migrate | API, Dependencies | Migration risks |

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output consensus |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

**Defaults:** `audit/architecture/migrate` → DEEP, others → consensus-based

## Python API

```python
from ai_delegate import SmartRouter, DebateOrchestrator, TaskConfig

# Auto-select CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")

# Create orchestrator with selected model
config = TaskConfig.from_task_type("audit")
orchestrator = DebateOrchestrator(model=model, task_config=config)
verdict = orchestrator.analyze(content, tier="auto")
```

## Supported CLIs

| CLI | Install | Models | Use Case |
|-----|---------|--------|----------|
| Ollama | ollama.ai | glm-5, kimi-k2.5, sonnet | Structured output, cloud |
| Gemini | gemini CLI | gemini-2.0-flash, gemini-2.5-pro | Fast, multimodal |
| Codex | codex CLI | gpt-4o, o3-mini | Code generation, reasoning |
| Claude | claude CLI | sonnet, opus | Fallback, safety |

## Rate Limiting

Max retries: 3 (2s → 4s → 8s). Automatic fallback to next available CLI on rate limit.

## References

- [Smart Router](references/smart-router.md) — CLI and model selection
- [Architecture Details](references/architecture.md) — Structure selection logic
- [CLI Reference](references/cli-reference.md) — Full command reference
- [Model Guide](references/models.md) — Model selection details
- [Token Efficiency](references/token-efficiency.md) — Savings examples
