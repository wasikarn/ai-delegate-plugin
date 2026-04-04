#!/bin/bash
# create-release.sh - Create GitHub release for ai-delegate-plugin
# Usage: ./scripts/create-release.sh <version>

set -euo pipefail

# Check if version is provided
if [ $# -eq 0 ]; then
    echo "Usage: $0 <version>"
    echo "Example: $0 2.4.0"
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

Features:
- Token optimization (82-98% startup savings)
- Complexity-based model selection (50-70% cost savings)
- Budget mode with DeepSeek/GLM (98% cost reduction)
- Supervisor+Worker pattern for distributed tasks
- Cache-friendly hooks (76-90% cache hit rate)
- Progressive disclosure SKILL.md structure

Improvements:
- Slim SKILL.md: 127→67 lines
- 4 new reference files: setup.md, domain-experts.md, quality-tiers.md, python-api.md
- Expert output format: summary at top (avoid 'lost in middle')
- New CLI support: DeepSeek, GLM
- New exports: ComplexityLevel, detect_complexity, get_model_for_complexity, Supervisor, WorkerType

Tests:
- test_complexity.py: 25 tests
- test_supervisor.py: 30 tests

Docs:
- research-application.md: Token optimization research
- budget-mode.md: Budget mode documentation
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