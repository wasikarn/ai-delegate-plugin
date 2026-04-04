# Setup

One-time installation:

```bash
pip install -e "${CLAUDE_PLUGIN_ROOT}" --break-system-packages
```

Verify: `ai-delegate --version`

## Supported CLIs

| CLI | Install | Models | Use Case |
|-----|---------|--------|----------|
| Ollama | ollama.ai | glm-5, kimi-k2.5, sonnet | Structured output, cloud |
| Gemini | gemini CLI | gemini-2.0-flash, gemini-2.5-pro | Fast, multimodal |
| Codex | codex CLI | gpt-4o, o3-mini | Code generation, reasoning |
| Claude | claude CLI | sonnet, opus | Fallback, safety |

## Rate Limiting

Max retries: 3 (2s → 4s → 8s). Automatic fallback to next available CLI on rate limit.

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AI_DELEGATE_CLI` | Force specific CLI (ollama, gemini, codex, claude) |
| `AI_DELEGATE_MODEL` | Force specific model |
| `AI_DELEGATE_NO_FALLBACK` | Disable fallback to other CLIs |
