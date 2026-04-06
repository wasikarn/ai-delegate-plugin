# Changelog

All notable changes to ai-delegate-plugin will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

#### Hooks Optimization — OMC Compatibility

- **SessionStart hook removed** — No longer auto-installs Python package on every session
  - Reduces session startup overhead (~2-5s per session)
  - Prevents duplicate hooks when used alongside OMC plugin
  - Installation now requires manual `pip install -e` once per environment
  - README updated with installation note

### Added

#### Phase 1A Foundation — Pure Module Extraction

- **consensus.py** — Standalone `ConsensusCalculator` extracted from `debate/orchestrator.py`
  - `ConsensusCalculator.calculate(expert_results)` — computes consensus/disputed/unique findings
  - `normalize_finding(raw_dict)` — translates domain-format dicts to canonical `Finding` objects
  - Case-insensitive deduplication by `(severity.lower(), issue.lower())`
- **complexity.py** — Deterministic `ComplexityAssessor` for content complexity scoring
  - `ComplexityAssessor.assess(content)` — rule-based scoring: line count + keyword signals
  - `ComplexityAssessor.assess_files(paths)` — aggregates across multiple files
  - `ComplexityScore` dataclass: level, domains, file_count, line_count, security_signals
  - Security signals > 5 bumps low → medium level
- **catalog.py** — `AgentCatalog` for discovering agent definitions across installed plugins
  - Scans `~/.claude/plugins/*/agents/*.md` for agent frontmatter
  - S1: Agent name validation (regex `[a-zA-Z0-9_-]+`, command injection prevention)
  - S2: Plugin trust boundary via `~/.claude/ai-delegate-trust.json` allowlist
  - S3: Path traversal prevention via `resolve()` + `is_relative_to()`
  - S4: DoS protection — 100 agent cap, 5s timeout (SIGALRM/Unix), 4096-byte frontmatter limit
  - `AgentCatalog.for_domains(domains)` — filter agents by detected domain keywords
  - `DOMAIN_KEYWORDS` — 7 domains: security, performance, architecture, code-quality, testing, migration, database

#### Phase 1B Foundation — Path B Agent Executor

- **agent_executor.py** — Path B subprocess execution via `ollama launch claude`
  - `AgentExecutorConfig` — repo_path, allowed_tools, budget_usd=0.20, timeout_sec=120, effort="low"
  - `AgentExecutor.run(assignment, task)` — subprocess call, JSON result parsing, ExpertResult
  - `AgentExecutor._build_cmd()` — always list args (never shell=True); --bare, --dangerously-skip-permissions
  - `AgentPool.run_parallel(assignments, task)` — ThreadPoolExecutor, failed agents skipped (logged)
- **model_assigner.py** — Routes each agent to Path A/B/C
  - `ExecutionPath` enum: SDK (Path A) / CLI (Path B) / AGENT (Path C)
  - `ExpertAssignment` dataclass: agent + path + resolved model
  - `ModelAssigner.assign()` — no file tools → SDK; deep/high-complexity + file tools → AGENT; else → CLI
  - `ModelAssigner.assign_all()` — batch routing, preserves order
  - `FILE_ACCESS_TOOLS` = {Read, Glob, Grep, Bash}; `DEEP_DOMAINS` = {architecture, migration}
- **constants.py** — Added `AgentExecutorDefaults` class (ALLOWED_TOOLS, BUDGET_USD, TIMEOUT_SEC, EFFORT)
- **40 new tests** across test_agent_executor.py, test_agent_pool.py, test_model_assigner.py (628 total)

#### Phase 1C Foundation — Path D Agent Teams Peer Debate

- **debate_runner.py** — Data models for Path D Agent Teams peer debate handoff
  - `DisputedFindingsBundle` — serializable Python → Claude Code skill layer handoff
    - `to_json()` / `from_json()` — full roundtrip serialization
    - Carries: disputed_findings, expert_results, task_type, file_context
  - `DebateResult` — DebateTeamRunner → Adjudicator result container
    - `from_json()` — deserializes lead agent output
    - resolved_findings: ≥80% AGREE — skip Adjudicator
    - unresolved_findings: <80% AGREE — escalate to Adjudicator
- **ExpertResult.from_dict()** — inverse of `to_dict()`, required for bundle deserialization
- **ai_delegate/agents/debate-lead.md** — Agent Teams lead (Sonnet)
  - Creates expert teammates (kimi-k2.5:cloud), coordinates 1-round debate
  - AGREE/CHALLENGE/WITHDRAW protocol via mailbox
  - 80% consensus threshold for resolution
- **ai_delegate/agents/debate-expert.md** — Agent teammate template (kimi-k2.5:cloud)
  - Responds to disputed findings from shared task list
  - Does NOT re-analyze codebase — works from findings context only
- **tests/agents/** — 4 scenario fixtures for manual debate protocol validation
  - scenario_all_agree, scenario_one_challenged, scenario_split_verdict, scenario_teammate_timeout

---

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
