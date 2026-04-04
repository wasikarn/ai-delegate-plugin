#!/bin/bash
# restore-debate-context.sh - Restore debate context after compaction
# Reminds Claude about active debate session

set -euo pipefail

# Look for debate artifacts in plugin data directory
PLUGIN_DATA="${CLAUDE_PLUGIN_DATA:-$HOME/.claude/plugins/data/ai-delegate}"
DEBATE_FILE="$PLUGIN_DATA/current_debate.json"

# If no active debate, exit silently
if [ ! -f "$DEBATE_FILE" ]; then
    exit 0
fi

# Read debate state
TASK_TYPE=$(jq -r '.task_type // "unknown"' "$DEBATE_FILE" 2>/dev/null || echo "unknown")
CONSENSUS=$(jq -r '.consensus_score // 0' "$DEBATE_FILE" 2>/dev/null || echo "0")
TIER=$(jq -r '.tier_used // "standard"' "$DEBATE_FILE" 2>/dev/null || echo "standard")

# Build context reminder
CONTEXT="Active debate session detected. Task: $TASK_TYPE, Consensus: ${CONSENSUS}%, Tier: $TIER. Previous analysis context was compacted. If continuing analysis, consider re-running with ai-delegate $TASK_TYPE --file <path>"

# Output context
jq -n --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
        hookEventName: "PostCompact",
        additionalContext: $ctx
    }
}'