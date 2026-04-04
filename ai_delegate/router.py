"""
Smart router for selecting optimal AI CLI and model based on task requirements.

Philosophy: "Push to the right man for the right job" - Select the best available
CLI and model combination for each task type.
"""

import shutil
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from .constants import (
    Models,
    TokenLimits,
    ComplexityThresholds,
    QualityThresholds,
    RetryConfig,
    CLIPriority,
    TaskTypes,
    OLLAMA_MODELS,
    GEMINI_MODELS,
    CODEX_MODELS,
    CLAUDE_MODELS,
    DEEPSEEK_MODELS,
    GLM_MODELS,
    CLI_STRENGTHS,
    FALLBACK_MODEL,
)

logger = logging.getLogger(__name__)


class CLIType(Enum):
    """Available AI CLI types."""
    OLLAMA = "ollama"
    GEMINI = "gemini"
    CODEX = "codex"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"
    GLM = "glm"


class ComplexityLevel(Enum):
    """Content complexity levels for model selection."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class CLIConfig:
    """Configuration for an AI CLI."""
    cli_type: CLIType
    cli_name: str
    models: Dict[str, str]
    strengths: List[str]
    structured_output: bool
    fallback_priority: int


# =============================================================================
# CLI Configurations
# =============================================================================

OLLAMA_CONFIG = CLIConfig(
    cli_type=CLIType.OLLAMA,
    cli_name="ollama",
    models=OLLAMA_MODELS,
    strengths=CLI_STRENGTHS["ollama"],
    structured_output=True,
    fallback_priority=CLIPriority.OLLAMA,
)

GEMINI_CONFIG = CLIConfig(
    cli_type=CLIType.GEMINI,
    cli_name="gemini",
    models=GEMINI_MODELS,
    strengths=CLI_STRENGTHS["gemini"],
    structured_output=True,
    fallback_priority=CLIPriority.GEMINI,
)

CODEX_CONFIG = CLIConfig(
    cli_type=CLIType.CODEX,
    cli_name="codex",
    models=CODEX_MODELS,
    strengths=CLI_STRENGTHS["codex"],
    structured_output=True,
    fallback_priority=CLIPriority.CODEX,
)

CLAUDE_CONFIG = CLIConfig(
    cli_type=CLIType.CLAUDE,
    cli_name="claude",
    models=CLAUDE_MODELS,
    strengths=CLI_STRENGTHS["claude"],
    structured_output=False,
    fallback_priority=CLIPriority.CLAUDE,
)

DEEPSEEK_CONFIG = CLIConfig(
    cli_type=CLIType.DEEPSEEK,
    cli_name="deepseek",
    models=DEEPSEEK_MODELS,
    strengths=CLI_STRENGTHS["deepseek"],
    structured_output=True,
    fallback_priority=CLIPriority.DEEPSEEK,
)

GLM_CONFIG = CLIConfig(
    cli_type=CLIType.GLM,
    cli_name="glm",
    models=GLM_MODELS,
    strengths=CLI_STRENGTHS["glm"],
    structured_output=True,
    fallback_priority=CLIPriority.GLM,
)


# =============================================================================
# Complexity-Based Model Selection
# =============================================================================

COMPLEXITY_MODEL_MAP = {
    ComplexityLevel.LOW: {
        "model": Models.CLAUDE_HAIKU,
        "cli": CLIType.CLAUDE,
        "max_tokens": TokenLimits.LOW_MAX_TOKENS,
        "reason": "Simple checks, fast response",
        "budget_model": Models.DEEPSEEK_CHAT,
    },
    ComplexityLevel.MEDIUM: {
        "model": Models.GLM_5_CLOUD,
        "cli": CLIType.OLLAMA,
        "max_tokens": TokenLimits.MEDIUM_MAX_TOKENS,
        "reason": "Standard analysis, cost-effective",
        "budget_model": Models.DEEPSEEK_CHAT,
    },
    ComplexityLevel.HIGH: {
        "model": Models.CLAUDE_SONNET,
        "cli": CLIType.CLAUDE,
        "max_tokens": TokenLimits.HIGH_MAX_TOKENS,
        "reason": "Complex reasoning, high accuracy",
        "budget_model": Models.DEEPSEEK_REASONER,
    },
}


def detect_complexity(content: str, task_type: str) -> ComplexityLevel:
    """
    Detect content complexity for model selection.

    Args:
        content: Code content to analyze
        task_type: Task type (audit, analyze, etc.)

    Returns:
        ComplexityLevel for model selection
    """
    if not content:
        return ComplexityLevel.LOW

    lines = content.count('\n') + 1

    # Architecture always needs high complexity
    if task_type == TaskTypes.ARCHITECTURE:
        return ComplexityLevel.HIGH

    # Simple single-file checks
    if lines < ComplexityThresholds.LOW_LINES and task_type in [TaskTypes.AUDIT]:
        return ComplexityLevel.LOW

    # Medium complexity
    if lines < ComplexityThresholds.MEDIUM_LINES:
        return ComplexityLevel.MEDIUM

    # Complex
    return ComplexityLevel.HIGH


def get_model_for_complexity(complexity: ComplexityLevel, budget_mode: bool = False) -> Dict:
    """
    Get model config for complexity level.

    Args:
        complexity: Detected complexity level
        budget_mode: Use budget models (DeepSeek) for cost savings

    Returns:
        Dict with model, cli, max_tokens, reason
    """
    config = COMPLEXITY_MODEL_MAP.get(complexity, COMPLEXITY_MODEL_MAP[ComplexityLevel.MEDIUM])

    if budget_mode and "budget_model" in config:
        return {
            "model": config["budget_model"],
            "cli": CLIType.DEEPSEEK,
            "max_tokens": config["max_tokens"],
            "reason": f"Budget mode: {config['reason']}"
        }

    return config


class SmartRouter:
    """
    Intelligently routes tasks to the best available CLI and model.
    """

    def __init__(self):
        """Initialize router and detect available CLIs."""
        self._available_clis: Dict[CLIType, bool] = {}
        self._detect_clis()

    def _detect_clis(self) -> None:
        """Detect which AI CLIs are installed."""
        self._available_clis = {
            CLIType.OLLAMA: shutil.which("ollama") is not None,
            CLIType.GEMINI: shutil.which("gemini") is not None,
            CLIType.CODEX: shutil.which("codex") is not None,
            CLIType.CLAUDE: shutil.which("claude") is not None,
            CLIType.DEEPSEEK: shutil.which("deepseek") is not None,
            CLIType.GLM: shutil.which("glm") is not None,
        }

        available = [cli.value for cli, avail in self._available_clis.items() if avail]
        logger.info(f"Available CLIs: {available}")

    def is_available(self, cli_type: CLIType) -> bool:
        """Check if a CLI is available."""
        return self._available_clis.get(cli_type, False)

    def get_available_clis(self) -> List[CLIType]:
        """Get list of available CLI types."""
        return [cli for cli, avail in self._available_clis.items() if avail]

    def select_cli_for_task(
        self,
        task_type: str,
        prefer_structured_output: bool = True,
    ) -> Tuple[CLIConfig, str]:
        """
        Select the best CLI and model for a task.

        Args:
            task_type: Task type (audit, analyze, etc.)
            prefer_structured_output: Prefer CLIs that support JSON output

        Returns:
            Tuple of (CLIConfig, model_name)

        Raises:
            RuntimeError: If no CLI is available
        """
        # Priority order based on task characteristics
        if task_type == TaskTypes.AUDIT:
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        elif task_type == TaskTypes.ARCHITECTURE:
            priority_order = [
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        elif task_type == TaskTypes.ANALYZE:
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        elif task_type == TaskTypes.REVIEW:
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        else:
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]

        # Filter by availability and structured output preference
        for cli_type, config in priority_order:
            if not self.is_available(cli_type):
                continue

            if prefer_structured_output and not config.structured_output:
                if len(self.get_available_clis()) == 1:
                    model = config.models.get(task_type, FALLBACK_MODEL)
                    logger.info(f"Selected {cli_type.value} with model {model}")
                    return config, model
                continue

            model = config.models.get(task_type, FALLBACK_MODEL)
            logger.info(f"Selected {cli_type.value} with model {model} for task {task_type}")
            return config, model

        # Fallback: use first available CLI
        for cli_type, config in priority_order:
            if self.is_available(cli_type):
                model = config.models.get(task_type, FALLBACK_MODEL)
                logger.warning(f"Using fallback CLI {cli_type.value} with model {model}")
                return config, model

        raise RuntimeError(
            "No AI CLI available. Install one of: ollama, gemini, codex, or claude"
        )

    def get_fallback_chain(self, task_type: str) -> List[Tuple[CLIType, str]]:
        """
        Get the fallback chain for a task.

        Args:
            task_type: Task type

        Returns:
            List of (CLIType, model) tuples in fallback order
        """
        chain = []
        for cli_type in [CLIType.OLLAMA, CLIType.GEMINI, CLIType.CODEX, CLIType.CLAUDE]:
            if self.is_available(cli_type):
                config = {
                    CLIType.OLLAMA: OLLAMA_CONFIG,
                    CLIType.GEMINI: GEMINI_CONFIG,
                    CLIType.CODEX: CODEX_CONFIG,
                    CLIType.CLAUDE: CLAUDE_CONFIG,
                }[cli_type]
                model = config.models.get(task_type, FALLBACK_MODEL)
                chain.append((cli_type, model))
        return chain

    def get_model_for_cli(
        self,
        cli_type: CLIType,
        task_type: str,
        override_model: Optional[str] = None,
    ) -> str:
        """
        Get the appropriate model for a CLI and task.

        Args:
            cli_type: CLI type
            task_type: Task type
            override_model: Override model if specified

        Returns:
            Model name
        """
        if override_model:
            return override_model

        configs = {
            CLIType.OLLAMA: OLLAMA_CONFIG,
            CLIType.GEMINI: GEMINI_CONFIG,
            CLIType.CODEX: CODEX_CONFIG,
            CLIType.CLAUDE: CLAUDE_CONFIG,
            CLIType.DEEPSEEK: DEEPSEEK_CONFIG,
            CLIType.GLM: GLM_CONFIG,
        }

        config = configs.get(cli_type)
        if not config:
            return FALLBACK_MODEL

        return config.models.get(task_type, FALLBACK_MODEL)


# Global router instance
_router: Optional[SmartRouter] = None


def get_router() -> SmartRouter:
    """Get or create the global router instance."""
    global _router
    if _router is None:
        _router = SmartRouter()
    return _router


def select_cli_and_model(
    task_type: str,
    prefer_structured_output: bool = True,
    override_model: Optional[str] = None,
) -> Tuple[CLIType, str]:
    """
    Convenience function to select CLI and model.

    Args:
        task_type: Task type
        prefer_structured_output: Prefer CLIs with JSON output
        override_model: Override model if specified

    Returns:
        Tuple of (CLIType, model_name)
    """
    router = get_router()

    if override_model:
        for cli_type in [CLIType.OLLAMA, CLIType.GEMINI, CLIType.CODEX, CLIType.CLAUDE]:
            if router.is_available(cli_type):
                return cli_type, override_model

    config, model = router.select_cli_for_task(task_type, prefer_structured_output)
    return config.cli_type, model