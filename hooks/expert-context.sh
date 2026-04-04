#!/bin/bash
# expert-context.sh - Inject context for domain expert agents
# Provides base context and project information to experts

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract agent info
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null || echo "")
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null || echo "")

# If no agent type, exit silently
if [ -z "$AGENT_TYPE" ]; then
    exit 0
fi

# Build context based on agent type
CONTEXT=""

case "$AGENT_TYPE" in
    security-expert)
        CONTEXT="You are analyzing code for security vulnerabilities. Focus on OWASP Top 10, input validation, authentication, and secret detection."
        ;;
    performance-expert)
        CONTEXT="You are analyzing code for performance issues. Focus on algorithm complexity, database queries, caching, and memory usage."
        ;;
    architecture-expert)
        CONTEXT="You are analyzing code architecture. Focus on SOLID principles, design patterns, coupling, and cohesion."
        ;;
    *)
        exit 0
        ;;
esac

# Get project context if available
PROJECT_CONTEXT=""
if [ -n "$CWD" ] && [ -d "$CWD" ]; then
    # Detect framework
    if [ -f "$CWD/package.json" ]; then
        FRAMEWORK=$(grep -o '"next"\|"react"\|"vue"\|"express"' "$CWD/package.json" 2>/dev/null | head -1 | tr -d '"' || echo "")
        if [ -n "$FRAMEWORK" ]; then
            PROJECT_CONTEXT="Project uses $FRAMEWORK framework."
        fi
    elif [ -f "$CWD/requirements.txt" ]; then
        PROJECT_CONTEXT="Project uses Python."
    elif [ -f "$CWD/go.mod" ]; then
        PROJECT_CONTEXT="Project uses Go."
    fi
fi

# Combine context
FULL_CONTEXT="$CONTEXT"
if [ -n "$PROJECT_CONTEXT" ]; then
    FULL_CONTEXT="$CONTEXT $PROJECT_CONTEXT"
fi

# Output context
jq -n --arg ctx "$FULL_CONTEXT" '{
    hookSpecificOutput: {
        hookEventName: "SubagentStart",
        additionalContext: $ctx
    }
}'