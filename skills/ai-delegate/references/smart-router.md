# Smart Router

Automatically selects the best available AI CLI and model for each task type.

## Philosophy

**"Push to the right man for the right job"** - Route tasks to the optimal tool based on:

1. Available CLIs (detected at runtime)
2. Task requirements (security, performance, architecture, etc.)
3. Model strengths (structured output, reasoning, speed)

## Supported CLIs

| CLI | Install Command | Strengths |
|-----|-----------------|----------|
| Ollama | `ollama.ai` | Structured output, cloud models |
| Gemini | `gemini` CLI | Fast, reasoning, multimodal |
| Codex | `codex` CLI | Code generation, reasoning |
| Claude | `claude` CLI | Fallback, safety |

## Task-CLI Mapping

| Task | Primary CLI | Model | Reason |
|------|-------------|-------|--------|
| `audit` | Ollama | glm-5:cloud | OWASP-focused, structured |
| `analyze` | Ollama | glm-5:cloud | Performance, structured |
| `architecture` | Codex | o3-mini | Deep reasoning |
| `refactor` | Ollama | kimi-k2.5:cloud | Complex reasoning |
| `migrate` | Codex | o3-mini | Dependency analysis |
| `review` | Ollama | kimi-k2.5:cloud | Multi-domain |

## Fallback Chain

```
1. Check Ollama (cloud models)
   ↓ not available
2. Check Gemini (fast, structured)
   ↓ not available
3. Check Codex (reasoning)
   ↓ not available
4. Fallback to Claude CLI
```

## Detection

```python
from ai_delegate.router import get_router

router = get_router()
available = router.get_available_clis()
# Returns: [CLIType.OLLAMA, CLIType.CLAUDE]
```

## CLI and Model Selection

```python
from ai_delegate.router import select_cli_and_model

# Automatic selection
cli_type, model = select_cli_and_model("audit")
# Returns: (CLIType.OLLAMA, "glm-5:cloud")

# With model override
cli_type, model = select_cli_and_model("audit", override_model="kimi-k2.5:cloud")
```

## Model Selection by Task

### Security Audit (audit)

| Priority | CLI | Model | Why |
|----------|-----|-------|-----|
| 1 | Ollama | glm-5:cloud | OWASP-focused, structured output |
| 2 | Gemini | gemini-2.0-flash | Fast security analysis |
| 3 | Codex | gpt-4o | Security analysis |
| 4 | Claude | sonnet | Fallback |

### Performance Analysis (analyze)

| Priority | CLI | Model | Why |
|----------|-----|-------|-----|
| 1 | Ollama | glm-5:cloud | Structured output |
| 2 | Gemini | gemini-2.0-flash | Fast analysis |
| 3 | Codex | gpt-4o | Performance |
| 4 | Claude | sonnet | Fallback |

### Architecture Review (architecture)

| Priority | CLI | Model | Why |
|----------|-----|-------|-----|
| 1 | Codex | o3-mini | Deep reasoning |
| 2 | Ollama | kimi-k2.5:cloud | Multi-perspective |
| 3 | Gemini | gemini-2.5-pro | Architecture reasoning |
| 4 | Claude | opus | Deep reasoning |

### Code Review (review)

| Priority | CLI | Model | Why |
|----------|-----|-------|-----|
| 1 | Ollama | kimi-k2.5:cloud | Multi-perspective |
| 2 | Codex | o3-mini | Reasoning |
| 3 | Gemini | gemini-2.5-pro | Review |
| 4 | Claude | sonnet | Fallback |

## Integration with CLI

```bash
# The router automatically selects the best available CLI
ai-delegate audit --file src/auth.py

# Override model (still uses best available CLI)
ai-delegate audit --model gemini-2.0-flash --file src/auth.py

# Specify CLI explicitly
ai-delegate audit --cli gemini --file src/auth.py
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `AI_DELEGATE_CLI` | Force specific CLI (ollama, gemini, codex, claude) |
| `AI_DELEGATE_MODEL` | Force specific model |
| `AI_DELEGATE_NO_FALLBACK` | Disable fallback to other CLIs |
