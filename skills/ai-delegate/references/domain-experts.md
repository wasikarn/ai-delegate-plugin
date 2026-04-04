# Domain Experts

Multi-agent parallel analysis with debate and adjudication.

## Expert Domains

| Domain | Experts | Focus |
|--------|---------|-------|
| security | OWASP, Auth, Input | Vulnerabilities, secrets |
| performance | Complexity, Database, Memory | Bottlenecks, queries |
| architecture | Patterns, SOLID, Scalability | Design, coupling |
| refactor | Simplification, Patterns | Code improvements |
| migrate | API, Dependencies | Migration risks |

## Model Selection by Complexity

| Complexity | Model | Use Case |
|-----------|-------|----------|
| LOW | haiku | Single vulnerability check, <100 lines |
| MEDIUM | glm-5:cloud | Standard analysis, <500 lines |
| HIGH | sonnet | Complex reasoning, architecture |

## Expert Output Format

Experts return JSON with critical info at top (avoid "lost in middle"):

```json
{
  "summary": "CRITICAL: 3 high-severity findings",
  "severity_breakdown": {"high": 3, "medium": 5, "low": 2},
  "top_findings": [...],
  "domain": "security",
  "score": 75,
  "detailed_findings": [...]
}
```
