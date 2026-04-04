#!/bin/bash
# detect-analysis-task.sh - Auto-route to ai-delegate skill based on prompt keywords
# Returns context suggestion if analysis-related keywords detected

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract prompt text
PROMPT=$(echo "$INPUT" | jq -r '.prompt // empty' 2>/dev/null || echo "")

# If no prompt, exit silently
if [ -z "$PROMPT" ]; then
    exit 0
fi

# Define keyword patterns
SECURITY_KEYWORDS="security|vulnerability|audit|xss|sql injection|auth|owasp|cve|csrf|injection"
PERFORMANCE_KEYWORDS="performance|slow|optimize|bottleneck|latency|memory leak|n\+1|query|cache"
ARCHITECTURE_KEYWORDS="architecture|design pattern|solid|coupling|cohesion|scalability|layered"
REFACTOR_KEYWORDS="refactor|simplify|complexity|code smell|technical debt|clean code|duplication"
MIGRATE_KEYWORDS="migrate|upgrade|breaking change|version|dependency|api change|deprecation"
TESTING_KEYWORDS="test|coverage|unit test|integration test|mock|assertion|test quality"
CODE_QUALITY_KEYWORDS="code quality|maintainability|readability|code smell|naming|structure"
DATABASE_KEYWORDS="database|schema|migration|query|index|sql|nosql|orm"

# Check for keywords (case insensitive)
CONTEXT=""

if echo "$PROMPT" | grep -iqE "$SECURITY_KEYWORDS"; then
    CONTEXT="Detected security-related request. Consider using: ai-delegate audit --file <path>"
elif echo "$PROMPT" | grep -iqE "$PERFORMANCE_KEYWORDS"; then
    CONTEXT="Detected performance-related request. Consider using: ai-delegate analyze --file <path>"
elif echo "$PROMPT" | grep -iqE "$ARCHITECTURE_KEYWORDS"; then
    CONTEXT="Detected architecture-related request. Consider using: ai-delegate architecture --file <path>"
elif echo "$PROMPT" | grep -iqE "$REFACTOR_KEYWORDS"; then
    CONTEXT="Detected refactoring-related request. Consider using: ai-delegate refactor --file <path>"
elif echo "$PROMPT" | grep -iqE "$MIGRATE_KEYWORDS"; then
    CONTEXT="Detected migration-related request. Consider using: ai-delegate migrate --file <path>"
elif echo "$PROMPT" | grep -iqE "$TESTING_KEYWORDS"; then
    CONTEXT="Detected testing-related request. Consider using: ai-delegate test --file <path>"
elif echo "$PROMPT" | grep -iqE "$CODE_QUALITY_KEYWORDS"; then
    CONTEXT="Detected code quality-related request. Consider using: ai-delegate quality --file <path>"
elif echo "$PROMPT" | grep -iqE "$DATABASE_KEYWORDS"; then
    CONTEXT="Detected database-related request. Consider using: ai-delegate database --file <path>"
fi

# Output context if detected
if [ -n "$CONTEXT" ]; then
    jq -n --arg ctx "$CONTEXT" '{
        hookSpecificOutput: {
            hookEventName: "UserPromptSubmit",
            additionalContext: $ctx
        }
    }'
else
    exit 0
fi