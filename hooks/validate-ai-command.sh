#!/bin/bash
# validate-ai-command.sh - Validate ai-delegate commands before execution

# Read hook input
INPUT=$(cat)

# Extract command — empty for non-Bash tools (Grep, Read, etc.)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || COMMAND=""
COMMAND="${COMMAND:-}"

# Extract the EXECUTABLE (first token in the command, basename only)
# This correctly handles: /usr/bin/ai-delegate, ./ai-delegate, ai-delegate
EXECUTABLE=$(echo "$COMMAND" | awk '{print $1}' | awk -F'/' '{print $NF}')

# Only intercept ai-delegate commands
if [ "$EXECUTABLE" != "ai-delegate" ]; then
    exit 0
fi

# Valid tasks
VALID_TASKS="audit|analyze|architecture|refactor|migrate|review"

# Allow meta flags (--version, --help, -h, -V)
if echo "$COMMAND" | grep -qE "ai-delegate\s+(--version|--help|-h|-V)"; then
    exit 0
fi

# Check if command has a valid task
if ! echo "$COMMAND" | grep -qE "ai-delegate\s+($VALID_TASKS)(\s|$)"; then
    jq -n --arg cmd "$COMMAND" '{
        hookSpecificOutput: {
            hookEventName: "PreToolUse",
            permissionDecision: "deny",
            permissionDecisionReason: "Invalid ai-delegate task. Valid tasks: audit, analyze, architecture, refactor, migrate, review"
        }
    }'
    exit 0
fi

# Allow valid command
exit 0