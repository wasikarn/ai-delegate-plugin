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

logger = logging.getLogger(__name__)


class CLIType(Enum):
    """Available AI CLI types."""
    OLLAMA = "ollama"
    GEMINI = "gemini"
    CODEX = "codex"
    CLAUDE = "claude"
    DEEPSEEK = "deepseek"  # Budget option
    GLM = "glm"            # Chinese market


class ComplexityLevel(Enum):
    """Content complexity levels for model selection."""
    LOW = "low"        # Simple checks, <100 lines
    MEDIUM = "medium"  # Standard analysis, <500 lines
    HIGH = "high"      # Complex reasoning, architecture


@dataclass
class CLIConfig:
    """Configuration for an AI CLI."""
    cli_type: CLIType
    cli_name: str  # Command name
    models: Dict[str, str]  # task_type -> model_name
    strengths: List[str]  # What this CLI is good at
    structured_output: bool  # Supports JSON output
    fallback_priority: int  # Lower = higher priority


# =============================================================================
# CLI Configurations by Task Type
# =============================================================================

# Ollama models (cloud via Ollama)
OLLAMA_CONFIG = CLIConfig(
    cli_type=CLIType.OLLAMA,
    cli_name="ollama",
    models={
        "audit": "glm-5:cloud",        # OWASP-focused, structured output
        "analyze": "glm-5:cloud",        # Deep analysis, performance
        "architecture": "kimi-k2.5:cloud",  # Reasoning, multi-perspective
        "refactor": "kimi-k2.5:cloud",  # Complex reasoning
        "migrate": "kimi-k2.5:cloud",    # Dependency analysis
        "review": "kimi-k2.5:cloud",    # Multi-domain review
    },
    strengths=["structured_output", "security", "performance", "architecture"],
    structured_output=True,
    fallback_priority=1,
)

# Gemini CLI models
GEMINI_CONFIG = CLIConfig(
    cli_type=CLIType.GEMINI,
    cli_name="gemini",
    models={
        "audit": "gemini-2.0-flash",      # Fast security analysis
        "analyze": "gemini-2.0-flash",     # Performance analysis
        "architecture": "gemini-2.5-pro",   # Deep architecture reasoning
        "refactor": "gemini-2.0-flash",    # Refactoring suggestions
        "migrate": "gemini-2.5-pro",        # Migration analysis
        "review": "gemini-2.5-pro",        # Multi-domain review
    },
    strengths=["fast", "reasoning", "multimodal"],
    structured_output=True,
    fallback_priority=2,
)

# Codex CLI models
CODEX_CONFIG = CLIConfig(
    cli_type=CLIType.CODEX,
    cli_name="codex",
    models={
        "audit": "gpt-4o",              # Security analysis
        "analyze": "gpt-4o",             # Performance
        "architecture": "o3-mini",       # Architecture reasoning
        "refactor": "gpt-4o",           # Refactoring
        "migrate": "o3-mini",            # Migration analysis
        "review": "o3-mini",            # Multi-domain review
    },
    strengths=["code_generation", "reasoning", "documentation"],
    structured_output=True,
    fallback_priority=3,
)

# Claude CLI models (fallback)
CLAUDE_CONFIG = CLIConfig(
    cli_type=CLIType.CLAUDE,
    cli_name="claude",
    models={
        "audit": "sonnet",              # Security analysis
        "analyze": "sonnet",             # Performance
        "architecture": "opus",          # Architecture (needs deep reasoning)
        "refactor": "sonnet",           # Refactoring
        "migrate": "opus",               # Migration analysis
        "review": "sonnet",             # Multi-domain review
    },
    strengths=["reasoning", "structured_output", "safety"],
    structured_output=False,  # Claude CLI doesn't have --format json
    fallback_priority=4,       # Always last resort
)

# DeepSeek CLI (budget option - ultra low cost)
DEEPSEEK_CONFIG = CLIConfig(
    cli_type=CLIType.DEEPSEEK,
    cli_name="deepseek",
    models={
        "audit": "deepseek-chat",       # Budget security analysis
        "analyze": "deepseek-chat",      # Budget performance
        "architecture": "deepseek-reasoner",  # Budget reasoning
        "refactor": "deepseek-chat",
        "migrate": "deepseek-reasoner",
        "review": "deepseek-chat",
    },
    strengths=["budget", "fast", "reasoning"],
    structured_output=True,
    fallback_priority=5,  # Budget option
)

# GLM CLI (Chinese market, cost-effective)
GLM_CONFIG = CLIConfig(
    cli_type=CLIType.GLM,
    cli_name="glm",
    models={
        "audit": "glm-5:cloud",         # Already in Ollama
        "analyze": "glm-5:cloud",
        "architecture": "glm-5:cloud",
        "refactor": "glm-5:cloud",
        "migrate": "glm-5:cloud",
        "review": "glm-5:cloud",
    },
    strengths=["chinese_market", "structured_output", "cloud"],
    structured_output=True,
    fallback_priority=6,  # Alternative option
)


# =============================================================================
# Complexity-Based Model Selection
# =============================================================================

# Model selection by complexity (50-70% cost savings)
# Budget mode uses DeepSeek for ultra-low cost
COMPLEXITY_MODEL_MAP = {
    ComplexityLevel.LOW: {
        "model": "haiku",
        "cli": CLIType.CLAUDE,
        "max_tokens": 2000,
        "reason": "Simple checks, fast response",
        "budget_model": "deepseek-chat",  # Budget alternative
    },
    ComplexityLevel.MEDIUM: {
        "model": "glm-5:cloud",
        "cli": CLIType.OLLAMA,
        "max_tokens": 4000,
        "reason": "Standard analysis, cost-effective",
        "budget_model": "deepseek-chat",  # Budget alternative
    },
    ComplexityLevel.HIGH: {
        "model": "sonnet",
        "cli": CLIType.CLAUDE,
        "max_tokens": 8000,
        "reason": "Complex reasoning, high accuracy",
        "budget_model": "deepseek-reasoner",  # Budget alternative
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
    if task_type == "architecture":
        return ComplexityLevel.HIGH

    # Simple single-file checks
    if lines < 100 and task_type in ["audit"]:
        return ComplexityLevel.LOW

    # Medium complexity
    if lines < 500:
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

    Detection order:
    1. Check which CLIs are installed
    2. Select best CLI for task type
    3. Choose appropriate model for the CLI
    4. Fall back to next available CLI if needed
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
            task_type: Task type (audit, analyze, architecture, etc.)
            prefer_structured_output: Prefer CLIs that support JSON output

        Returns:
            Tuple of (CLIConfig, model_name)

        Raises:
            RuntimeError: If no CLI is available
        """
        # Priority order based on task characteristics
        if task_type == "audit":
            # Security benefits from Ollama's structured output
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        elif task_type == "architecture":
            # Architecture needs deep reasoning
            priority_order = [
                (CLIType.CODEX, CODEX_CONFIG),   # o3-mini for reasoning
                (CLIType.OLLAMA, OLLAMA_CONFIG), # kimi-k2.5 for reasoning
                (CLIType.GEMINI, GEMINI_CONFIG), # gemini-2.5-pro
                (CLIType.CLAUDE, CLAUDE_CONFIG), # opus
            ]
        elif task_type == "analyze":
            # Performance needs structured output
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        elif task_type == "review":
            # Multi-domain needs balanced approach
            priority_order = [
                (CLIType.OLLAMA, OLLAMA_CONFIG),   # kimi for multi-perspective
                (CLIType.CODEX, CODEX_CONFIG),     # o3-mini for reasoning
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ]
        else:
            # Default priority
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
                # Still consider it if it's the last option
                if len(self.get_available_clis()) == 1:
                    model = config.models.get(task_type, "sonnet")
                    logger.info(f"Selected {cli_type.value} with model {model}")
                    return config, model
                continue

            model = config.models.get(task_type, "sonnet")
            logger.info(f"Selected {cli_type.value} with model {model} for task {task_type}")
            return config, model

        # Fallback: use first available CLI
        for cli_type, config in priority_order:
            if self.is_available(cli_type):
                model = config.models.get(task_type, "sonnet")
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
                model = config.models.get(task_type, "sonnet")
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
        }

        config = configs.get(cli_type)
        if not config:
            return "sonnet"

        return config.models.get(task_type, "sonnet")


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
        # Use override model with first available CLI
        for cli_type in [CLIType.OLLAMA, CLIType.GEMINI, CLIType.CODEX, CLIType.CLAUDE]:
            if router.is_available(cli_type):
                return cli_type, override_model

    config, model = router.select_cli_for_task(task_type, prefer_structured_output)
    return config.cli_type, model