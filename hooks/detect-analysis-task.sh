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
SECURITY_KEYWORDS="security|vulnerability|audit|xss|sql injection|auth|owasp|cve"
PERFORMANCE_KEYWORDS="performance|slow|optimize|bottleneck|latency|memory leak|n\+1"
ARCHITECTURE_KEYWORDS="architecture|design pattern|solid|coupling|cohesion|refactor"

# Check for keywords (case insensitive)
CONTEXT=""

if echo "$PROMPT" | grep -iqE "$SECURITY_KEYWORDS"; then
    CONTEXT="Detected security-related request. Consider using: ai-delegate audit --file <path>"
elif echo "$PROMPT" | grep -iqE "$PERFORMANCE_KEYWORDS"; then
    CONTEXT="Detected performance-related request. Consider using: ai-delegate analyze --file <path>"
elif echo "$PROMPT" | grep -iqE "$ARCHITECTURE_KEYWORDS"; then
    CONTEXT="Detected architecture-related request. Consider using: ai-delegate architecture --file <path>"
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