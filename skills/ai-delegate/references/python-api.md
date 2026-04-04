# Python API

## Basic Usage

```python
from ai_delegate import SmartRouter, DebateOrchestrator, TaskConfig

# Auto-select CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")

# Create orchestrator with selected model
config = TaskConfig.from_task_type("audit")
orchestrator = DebateOrchestrator(model=model, task_config=config)
verdict = orchestrator.analyze(content, tier="auto")
```

## Smart Router

```python
from ai_delegate.router import get_router, select_cli_and_model

router = get_router()
available = router.get_available_clis()
# Returns: [CLIType.OLLAMA, CLIType.CLAUDE]

# Automatic selection
cli_type, model = select_cli_and_model("audit")
# Returns: (CLIType.OLLAMA, "glm-5:cloud")

# With model override
cli_type, model = select_cli_and_model("audit", override_model="kimi-k2.5:cloud")
```

## Complexity Detection

```python
from ai_delegate.router import detect_complexity, ComplexityLevel

complexity = detect_complexity(code_content, "audit")

if complexity == ComplexityLevel.LOW:
    # Use haiku for simple checks
    model = "haiku"
elif complexity == ComplexityLevel.MEDIUM:
    # Use glm-5 for standard analysis
    model = "glm-5:cloud"
else:
    # Use sonnet for complex reasoning
    model = "sonnet"
```

## Debate Orchestrator

```python
from ai_delegate import DebateOrchestrator, TaskConfig

config = TaskConfig(
    task_type="audit",
    domain="security",
    experts=["owasp", "auth", "input"],
    tier="deep"
)

orchestrator = DebateOrchestrator(config)
result = orchestrator.analyze(
    content=file_content,
    file_path="src/auth.py"
)

print(result.summary)
print(result.findings)
print(result.consensus_score)
```
