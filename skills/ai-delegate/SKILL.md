---
name: ai-delegate
description: |
  Multi-agent debate system for comprehensive code analysis. Domain experts (security, performance, architecture, refactor, migrate, testing, database, code-quality) analyze in parallel, debate findings, and adjudicator synthesizes final verdict. Auto-selects best AI CLI (Ollama, Gemini, Codex, Claude). TRIGGER on code review, security audit, performance analysis, architecture review, refactoring, migration, testing analysis.
license: MIT
compatibility: Python 3.10+. Ollama, Gemini, Codex, Claude CLI.
metadata:
  author: KoBig
  version: "0.3.0"
  tests: 628 tests, 97% coverage
---

# AI Delegation Framework

Multi-agent adaptive delegation with smart CLI routing and domain expert debate.

## Quick Start

```bash
# Security audit (auto-selects best CLI)
ai-delegate audit --file src/auth.py

# Performance analysis
ai-delegate analyze --file src/api.py

# Architecture review
ai-delegate architecture --file ./src/

# Refactoring analysis
ai-delegate refactor --file src/legacy.py

# Migration analysis
ai-delegate migrate --file ./src/ --from v1 --to v2

# Testing analysis
ai-delegate test --file tests/

# Code quality review
ai-delegate quality --file src/

# Database analysis
ai-delegate database --file migrations/

# Multi-domain code review
ai-delegate review src/main.py -d security,performance
```

## Domain Experts

| Domain | Experts | Focus |
|--------|---------|-------|
| **Security** | OWASP, Auth, Input | Vulnerabilities, secrets, OWASP Top 10 |
| **Performance** | Complexity, Database, Memory | Bottlenecks, queries, caching |
| **Architecture** | Patterns, SOLID, Scalability | Design, coupling, cohesion |
| **Refactor** | Simplification, Patterns | Code improvements, complexity reduction |
| **Migrate** | API, Dependencies | Migration risks, breaking changes |
| **Testing** | Coverage, Quality, Mocking | Test gaps, quality issues |
| **Code Quality** | Smells, Maintainability | Readability, standards, debt |
| **Database** | Schema, Queries, Migrations | Schema design, query optimization |

## Smart Router

| Available CLIs | Detection | Fallback |
|---------------|-----------|----------|
| Ollama | `which ollama` | Gemini |
| Gemini | `which gemini` | Codex |
| Codex | `which codex` | Claude |
| Claude | `which claude` | Last resort |

| Task | CLI | Model |
|------|-----|-------|
| audit | Ollama | glm-5:cloud |
| analyze | Ollama | glm-5:cloud |
| architecture | Codex | o3-mini |
| review | Ollama | kimi-k2.5:cloud |
| refactor | Ollama | kimi-k2.5:cloud |
| migrate | Codex | o3-mini |

## Architecture

```
SmartRouter → ModelAssigner → Execution Paths
├── Path A: BackendClient (SDK → localhost:11434, no tools)
├── Path B: AgentPool (ollama launch claude, Read/Grep/Glob, kimi-k2.5)
├── Path C: Agent tool (Claude Code Agent, Sonnet, all tools)
└── Path D: Agent Teams (debate-lead + kimi peers, AGREE/CHALLENGE/WITHDRAW)

DebateOrchestrator
├── ExpertRunner (parallel, all paths)
├── ConsensusCalculator (80% agreement threshold)
├── DisputedFindingsBundle → debate-lead agent (Path D)
└── Adjudicator (Sonnet) → final verdict
```

| Path | When | Model |
|------|------|-------|
| A | No file access needed | kimi-k2.5:cloud |
| B | File access, standard domain, low/medium complexity | kimi-k2.5:cloud |
| C | File access + architecture/migration or high complexity | Sonnet |
| D | Peer debate on disputed findings | kimi-k2.5:cloud peers |

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

## CLI Commands

| Command | Domain | Use Case |
|---------|--------|----------|
| `audit` | Security | OWASP Top 10, auth, crypto |
| `analyze` | Performance | Bottlenecks, queries, memory |
| `architecture` | Architecture | Patterns, SOLID, coupling |
| `refactor` | Refactor | Complexity, smells, patterns |
| `migrate` | Migrate | API changes, dependencies |
| `test` | Testing | Coverage, quality, mocking |
| `quality` | Code Quality | Maintainability, standards |
| `database` | Database | Schema, queries, migrations |
| `review` | Multi-domain | Comprehensive review |

## Python API

```python
from ai_delegate import (
    SmartRouter, DebateOrchestrator, TaskConfig,
    # Complexity
    ComplexityAssessor, ComplexityScore,
    # Path B
    AgentExecutorConfig, AgentExecutor, AgentPool,
    # Routing
    ModelAssigner, ExecutionPath, ExpertAssignment,
    # Agent catalog
    AgentCatalog, AgentMetadata,
    # Path D
    DisputedFindingsBundle, DebateResult,
)

# Route agents to execution paths
agents = AgentCatalog().for_domains(["security"])
complexity = ComplexityAssessor().assess_files(["src/auth.py"])
assignments = ModelAssigner.assign_all(agents, complexity)

# Run Path B agents in parallel
config = AgentExecutorConfig(repo_path=Path("."))
pool = AgentPool(AgentExecutor(config))
results = pool.run_parallel(
    [a for a in assignments if a.path == ExecutionPath.CLI],
    task="audit src/auth.py for security issues",
)

# Standard debate orchestration
orchestrator = DebateOrchestrator(model=model, task_config=TaskConfig.from_task_type("audit"))
verdict = orchestrator.analyze(content, tier="auto")
```

## References

- [Setup & CLI Details](references/setup.md)
- [Domain Experts & Model Selection](references/domain-experts.md)
- [Quality Tiers & Fallback](references/quality-tiers.md)
- [Python API](references/python-api.md)
- [Smart Router Details](references/smart-router.md)
- [Architecture Details](references/architecture.md)
- [Model Guide](references/models.md)
- [Token Efficiency](references/token-efficiency.md)
- [Examples & Use Cases](references/examples.md)
