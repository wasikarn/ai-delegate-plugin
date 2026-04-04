#!/bin/bash
# create-release.sh - Create GitHub release for ai-delegate-plugin
# Usage: ./scripts/create-release.sh <version>

set -euo pipefail

# Check if version is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 0.0.1"
    exit 1
fi

VERSION=$1
TAG="v${VERSION}"

# Get current branch
BRANCH=$(git rev-parse --abbrev-ref HEAD)

echo "Creating release ${TAG} from branch ${BRANCH}"
echo "---"

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    echo "ERROR: Uncommitted changes found. Please commit first."
    git status --short
    exit 1
fi

# Create tag
echo "Creating tag ${TAG}..."
git tag -a "${TAG}" -m "Release ${TAG}

First release of ai-delegate-plugin!

## Features

### Core Framework
- Smart Router: Multi-CLI support (Ollama, Gemini, Codex, Claude, DeepSeek, GLM)
- Debate Orchestrator: Multi-agent parallel analysis
- Domain Experts: Security, Performance, Architecture, Refactor, Migrate

### Token Optimization (82-98% startup savings)
- Progressive disclosure SKILL.md (127→67 lines)
- Reference files: setup.md, domain-experts.md, quality-tiers.md, python-api.md
- .claudeignore for input reduction

### Complexity-Based Model Selection (50-70% cost savings)
- Automatic complexity detection (LOW/MEDIUM/HIGH)
- Budget mode for ultra-low-cost analysis (98% savings)

### Supervisor+Worker Pattern
- Distributed task execution
- Worker types: CODE, SEARCH, REVIEW, DOCS, TEST
- Parallel task delegation

### Hooks System
- SessionStart: Auto-install
- UserPromptSubmit: Keyword detection
- PreToolUse: Command validation
- PostToolUse: Auto-audit
- SubagentStart/Stop: Context injection + quality gates

## Tests
- 164 tests, 97% coverage
- test_complexity.py: 25 tests
- test_supervisor.py: 30 tests

## Documentation
- Architecture flow diagram
- Research application summary
- Budget mode guide
"

# Push tag
echo "Pushing tag to origin..."
git push origin "${TAG}"

echo "---"
echo "Tag ${TAG} created and pushed."
echo ""
echo "Next steps:"
echo "1. Go to: https://github.com/wasikarn/ai-delegate-plugin/releases/new"
echo "2. Select tag: ${TAG}"
echo "3. Title: ai-delegate-plugin ${TAG}"
echo "4. Copy release notes from above"
echo "5. Click 'Create release'"