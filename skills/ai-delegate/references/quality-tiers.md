# Quality Tiers

Consensus-based processing levels.

## Tier Selection

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output consensus immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

## Default Tiers by Task

| Task | Default Tier | Reason |
|------|--------------|--------|
| audit | DEEP | Security requires thoroughness |
| architecture | DEEP | Design decisions critical |
| migrate | DEEP | Migration risks high impact |
| review | Consensus-based | Balanced approach |
| analyze | Consensus-based | Performance varies |
| refactor | Consensus-based | Improvements incremental |

## Fallback Chain

```
Primary: Ollama (glm-5:cloud, kimi-k2.5:cloud)
    ↓ not available
Gemini CLI (gemini-2.0-flash)
    ↓ not available
Codex CLI (o3-mini)
    ↓ not available
Claude CLI (sonnet/opus)
```
