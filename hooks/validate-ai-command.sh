#!/bin/bash
# validate-ai-command.sh - Validate ai-delegate commands before execution
# Blocks invalid commands and suggests corrections

# Read hook input
INPUT=$(cat)

# Extract command — empty for non-Bash tools (Grep, Read, etc.)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null) || COMMAND=""
COMMAND="${COMMAND:-}"

# Only intercept when ai-delegate is the executable being invoked
# (starts the command or follows a shell separator), not inside strings/args
if ! echo "$COMMAND" | grep -qE "(^|;|\|\||&&|\|)\s*ai-delegate(\s|$)"; then
    exit 0
fi

# Valid tasks
VALID_TASKS="audit|analyze|architecture|refactor|migrate|review"

# Allow meta flags (--version, --help)
if echo "$COMMAND" | grep -qE "ai-delegate\s+(--version|--help|-h|-V)"; then
    exit 0
fi

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