#!/bin/bash
# expert-gate.sh - Quality gate for domain expert outputs
# Validates expert findings have required format and evidence

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract agent info
AGENT_TYPE=$(echo "$INPUT" | jq -r '.agent_type // empty' 2>/dev/null || echo "")
AGENT_OUTPUT=$(echo "$INPUT" | jq -r '.output // empty' 2>/dev/null || echo "")

# If no agent type, exit silently
if [ -z "$AGENT_TYPE" ]; then
    exit 0
fi

# Only check for expert agents
case "$AGENT_TYPE" in
    security-expert|performance-expert|architecture-expert)
        ;;
    *)
        exit 0
        ;;
esac

# Check if output contains required elements
ERRORS=""

# Check for domain field
if ! echo "$AGENT_OUTPUT" | grep -q '"domain"'; then
    ERRORS="$ERRORS - Missing 'domain' field in output\n"
fi

# Check for findings array
if ! echo "$AGENT_OUTPUT" | grep -q '"findings"'; then
    ERRORS="$ERRORS - Missing 'findings' array in output\n"
fi

# Check for score
if ! echo "$AGENT_OUTPUT" | grep -q '"score"'; then
    ERRORS="$ERRORS - Missing 'score' field in output\n"
fi

# If errors found, block and request fix
if [ -n "$ERRORS" ]; then
    jq -n --arg errs "$ERRORS" --arg agent "$AGENT_TYPE" '{
        hookSpecificOutput: {
            hookEventName: "SubagentStop",
            decision: "block",
            reason: "Expert output validation failed for \($agent):\n\($errs)Please ensure output follows the required JSON format with domain, findings, and score."
        }
    }'
else
    exit 0
fi