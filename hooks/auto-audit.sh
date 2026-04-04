#!/bin/bash
# auto-audit.sh - Auto-run security audit on sensitive file changes
# Triggers ai-delegate audit for security-sensitive files

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Extract file path
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null || echo "")

# If no file, exit silently
if [ -z "$FILE_PATH" ]; then
    exit 0
fi

# Check if file still exists
if [ ! -f "$FILE_PATH" ]; then
    exit 0
fi

# Define sensitive file patterns
SENSITIVE_PATTERNS="auth|security|password|crypto|token|session|login|middleware|guard"

# Check if file matches sensitive patterns
if ! echo "$FILE_PATH" | grep -iqE "$SENSITIVE_PATTERNS"; then
    exit 0
fi

# Check if ai-delegate is available
if ! command -v ai-delegate &> /dev/null; then
    exit 0
fi

# Run audit in background and output suggestion
jq -n --arg file "$FILE_PATH" '{
    hookSpecificOutput: {
        hookEventName: "PostToolUse",
        additionalContext: "Sensitive file modified: \($file). Consider running: ai-delegate audit --file \"\($file)\""
    }
}'