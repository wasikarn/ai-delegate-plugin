#!/bin/bash
# expert-context.sh - Inject context for domain expert agents
# Provides base context and project information to experts
# Optimized for prompt caching (static prompts, external references)

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

# Build context based on agent type (STATIC - cache-friendly)
case "$AGENT_TYPE" in
    security-expert)
        CONTEXT="You are analyzing code for security vulnerabilities.
Focus on OWASP Top 10, input validation, authentication, and secret detection.

OUTPUT FORMAT (JSON):
1. summary - One-line critical finding (TOP)
2. severity_breakdown - Quick counts {high, medium, low}
3. top_findings - Top 3 most important findings
4. domain - Your domain (security)
5. score - Confidence score (0-100)
6. detailed_findings - Full analysis (BOTTOM)

Project context: See ${CWD}/package.json for framework details."
        ;;
    performance-expert)
        CONTEXT="You are analyzing code for performance issues.
Focus on algorithm complexity, database queries, caching, and memory usage.

OUTPUT FORMAT (JSON):
1. summary - One-line critical finding (TOP)
2. severity_breakdown - Quick counts {high, medium, low}
3. top_findings - Top 3 most important findings
4. domain - Your domain (performance)
5. score - Confidence score (0-100)
6. detailed_findings - Full analysis (BOTTOM)

Project context: See ${CWD}/package.json for framework details."
        ;;
    architecture-expert)
        CONTEXT="You are analyzing code architecture.
Focus on SOLID principles, design patterns, coupling, and cohesion.

OUTPUT FORMAT (JSON):
1. summary - One-line critical finding (TOP)
2. severity_breakdown - Quick counts {high, medium, low}
3. top_findings - Top 3 most important findings
4. domain - Your domain (architecture)
5. score - Confidence score (0-100)
6. detailed_findings - Full analysis (BOTTOM)

Project context: See ${CWD}/package.json for framework details."
        ;;
    *)
        exit 0
        ;;
esac

# Output context (static prompts for better caching)
jq -n --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
        hookEventName: "SubagentStart",
        additionalContext: $ctx
    }
}'