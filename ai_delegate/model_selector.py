"""
Model selection utilities based on MODEL_INFO specifications.

Provides helper functions for intelligent model selection based on:
- Context window requirements
- Benchmark performance
- Modality support (vision, tools)
- Task type optimization
"""

from typing import List, Optional
from .constants import Models, MODEL_INFO, ModelSpec, TaskTypes


def get_model_for_context(needed_tokens: int) -> str:
    """
    Find a model with sufficient context window.

    Args:
        needed_tokens: Minimum context tokens required

    Returns:
        Model name with sufficient context (largest if multiple match)
    """
    candidates = [
        (name, spec)
        for name, spec in MODEL_INFO.items()
        if spec["context_window"] >= needed_tokens
    ]
    if not candidates:
        return Models.KIMI_K25_CLOUD  # fallback to largest

    # Return the one with largest context window
    return max(candidates, key=lambda x: x[1]["context_window"])[0]


def get_vision_capable_models() -> List[str]:
    """
    Get models that support vision/image input.

    Returns:
        List of model names with image modality support
    """
    return [
        name for name, spec in MODEL_INFO.items()
        if "image" in spec["modalities"]
    ]


def get_tools_capable_models() -> List[str]:
    """
    Get models that support tool/function calling.

    Returns:
        List of model names with tools feature
    """
    return [
        name for name, spec in MODEL_INFO.items()
        if "tools" in spec["features"]
    ]


def get_best_for_coding() -> str:
    """
    Get best model for coding tasks based on LiveCodeBench/SWE-bench.

    Returns:
        Model name with best coding benchmark scores
    """
    # Gemma4 has LiveCodeBench 80.0%, GLM-5 has SWE-bench 77.8%
    # Gemma4 is better for coding
    return Models.GEMMA4_31B_CLOUD


def get_best_for_reasoning() -> str:
    """
    Get best model for reasoning tasks based on AIME/GPQA benchmarks.

    Returns:
        Model name with best reasoning benchmark scores
    """
    # GLM-5: AIME 92.7%, GPQA 86.0%
    # Gemma4: AIME 89.2%, GPQA 84.3%
    return Models.GLM_5_CLOUD


def get_best_for_long_context() -> str:
    """
    Get model with largest context window.

    Returns:
        Model name with largest context (256K)
    """
    return max(
        MODEL_INFO.items(),
        key=lambda x: x[1]["context_window"]
    )[0]


def get_cheapest_model() -> str:
    """
    Get cheapest model (Ollama Cloud = $0 subscription).

    Returns:
        Model name with lowest cost
    """
    # All Ollama Cloud models are $0 per token
    return Models.GLM_5_CLOUD


def get_fastest_model() -> str:
    """
    Get fastest model for quick responses.

    Returns:
        Model name optimized for speed
    """
    # Claude Haiku is optimized for speed
    # GLM-5 is also fast (40B active params)
    return Models.CLAUDE_HAIKU


def supports_vision(model: str) -> bool:
    """
    Check if a model supports vision/image input.

    Args:
        model: Model name to check

    Returns:
        True if model supports image modality
    """
    if model not in MODEL_INFO:
        return False
    return "image" in MODEL_INFO[model]["modalities"]


def supports_tools(model: str) -> bool:
    """
    Check if a model supports tool/function calling.

    Args:
        model: Model name to check

    Returns:
        True if model supports tools
    """
    if model not in MODEL_INFO:
        return False
    return "tools" in MODEL_INFO[model]["features"]


def supports_extended_thinking(model: str) -> bool:
    """
    Check if a model supports extended thinking mode.

    Args:
        model: Model name to check

    Returns:
        True if model supports extended_thinking feature
    """
    if model not in MODEL_INFO:
        return False
    return "extended_thinking" in MODEL_INFO[model]["features"]


def get_model_for_task(
    task_type: str,
    needs_vision: bool = False,
    needs_long_context: bool = False,
    budget_mode: bool = False,
) -> str:
    """
    Get best model for a specific task type.

    Selects model based on:
    - Task type (coding, reasoning, analysis, etc.)
    - Vision requirements
    - Context window requirements
    - Budget constraints

    Args:
        task_type: Task type (audit, analyze, architecture, etc.)
        needs_vision: Whether task requires image input
        needs_long_context: Whether task needs >200K context
        budget_mode: Whether to prefer cheaper models

    Returns:
        Recommended model name
    """
    # Task-specific recommendations
    task_model_map = {
        TaskTypes.AUDIT: Models.GLM_5_CLOUD,      # Reasoning-focused
        TaskTypes.ANALYZE: Models.GLM_5_CLOUD,    # Reasoning-focused
        TaskTypes.ARCHITECTURE: Models.KIMI_K25_CLOUD,  # Vision + long context
        TaskTypes.REFACTOR: Models.GEMMA4_31B_CLOUD,  # Coding
        TaskTypes.MIGRATE: Models.KIMI_K25_CLOUD,  # Complex reasoning
        TaskTypes.REVIEW: Models.KIMI_K25_CLOUD,  # Vision for code review
        TaskTypes.DOCS: Models.GLM_5_CLOUD,       # Reasoning
        TaskTypes.TEST: Models.GEMMA4_31B_CLOUD,  # Coding
        TaskTypes.EXPLAIN: Models.KIMI_K25_CLOUD,  # Vision for diagrams
    }

    base_model = task_model_map.get(task_type, Models.KIMI_K25_CLOUD)

    # Override for vision requirement
    if needs_vision and not supports_vision(base_model):
        vision_models = get_vision_capable_models()
        if vision_models:
            base_model = vision_models[0]

    # Override for long context
    if needs_long_context:
        if MODEL_INFO[base_model]["context_window"] < 200_000:
            base_model = get_best_for_long_context()

    # Override for budget mode
    if budget_mode:
        # All Ollama Cloud models are $0
        base_model = Models.GLM_5_CLOUD

    return base_model


def get_model_info(model: str) -> Optional[ModelSpec]:
    """
    Get specification for a model.

    Args:
        model: Model name

    Returns:
        ModelSpec dict or None if not found
    """
    return MODEL_INFO.get(model)


def list_models() -> List[str]:
    """
    List all available models.

    Returns:
        List of model names
    """
    return list(MODEL_INFO.keys())


def get_context_window(model: str) -> int:
    """
    Get context window size for a model.

    Args:
        model: Model name

    Returns:
        Context window in tokens (0 if model not found)
    """
    if model in MODEL_INFO:
        return MODEL_INFO[model]["context_window"]
    return 0


def get_benchmark(model: str, benchmark: str) -> Optional[float]:
    """
    Get benchmark score for a model.

    Args:
        model: Model name
        benchmark: Benchmark name (e.g., "aime_2026", "swe_bench")

    Returns:
        Benchmark score or None if not available
    """
    if model not in MODEL_INFO:
        return None
    return MODEL_INFO[model]["benchmarks"].get(benchmark)