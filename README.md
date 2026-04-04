# AI Delegate Plugin

**Multi-agent AI delegation framework with smart CLI routing and domain expert debate system.**

[![Version](https://img.shields.io/badge/version-0.0.1-blue.svg)](https://github.com/wasikarn/ai-delegate-plugin)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-164%20tests-97%25%20coverage-brightgreen.svg)]()

---

## Features

### 🎯 Smart Router

Automatically selects the best available AI CLI and model for each task:

- **Ollama** (glm-5:cloud, kimi-k2.5:cloud) - Structured output, cloud models
- **Gemini** (gemini-2.0-flash, gemini-2.5-pro) - Fast, multimodal
- **Codex** (gpt-4o, o3-mini) - Code generation, reasoning
- **Claude** (sonnet, opus) - Fallback, safety
- **DeepSeek** (deepseek-chat, deepseek-reasoner) - Budget option
- **GLM** (glm-5:cloud) - Chinese market

### 💰 Token Optimization (82-98% Savings)

- **Progressive disclosure SKILL.md** - Slimmed from 127 to 67 lines
- **.claudeignore** - 20-40% input token reduction
- **Cache-friendly hooks** - 76-90% cache hit rate
- **Complexity-based model selection** - 50-70% cost savings

### 🤖 Budget Mode (98% Cost Reduction)

- Use DeepSeek/GLM for ultra-low-cost analysis
- Automatic fallback chain
- Quality trade-off: ~40% lower benchmarks for ~5% of cost

### 🔄 Supervisor+Worker Pattern

- Supervisor (Sonnet/Opus) for planning and coordination
- Workers (Haiku/GLM/DeepSeek) for execution
- Parallel task delegation
- 98% cost reduction for delegated tasks

### 🎭 Multi-Agent Debate System

- Domain experts analyze in parallel
- Debate findings for consensus
- Adjudicator synthesizes final verdict
- Quality tiers: FAST (≥90%), STANDARD (70-90%), DEEP (<70%)

### 🪝 Hooks System

- **SessionStart** - Auto-install Python package
- **UserPromptSubmit** - Keyword detection for analysis tasks
- **PreToolUse** - Validate ai-delegate commands
- **PostToolUse** - Auto-audit sensitive files
- **SubagentStart/Stop** - Context injection + quality gates
- **Stop** - Analysis summary generation
- **PostCompact** - Restore debate context

---

## Installation

### As Claude Code Plugin

Add to your `~/.claude/settings.json`:

```json
{
  "plugins": {
    "marketplaces": [
      "/path/to/ai-delegate-plugin"
    ]
  }
}
```

### Python Package Setup

One-time installation:

```bash
pip install -e /path/to/ai-delegate-plugin --break-system-packages
```

Verify:

```bash
ai-delegate --version
```

---

## Quick Start

### CLI Usage

```bash
# Security audit (auto-selects best CLI)
ai-delegate audit --file src/auth.py

# Performance analysis
ai-delegate analyze --file src/api.py

# Architecture review
ai-delegate architecture --file ./src/

# Multi-domain code review
ai-delegate review src/main.py -d security,performance

# Override model
ai-delegate audit --model gemini-2.0-flash --file src/auth.py

# Budget mode (DeepSeek)
ai-delegate audit --budget --file src/auth.py
```

### Python API

```python
from ai_delegate import (
    SmartRouter,
    DebateOrchestrator,
    TaskConfig,
    detect_complexity,
    get_model_for_complexity,
    ComplexityLevel,
)

# Detect content complexity
complexity = detect_complexity(code_content, "audit")
# Returns: ComplexityLevel.LOW/MEDIUM/HIGH

# Get model for complexity (default mode)
config = get_model_for_complexity(complexity)
# Returns: {"model": "glm-5:cloud", "cli": CLIType.OLLAMA, ...}

# Get model for complexity (budget mode)
config = get_model_for_complexity(complexity, budget_mode=True)
# Returns: {"model": "deepseek-chat", "cli": CLIType.DEEPSEEK, ...}

# Auto-select CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")

# Create orchestrator with selected model
config = TaskConfig.from_task_type("audit")
orchestrator = DebateOrchestrator(model=model, task_config=config)
verdict = orchestrator.analyze(content, tier="auto")
```

### Supervisor+Worker Pattern

```python
from ai_delegate import create_supervisor, WorkerType

# Create budget supervisor
supervisor = create_supervisor(budget_mode=True, max_workers=4)

# Delegate single task
result = supervisor.delegate(
    WorkerType.CODE,
    analyze_code,
    file_path="src/auth.py"
)

# Delegate parallel tasks
results = supervisor.delegate_parallel([
    {"task_type": WorkerType.CODE, "task": analyze_code, "args": ("file1.py",)},
    {"task_type": WorkerType.REVIEW, "task": review_code, "args": ("file2.py",)},
])
```

---

## Configuration

### Environment Variables

```bash
# Model selection
export AI_DELEGATE_CLI=ollama          # Force specific CLI
export AI_DELEGATE_MODEL=glm-5:cloud   # Force specific model
export AI_DELEGATE_NO_FALLBACK=1       # Disable fallback chain
export AI_DELEGATE_BUDGET_MODE=1       # Enable budget mode globally
```

### Token Optimization

```json
// ~/.claude/settings.json
{
  "env": {
    "MAX_THINKING_TOKENS": "8000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

### .claudeignore

Create `.claudeignore` in your project root:

```gitignore
# Dependencies
node_modules/
__pycache__/
.venv/

# Build outputs
dist/
build/
*.egg-info/

# Generated files
*.generated.*

# Test fixtures
tests/fixtures/
**/__snapshots__/

# Lock files
package-lock.json
poetry.lock
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Smart Router                            │
│  Detects: Ollama ✓ | Gemini ✓ | Codex ✗ | Claude ✓         │
│  Selects: Ollama/glm-5:cloud for "audit"                   │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 DebateOrchestrator                           │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │              ExpertRunner (Parallel)                   │ │
│  │                                                        │ │
│  │  OWASP Expert ───┐                                    │ │
│  │  Auth Expert ────┼──► DebatePhase                     │ │
│  │  Input Expert ───┘         │                          │ │
│  │                             ▼                          │ │
│  │                      Adjudicator                       │ │
│  │                             │                          │ │
│  │                             ▼                          │ │
│  │                     Consensus + Verdict               │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

---

## Hooks

| Hook | Event | Action |
|------|-------|--------|
| `detect-analysis-task.sh` | UserPromptSubmit | Detect keywords, suggest skill |
| `validate-ai-command.sh` | PreToolUse/Bash | Validate ai-delegate commands |
| `expert-context.sh` | SubagentStart | Inject domain context |
| `expert-gate.sh` | SubagentStop | Quality gate for expert outputs |
| `auto-audit.sh` | PostToolUse/Write | Auto-audit sensitive files |
| `analysis-summary.sh` | Stop | Generate analysis summary |
| `restore-debate-context.sh` | PostCompact | Restore debate context |

---

## Domain Experts

| Domain | Experts | Focus |
|--------|---------|-------|
| **Security** | OWASP, Auth, Input | Vulnerabilities, secrets, OWASP Top 10 |
| **Performance** | Complexity, Database, Memory | Bottlenecks, queries, caching |
| **Architecture** | Patterns, SOLID, Scalability | Design, coupling, cohesion |
| **Refactor** | Simplification, Patterns | Code improvements |
| **Migrate** | API, Dependencies | Migration risks |

---

## Quality Tiers

| Consensus | Tier | Process |
|-----------|------|---------|
| ≥ 90% | FAST | Output consensus immediately |
| 70-90% | STANDARD | Debate + adjudication |
| < 70% | DEEP | Judge evaluation |

**Defaults:** `audit/architecture/migrate` → DEEP, others → consensus-based

---

## Complexity Detection

| Complexity | Lines | Model (Default) | Model (Budget) |
|-----------|-------|-----------------|-----------------|
| **LOW** | <100 | haiku | deepseek-chat |
| **MEDIUM** | 100-500 | glm-5:cloud | deepseek-chat |
| **HIGH** | >500 | sonnet | deepseek-reasoner |

### Task-Specific Rules

- **Architecture** → Always HIGH
- **Audit (small)** → LOW (if <100 lines)
- **Others** → Standard rules

---

## Cost Comparison

| Model | Input | Output | Use Case |
|-------|-------|--------|----------|
| **DeepSeek-V3** | $0.28/M | $0.42/M | Budget tasks |
| **GLM-5** | ~$1/M | ~$5/M | Standard tasks |
| **Claude Haiku** | $1/M | $5/M | Fast tasks |
| **Claude Sonnet** | $3/M | $15/M | Premium coding |
| **Claude Opus** | $5/M | $25/M | Architecture |

**Budget mode savings:** ~95% for standard tasks, ~98% for complex reasoning.

---

## Constants API

All configuration values are centralized in `constants.py`:

```python
from ai_delegate.constants import (
    Models,           # Model name constants
    TokenLimits,      # Token limits (2000, 4000, 8000)
    ComplexityThresholds,  # Line thresholds (100, 500)
    QualityThresholds,    # Consensus thresholds (70, 90)
    RetryConfig,      # Retry/timeout constants
    CLIPriority,      # Fallback priority (1-6)
    TaskTypes,        # Task type constants
    ExpertDomains,    # Expert domain constants
    DEFAULT_MODELS,   # Task-to-model mapping
    CLI_STRENGTHS,    # CLI capability mapping
)

# Example usage
model = Models.GLM_5_CLOUD
max_tokens = TokenLimits.MEDIUM_MAX_TOKENS  # 4000
task = TaskTypes.AUDIT
threshold = QualityThresholds.CONSENSUS_PERCENTAGE  # 80
```

---

## Test Coverage

```bash
pytest tests/ -v --cov=ai_delegate
```

- **164 tests**, 97% coverage
- `test_complexity.py` - 25 tests for complexity detection
- `test_supervisor.py` - 30 tests for Supervisor+Worker pattern

---

## Project Structure

```
ai-delegate-plugin/
├── ai_delegate/
│   ├── __init__.py          # Public API
│   ├── cli.py                # CLI entry point
│   ├── client.py             # AI client implementations
│   ├── config.py             # Task configurations
│   ├── constants.py          # Centralized constants ⭐ NEW
│   ├── models.py             # Data models
│   ├── router.py             # Smart router (refactored)
│   ├── supervisor.py         # Supervisor+Worker pattern ⭐ NEW
│   └── debate/
│       └── orchestrator.py   # Debate orchestration
├── skills/
│   └── ai-delegate/
│       ├── SKILL.md          # Skill definition (slimmed)
│       └── references/       # Reference documentation
├── hooks/
│   ├── hooks.json           # Hook configuration
│   ├── detect-analysis-task.sh
│   ├── validate-ai-command.sh
│   ├── expert-context.sh     # Cache-friendly ⭐ UPDATED
│   ├── expert-gate.sh
│   ├── auto-audit.sh
│   ├── analysis-summary.sh
│   └── restore-debate-context.sh
├── tests/
│   ├── test_complexity.py    # ⭐ NEW
│   ├── test_supervisor.py    # ⭐ NEW
│   └── ...
├── docs/
│   ├── architecture-flow.md
│   ├── research-application.md
│   └── budget-mode.md
├── scripts/
│   └── create-release.sh
├── .claudeignore             # ⭐ NEW
├── CHANGELOG.md
├── README.md
└── pyproject.toml
```

---

## Documentation

- [Architecture Flow](docs/architecture-flow.md) - How components interact
- [Research Application](docs/research-application.md) - Token optimization research
- [Budget Mode](docs/budget-mode.md) - Budget mode documentation

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

---

## Acknowledgments

- Research from Claude Code Optimization, Multi-Agent Systems, Token Efficiency
- Inspired by multi-agent debate frameworks
- Built for Claude Code plugin ecosystem
