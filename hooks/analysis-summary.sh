#!/bin/bash
# analysis-summary.sh - Log analysis session summary to stderr on session end
# Stop hook: must exit 0 silently (no hookSpecificOutput — invalid for Stop event)

set -euo pipefail

# Read hook input
INPUT=$(cat)

# Check for analysis-related transcript
TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // empty' 2>/dev/null || echo "")

# If no transcript, exit silently
if [ -z "$TRANSCRIPT_PATH" ] || [ ! -f "$TRANSCRIPT_PATH" ]; then
    exit 0
fi

# Check if ai-delegate was used in session
if ! grep -q "ai-delegate" "$TRANSCRIPT_PATH" 2>/dev/null; then
    exit 0
fi

# Count findings by severity (rough estimation from transcript)
HIGH_COUNT=$(grep -c '"severity":\s*"high"\|"severity":\s*"critical"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
MEDIUM_COUNT=$(grep -c '"severity":\s*"medium"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
LOW_COUNT=$(grep -c '"severity":\s*"low"' "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")

# Log to stderr (Stop hook must not write to stdout)
echo "[ai-delegate] Session summary: HIGH=${HIGH_COUNT} MEDIUM=${MEDIUM_COUNT} LOW=${LOW_COUNT}" >&2

exit 0
