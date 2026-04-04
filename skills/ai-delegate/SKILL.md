---
name: ai-delegate
description: Multi-agent debate system for code analysis. Domain experts analyze in parallel, debate findings, and adjudicator synthesizes final verdict. TRIGGER when you need code review, security audit, performance analysis, or architecture review.
license: MIT
compatibility: Requires Python 3.10+. Uses cloud models (glm-5, kimi-k2.5, sonnet).
metadata:
  author: KoBig
  version: "2.2.0"
  tests: 164 tests, 97% coverage
---

# AI Delegation Framework

Multi-agent adaptive delegation framework with domain expert debate system.

## Setup

One-time installation:

```bash
pip install -e "${CLAUDE_PLUGIN_ROOT}" --break-system-packages
```

Verify: `ai-delegate --version`

## Quick Start

```bash
ai-delegate audit --file src/auth.py           # Security audit
ai-delegate analyze --tier deep --file src/api.py  # Performance
ai-delegate architecture --file ./src/          # Architecture review
ai-delegate audit --model glm-5:cloud --file src/auth.py
```

## Architecture

```
DebateOrchestrator (thin coordinator)
├── ExpertRunner        # Parallel execution (pooled threads)
├── ConsensusCalculator # Consensus calculation
├── DebatePhase         # Debate rounds
└── Adjudicator         # Verdict synthesis + judge
```

**Patterns:** Single Responsibility, Composition, Dependency Injection, Object Pool

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
from ai_delegate import OllamaClient, DebateOrchestrator, TaskConfig

config = TaskConfig.from_task_type("audit")
client = OllamaClient(model=config.default_model)
orchestrator = DebateOrchestrator(client=client, task_config=config)
verdict = orchestrator.analyze(content, tier="auto")
```

## Models

| Model | Use Case |
|-------|----------|
| `glm-5:cloud` | Security, performance, structured output |
| `kimi-k2.5:cloud` | Reasoning, architecture |
| `sonnet` | Fallback |

## Rate Limiting

Max retries: 3 (2s → 4s → 8s). Fallback to Claude CLI on usage limit.

## References

- [Architecture Details](references/architecture.md) — Structure selection logic
- [CLI Reference](references/cli-reference.md) — Full command reference
- [Model Guide](references/models.md) — Model selection details
- [Token Efficiency](references/token-efficiency.md) — Savings examples
