# Architecture Reference

## Structure Selection

| Profile | Structure | Use Case |
|---------|-----------|----------|
| Simple (1 domain, <500 tokens) | FLAT | CEO handles directly |
| Standard (1 domain, >500) | FLAT | Single worker |
| Multi-domain (2-3) | MATRIX | Parallel teams |
| Complex (4+ domains) | TEAM-BASED | Full debate |
| Critical tasks | HIERARCHICAL | QA layer |

## Selection Logic

```python
if critical: HIERARCHICAL
elif domains >= 4: TEAM_BASED
elif domains >= 2: MATRIX
else: FLAT
```

## Component Architecture

```
DebateOrchestrator (thin coordinator)
├── ExpertRunner        # Parallel expert execution
│   └── ThreadPoolExecutor (shared pool)
├── ConsensusCalculator # Static consensus calculation
├── DebatePhase         # Expert debate rounds
└── Adjudicator         # Verdict synthesis + judge evaluation
```

## Design Patterns Used

| Pattern | Application |
|---------|-------------|
| Single Responsibility | Each class handles one concern |
| Composition | Components injected into orchestrator |
| Dependency Injection | Client and config via constructor |
| Object Pool | ThreadPoolExecutor shared across instances |
| Caching | ExpertResult.parsed_output property |

## Debate Flow

1. **Phase 1:** Experts analyze in parallel
2. **Phase 2:** Experts present & debate
3. **Phase 3:** Experts rebut & refine (Team-Based)
4. **Phase 4:** Adjudicator synthesizes verdict
