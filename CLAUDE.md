# AI Delegate Plugin

Claude Code plugin for multi-agent AI delegation with smart CLI routing and domain expert debate system.

## Architecture

```
SmartRouter → DebateOrchestrator
├── ExpertRunner (parallel, budget models via Ollama)
│   ├── OWASP Expert → findings
│   ├── Auth Expert → findings
│   └── Input Expert → findings
├── ConsensusCalculator (80% agreement threshold)
└── Adjudicator (Sonnet) → final verdict
```

## Model Selection

### Default Models (via Ollama)

| Task | Model | CLI |
|------|-------|-----|
| audit | glm-5:cloud | Ollama |
| analyze | glm-5:cloud | Ollama |
| architecture | kimi-k2.5:cloud | Ollama |
| review | kimi-k2.5:cloud | Ollama |
| refactor | kimi-k2.5:cloud | Ollama |
| migrate | kimi-k2.5:cloud | Ollama |

### Budget Mode (Cost Savings)

| Complexity | Default Model | Budget Model |
|------------|---------------|---------------|
| LOW | haiku | glm-5:cloud |
| MEDIUM | glm-5:cloud | glm-5:cloud |
| HIGH | sonnet | kimi-k2.5:cloud |

### Fallback Priority

1. Ollama (GLM/Kimi) - structured output, cost-effective
2. Gemini - fast, multimodal
3. Codex - code generation, reasoning
4. Claude - fallback, safety

## CLI Types

```python
class CLIType(Enum):
    OLLAMA = "ollama"    # Priority 1
    GEMINI = "gemini"    # Priority 2
    CODEX = "codex"      # Priority 3
    CLAUDE = "claude"    # Priority 4
    GLM = "glm"          # Priority 5
```

## Constants Reference

All values centralized in `ai_delegate/constants.py`:

```python
from ai_delegate.constants import (
    Models,              # Model name strings
    TokenLimits,         # LOW=2000, MEDIUM=4000, HIGH=8000
    ComplexityThresholds, # LOW_LINES=100, MEDIUM_LINES=500
    QualityThresholds,    # FAST=90%, STANDARD=70%
    RetryConfig,         # MAX_RETRIES=3, API_TIMEOUT=300
    CLIPriority,         # OLLAMA=1, GEMINI=2, etc.
    TaskTypes,           # AUDIT, ANALYZE, ARCHITECTURE, etc.
    WorkerConstants,     # DEFAULT_MAX_WORKERS=4
)
```

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

**Always DEEP:** audit, architecture, migrate

## Key Files

- `ai_delegate/constants.py` - All centralized constants
- `ai_delegate/router.py` - SmartRouter, CLI detection, model selection
- `ai_delegate/supervisor.py` - Supervisor+Worker pattern
- `ai_delegate/debate/orchestrator.py` - Debate orchestration
- `ai_delegate/client.py` - Ollama client with fallback

## Testing

```bash
pytest tests/ -v --cov=ai_delegate
```

210 tests, 97% coverage.

## No Hardcoding Rule

All configuration values must reference `constants.py`:

- Model names → `Models.*`
- Token limits → `TokenLimits.*`
- Thresholds → `QualityThresholds.*` / `ComplexityThresholds.*`
- Task types → `TaskTypes.*`
- Worker config → `WorkerConstants.*`
