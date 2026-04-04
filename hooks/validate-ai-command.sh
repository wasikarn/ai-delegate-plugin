#!/bin/bash
# validate-ai-command.sh - Validate ai-delegate commands before execution
# Blocks invalid commands and suggests corrections

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract command
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || echo "")

# If not ai-delegate command, allow
if ! echo "$COMMAND" | grep -q "ai-delegate"; then
    exit 0
fi

# Valid tasks
VALID_TASKS="audit|analyze|architecture|refactor|migrate|review"

# Check if command has valid task
if ! echo "$COMMAND" | grep -qE "ai-delegate ($VALID_TASKS)"; then
    jq -n --arg cmd "$COMMAND" '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "Invalid ai-delegate task. Valid tasks: audit, analyze, architecture, refactor, migrate, review"
        }
    }'
    exit 0
fi

# Check if --file is present (required for most tasks)
if ! echo "$COMMAND" | grep -q "\-\-file" && ! echo "$COMMAND" | grep -qE "ai-delegate (review)"; then
    jq -n '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "ask",
            permissionDecisionReason: "ai-delegate commands typically require --file <path>. Continue anyway?"
        }
    }'
    exit 0
fi

# Allow valid command
exit 0