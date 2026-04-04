#!/bin/bash
# analysis-summary.sh - Generate summary of analysis session
# Reports findings from ai-delegate debate session

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
HIGH_COUNT=$(grep -c "high\|critical" "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
MEDIUM_COUNT=$(grep -c "medium" "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")
LOW_COUNT=$(grep -c "low\|info" "$TRANSCRIPT_PATH" 2>/dev/null || echo "0")

# Build summary
SUMMARY="Analysis session summary: "
if [ "$HIGH_COUNT" -gt 0 ] || [ "$MEDIUM_COUNT" -gt 0 ] || [ "$LOW_COUNT" -gt 0 ]; then
    SUMMARY="$SUMMARY Findings: HIGH=$HIGH_COUNT, MEDIUM=$MEDIUM_COUNT, LOW=$LOW_COUNT"
else
    SUMMARY="$SUMMARY No significant findings"
fi

# Output summary
jq -n --arg summary "$SUMMARY" '{
    hookSpecificOutput: {
        hookEventName: "Stop",
        additionalContext: $summary
    }
}'