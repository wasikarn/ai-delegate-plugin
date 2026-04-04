# AI Delegate Plugin

Multi-agent debate system for code analysis. Domain experts analyze in parallel, debate findings, and adjudicator synthesizes final verdict.

## Installation

### As Claude Code Plugin

Add to your `~/.claude/settings.json`:

```json
{
  "plugins": {
    "marketplaces": [
      "/Users/kobig/Codes/Personals/ai-delegate-plugin"
    ]
  }
}
```

### Python Package Setup

One-time installation:

```bash
pip install -e /Users/kobig/Codes/Personals/ai-delegate-plugin --break-system-packages
```

## Usage

```bash
# Security audit
ai-delegate audit --file src/auth.py

# Performance analysis
ai-delegate analyze --tier deep --file src/api.py

# Architecture review
ai-delegate architecture --file ./src/

# Multi-domain code review
ai-delegate review src/main.py -d security,performance
```

## Features

- **Multi-Agent Debate**: Domain experts analyze in parallel, debate findings
- **Adaptive Quality Tiers**: FAST/STANDARD/DEEP based on consensus
- **Multiple Domains**: security, performance, architecture, refactor, migrate
- **Cloud Models**: glm-5:cloud, kimi-k2.5:cloud, sonnet (fallback)

## Architecture

```
DebateOrchestrator (thin coordinator)
├── ExpertRunner        # Parallel execution (pooled threads)
├── ConsensusCalculator # Consensus calculation
├── DebatePhase         # Debate rounds
└── Adjudicator         # Verdict synthesis + judge
```

## Test Coverage

164 tests, 97% coverage.

## License

MIT
