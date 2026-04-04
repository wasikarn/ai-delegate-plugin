# Model Selection Guide

## Available Models

| Model | Type | Strengths |
|-------|------|-----------|
| `glm-5:cloud` | Cloud | Structured output, security, performance |
| `kimi-k2.5:cloud` | Cloud | Reasoning, architecture, complex analysis |
| `sonnet` | Cloud | Fallback when rate limited |

## Task-Model Mapping

| Task | Default Model | Why |
|------|--------------|-----|
| `audit` | glm-5:cloud | OWASP-focused, structured output |
| `analyze` | glm-5:cloud | Deep analysis, performance |
| `architecture` | kimi-k2.5:cloud | Multi-perspective synthesis |
| `refactor` | kimi-k2.5:cloud | Complex reasoning |
| `migrate` | kimi-k2.5:cloud | Dependency analysis |
| `review` | kimi-k2.5:cloud | Multi-perspective analysis |

## Model Override

```bash
# Use specific model
ai-delegate audit --model glm-5:cloud --file src/auth.py
ai-delegate review --model kimi-k2.5:cloud --file src/

# Fallback behavior
# When rate limited: automatically switches to sonnet
```

## Cloud Models Only

No local model pull required. All models are cloud-based:

- `glm-5:cloud` — Fast, structured output
- `kimi-k2.5:cloud` — Deep reasoning
- `sonnet` — Reliable fallback
