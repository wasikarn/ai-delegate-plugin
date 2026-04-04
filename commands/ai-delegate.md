---
name: ai-delegate
description: Multi-agent code analysis with domain experts. Use for security audits, performance analysis, architecture reviews, and code reviews. Analyzes code through multiple expert perspectives and synthesizes findings.
argument-hint: <task> [--file <path>] [--model <model>] [--budget] [--domains <domains>]
allowed-tools: ["Read", "Grep", "Glob", "Bash"]
---

# AI Delegate Command

Multi-agent code analysis with domain expert debate system.

## Tasks

| Task | Description | Domains |
|------|-------------|---------|
| `audit` | Security audit | OWASP, Auth, Input |
| `analyze` | Performance analysis | Complexity, Database, Memory |
| `architecture` | Design review | Patterns, SOLID, Scalability |
| `review` | Code review | All domains |
| `refactor` | Refactoring analysis | Simplification, Patterns |
| `migrate` | Migration risks | API, Dependencies |

## Options

```
--file <path>      File or directory to analyze
--model <model>    Override model selection
--budget           Use budget mode (DeepSeek)
--domains <list>   Comma-separated domains for review
--tier <tier>      Quality tier: fast, standard, deep
```

## Examples

```bash
# Security audit
ai-delegate audit --file src/auth.py

# Performance analysis with specific model
ai-delegate analyze --file src/api.py --model gemini-2.0-flash

# Architecture review
ai-delegate architecture --file ./src/

# Multi-domain code review
ai-delegate review src/main.py --domains security,performance

# Budget mode for cost savings
ai-delegate audit --file src/auth.py --budget
```

## How It Works

1. **Smart Router** detects available CLIs and selects the best one
2. **Expert Runner** spawns domain experts in parallel
3. **Debate Phase** experts discuss findings
4. **Adjudicator** synthesizes final verdict

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

## Python API

```python
from ai_delegate import SmartRouter, DebateOrchestrator, TaskConfig

# Auto-select CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")

# Run analysis
config = TaskConfig.from_task_type("audit")
orchestrator = DebateOrchestrator(model=model, task_config=config)
verdict = orchestrator.analyze(content, tier="auto")
```

## References

See `skills/ai-delegate/references/` for detailed documentation on:

- Setup and CLI options
- Domain experts and model selection
- Quality tiers and fallback chains
- Python API usage
