# Token Efficiency

## CEO + Employees Architecture

```
Claude Code (CEO)
  │
  └── Debate Layer (Phase 1-4)
        │
        ├── Security Expert
        ├── Performance Expert
        └── Architecture Expert
```

**Key:** Worker tokens use Ollama budget, not Claude budget.

## When to Delegate

**Delegate (saves tokens):** Code Review, Large Files (>500 lines), Documentation, Tests, Security Audit, Performance, Architecture

**Keep on Claude:** Orchestration, Small Files, Q&A, Decisions, Synthesis

## Token Comparison by Structure

| Structure | Claude Tokens | Use Case |
|-----------|--------------|----------|
| FLAT (simple) | ~500 | Single domain, <500 lines |
| FLAT (worker) | ~1,500 | Single domain, >500 lines |
| HIERARCHICAL | ~1,500 | Critical tasks (audit) |
| MATRIX (3 domains) | ~1,000 | Multi-domain (2-3) |
| TEAM-BASED | ~1,000 | Complex (4+ domains) |

## Savings Examples

| Task | Without | With | Savings |
|------|---------|------|---------|
| Multi-domain review | ~210K | ~1.5K | **99%** |
| Large file (2000 lines) | ~150K | ~1.5K | **99%** |
| Documentation | ~80K | ~2.5K | **97%** |

## Adaptive Quality Tiers

```
Consensus ≥ 90% → FAST (skip debate)
Consensus 70-90% → STANDARD (debate + adjudication)
Consensus < 70% → DEEP (judge evaluation)
```

| Task | Default | Reason |
|------|---------|--------|
| `audit` | DEEP | Security critical |
| `architecture` | DEEP | Decisions critical |
| `migrate` | DEEP | Risks critical |
| `analyze` | Auto | Adapts to complexity |
| `refactor` | Auto | Adapts to scope |
| `review` | Auto | Adapts to findings |
