# Changelog

All notable changes to ai-delegate-plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.2] - 2026-04-04

### Added

#### Validation Module

- **validate_prompt()** - Security validation for user prompts (injection, encoding attacks)
- **validate_model_name()** - Model name validation with model list checking
- **ValidationResult** - Validation result dataclass with error/warning fields
- **Security patterns** - 11 injection patterns, 4 encoding patterns
- **Configurable validation** - `strict_validation` mode for hard rejection

### Changed

#### OllamaClient SRP Refactoring

- **Single Responsibility Principle** - Split OllamaClient into 5 focused components:
  - `CLIExecutor` - Subprocess execution and CLI availability checks
  - `RateLimiter` - Retry logic with exponential backoff
  - `OutputProcessor` - Output cleaning and thinking prefix stripping
  - `ResponseParser` - JSON extraction and parsing
  - `OllamaClient` - Orchestrates components (thin composition layer)
- **Dependency Injection** - All components injectable via constructor for testing
- **Factory Pattern** - `create_client()` for easy client creation with defaults
- **Test Coverage** - 90 new tests for SRP components (210 → 300 tests)

### Fixed

- All `_run_ollama` calls updated to new signature (json_output parameter)
- All tests passing with refactored architecture

---

## [0.0.1] - 2026-04-04

### Added

#### Core Framework

- **Smart Router** - Multi-CLI support (Ollama, Gemini, Codex, Claude, DeepSeek, GLM)
- **Debate Orchestrator** - Multi-agent parallel analysis with consensus calculation
- **Domain Experts** - Security (OWASP, Auth, Input), Performance, Architecture, Refactor, Migrate

#### Token Optimization (82-98% startup savings)

- **Progressive disclosure SKILL.md** - Slimmed from 127 to 67 lines (~490 tokens)
- **Reference files** - setup.md, domain-experts.md, quality-tiers.md, python-api.md
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

- **supervisor.py** - Distributed task execution
- **WorkerType enum** - CODE, SEARCH, REVIEW, DOCS, TEST
- **WorkerConfig** - Worker configuration dataclass
- **TaskResult** - Task execution result
- **create_supervisor()** - Factory function

#### Hooks System

- **SessionStart** - Auto-install Python package
- **UserPromptSubmit** - Keyword detection for analysis tasks
- **PreToolUse/Bash** - Validate ai-delegate commands
- **PostToolUse/Write|Edit** - Auto-audit sensitive files
- **SubagentStart** - Inject domain context
- **SubagentStop** - Quality gate for expert outputs
- **Stop** - Analysis summary generation
- **PostCompact** - Restore debate context

#### Cache-Friendly Hooks (76-90% cache hit rate)

- **expert-context.sh** - Static prompts for better caching
- **Output format** - Summary at top to avoid "lost in middle"

### Documentation

- **docs/architecture-flow.md** - Architecture flow diagram
- **docs/research-application.md** - Token optimization research summary
- **docs/budget-mode.md** - Budget mode documentation
- **skills/ai-delegate/references/** - Detailed reference documentation

### Tests

- **test_complexity.py** - 25 tests for complexity detection and model selection
- **test_supervisor.py** - 30 tests for Supervisor+Worker pattern
- **test_*.py** - 164 tests, 97% coverage

---

## Future Releases

### [0.1.0] - Planned

- CLI installer (pip install ai-delegate)
- Web dashboard for analysis history
- Custom expert configuration

### [1.0.0] - Planned

- Stable API
- Full documentation
- Performance benchmarks
