# Domain Experts

Multi-agent parallel analysis with debate and adjudication.

## Expert Domains

| Domain | Experts | Focus | Agent File |
|--------|---------|-------|------------|
| **security** | OWASP, Auth, Input | Vulnerabilities, secrets, OWASP Top 10 | security-expert.md |
| **performance** | Complexity, Database, Memory | Bottlenecks, queries, caching | performance-expert.md |
| **architecture** | Patterns, SOLID, Scalability | Design, coupling, cohesion | architecture-expert.md |
| **refactor** | Simplification, Patterns | Code improvements, complexity reduction | refactor-expert.md |
| **migrate** | API, Dependencies | Migration risks, breaking changes | migrate-expert.md |
| **testing** | Coverage, Quality, Mocking | Test gaps, quality issues | testing-expert.md |
| **code-quality** | Smells, Maintainability | Readability, standards, debt | code-quality-expert.md |
| **database** | Schema, Queries, Migrations | Schema design, query optimization | database-expert.md |

## Security Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|-------------|
| OWASP | Injection, XSS, CSRF, security misconfig | CVE references, severity ratings |
| Auth | JWT, OAuth, session management, password hashing | Auth vulnerabilities, crypto issues |
| Input | Input sanitization, hardcoded secrets, API key exposure | Validation gaps, secret exposures |

## Performance Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Complexity | Big O analysis, nested loops, recursion | Complexity classification |
| Database | N+1 queries, missing indexes, query optimization | Query performance issues |
| Memory | Memory leaks, large allocations, caching opportunities | Memory issues, cache patterns |

## Architecture Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Patterns | GoF patterns, anti-patterns | Pattern opportunities, violations |
| SOLID | All 5 SOLID principles | Principle violations |
| Scalability | Coupling, cohesion, distributed systems | Scalability bottlenecks |

## Refactor Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Simplification | Complexity reduction, readability | Simplification opportunities |
| Patterns | Extract Method, Strategy, Factory | Refactoring opportunities |

## Migrate Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| API | API versioning, breaking changes | Breaking change detection |
| Dependencies | Package migrations, version conflicts | Dependency risks |

## Testing Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Coverage | Line, branch, function coverage | Coverage gaps |
| Quality | Assertions, isolation, naming | Test quality issues |
| Mocking | Mock fidelity, contract testing | Mock issues |

## Code Quality Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Smells | Long methods, large classes, duplication | Code smell detection |
| Maintainability | Cognitive complexity, debt interest | Maintainability metrics |

## Database Domain Experts

| Expert | Focus | Key Checks |
|--------|-------|------------|
| Schema | Normalization, indexes, constraints | Schema issues |
| Queries | Execution plans, N+1, index usage | Query optimization |
| Migrations | Safe migrations, rollback strategies | Migration safety |

## Model Selection by Complexity

| Complexity | Model | Use Case |
|-----------|-------|----------|
| LOW | haiku | Single vulnerability check, <100 lines |
| MEDIUM | glm-5:cloud | Standard analysis, <500 lines |
| HIGH | sonnet | Complex reasoning, architecture |

## Budget Mode Models

| Complexity | Default Model | Budget Model |
|------------|---------------|--------------|
| LOW | haiku | glm-5:cloud |
| MEDIUM | glm-5:cloud | glm-5:cloud |
| HIGH | sonnet | kimi-k2.5:cloud |

## Expert Output Format

Experts return JSON with critical info at top (avoid "lost in middle"):

```json
{
  "summary": "CRITICAL: 3 high-severity findings",
  "severity_breakdown": {"high": 3, "medium": 5, "low": 2},
  "top_findings": [
    {
      "severity": "high",
      "title": "SQL Injection in login",
      "file": "auth.py",
      "line": 42,
      "recommendation": "Use parameterized queries"
    }
  ],
  "domain": "security",
  "score": 75,
  "detailed_findings": [...]
}
```

## Cross-Domain Considerations

| Domain | Security Impact | Performance Impact | Architecture Impact |
|--------|----------------|-------------------|---------------------|
| **Security** | Primary | Security checks add overhead | Security in architecture |
| **Performance** | Perf optimizations bypass security | Primary | Performance affects scalability |
| **Architecture** | Architecture impacts security | Architecture affects performance | Primary |
| **Refactor** | Refactoring can introduce vulnerabilities | Refactoring improves performance | Refactoring aligns with architecture |
| **Testing** | Tests verify security | Performance tests prevent regression | Tests reflect architecture |
| **Code Quality** | Quality issues hide vulnerabilities | Quality issues cause perf problems | Quality issues reflect architecture |
| **Database** | SQL injection, data exposure | Query performance critical | Database schema reflects domain |
