---
name: ai-delegate
description: Multi-agent debate system for code analysis. Domain experts analyze in parallel, debate findings, and adjudicator synthesizes final verdict. Auto-selects best AI CLI (Ollama, Gemini, Codex, Claude). TRIGGER on code review, security audit, performance analysis, architecture review.
license: MIT
compatibility: Python 3.10+. Ollama, Gemini, Codex, Claude CLI.
metadata:
  author: KoBig
  version: "0.0.1"
  tests: 164 tests, 97% coverage
---

# AI Delegation Framework

Multi-agent adaptive delegation with smart CLI routing and domain expert debate.

## Quick Start

```bash
ai-delegate audit --file src/auth.py
ai-delegate analyze --file src/api.py
ai-delegate architecture --file ./src/
```

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

## Architecture

```
SmartRouter → DebateOrchestrator
├── ExpertRunner (parallel)
├── ConsensusCalculator
├── DebatePhase
└── Adjudicator
```

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

## References

- [Setup & CLI Details](references/setup.md)
- [Domain Experts & Model Selection](references/domain-experts.md)
- [Quality Tiers & Fallback](references/quality-tiers.md)
- [Python API](references/python-api.md)
- [Smart Router Details](references/smart-router.md)
- [Architecture Details](references/architecture.md)
- [Model Guide](references/models.md)
- [Token Efficiency](references/token-efficiency.md)
