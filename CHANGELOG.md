# Changelog

All notable changes to ai-delegate-plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.4.0] - 2026-04-04

### Added

#### Token Optimization (82-98% startup savings)

- **Progressive disclosure SKILL.md** - Slimmed from 127 to 67 lines (~490 tokens)
- **Reference files** - Split into setup.md, domain-experts.md, quality-tiers.md, python-api.md
- **.claudeignore** - 20-40% input token reduction

#### Complexity-Based Model Selection (50-70% cost savings)

- **ComplexityLevel enum** - LOW/MEDIUM/HIGH complexity detection
- **detect_complexity()** - Automatic content complexity analysis
- **get_model_for_complexity()** - Model selection based on complexity
- **budget_mode parameter** - Enable ultra-low-cost DeepSeek models

#### Budget Models (98% cost reduction)

- **CLIType.DEEPSEEK** - DeepSeek CLI support
- **CLIType.GLM** - GLM CLI support
- **BUDGET_WORKERS** - Budget worker configurations

#### Supervisor+Worker Pattern

- **supervisor.py** - New module for distributed task execution
- **WorkerType enum** - CODE, SEARCH, REVIEW, DOCS, TEST
- **WorkerConfig** - Worker configuration dataclass
- **TaskResult** - Task execution result
- **create_supervisor()** - Factory function

#### Cache-Friendly Hooks (76-90% cache hit rate)

- **expert-context.sh** - Static prompts for better caching
- **Output format** - Summary at top to avoid "lost in middle"

### Changed

- **router.py** - Added DeepSeek/GLM detection, complexity detection
- ****init**.py** - Exported new modules (ComplexityLevel, Supervisor, etc.)
- **SKILL.md** - Restructured with progressive disclosure

### Tests

- **test_complexity.py** - 25 tests for complexity detection and model selection
- **test_supervisor.py** - 30 tests for Supervisor+Worker pattern

### Documentation

- **research-application.md** - Token optimization research summary
- **budget-mode.md** - Complete budget mode documentation
- **architecture-flow.md** - Architecture flow diagram

---

## [2.3.0] - 2026-04-03

### Added

- Smart router for CLI and model selection
- Domain experts (OWASP, Auth, Input for security)
- Quality tiers (FAST, STANDARD, DEEP)
- Debate orchestrator with consensus calculation

---

## [2.2.0] - 2026-04-02

### Added

- Expert context injection hooks
- Quality gates for expert outputs
- Auto-audit for sensitive files
- Analysis summary generation

---

## [2.1.0] - 2026-04-01

### Added

- Initial plugin structure
- Skills architecture
- Hook system (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, SubagentStart, SubagentStop, Stop, PostCompact)
- Basic CLI commands

---

## [2.0.0] - 2026-03-31

### Added

- Project initialization
- Core architecture design
