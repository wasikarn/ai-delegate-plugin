"""
Smart router for selecting optimal AI CLI and model based on task requirements.

Philosophy: "Push to the right man for the right job" - Select the best available
CLI and model combination for each task type.
"""

import functools
import time
import shutil
import logging
from typing import TYPE_CHECKING, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum

if TYPE_CHECKING:
    from .memory import AnalysisMemory

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
    GLM_MODELS,
    CLI_STRENGTHS,
    FALLBACK_MODEL,
    HealthConfig,
    AdaptiveConfig,
)

logger = logging.getLogger(__name__)


class CLIType(Enum):
    """Available AI CLI types."""
    OLLAMA = "ollama"
    GEMINI = "gemini"
    CODEX = "codex"
    CLAUDE = "claude"
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
        "budget_model": Models.GLM_5_CLOUD,
    },
    ComplexityLevel.MEDIUM: {
        "model": Models.GLM_5_CLOUD,
        "cli": CLIType.OLLAMA,
        "max_tokens": TokenLimits.MEDIUM_MAX_TOKENS,
        "reason": "Standard analysis, cost-effective",
        "budget_model": Models.GLM_5_CLOUD,
    },
    ComplexityLevel.HIGH: {
        "model": Models.CLAUDE_SONNET,
        "cli": CLIType.CLAUDE,
        "max_tokens": TokenLimits.HIGH_MAX_TOKENS,
        "reason": "Complex reasoning, high accuracy",
        "budget_model": Models.KIMI_K25_CLOUD,
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


@functools.lru_cache(maxsize=16)
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
            "cli": CLIType.OLLAMA,  # GLM runs via Ollama
            "max_tokens": config["max_tokens"],
            "reason": f"Budget mode: {config['reason']}"
        }

    return config


class CliHealthMonitor:
    """In-memory CLI health tracker. Fresh per session, zero I/O on healthy runs."""

    _TTL: Dict[str, float] = {
        "rate_limit": HealthConfig.RATE_LIMIT_TTL,
        "network":    HealthConfig.NETWORK_TTL,
        "auth":       HealthConfig.AUTH_TTL,
    }

    def __init__(self) -> None:
        self._degraded: Dict[CLIType, Tuple[float, str]] = {}
        self._auth_warned: Set[CLIType] = set()

    def mark_failed(self, cli: CLIType, error_type: str) -> None:
        """Mark CLI as degraded. error_type: 'rate_limit' | 'auth' | 'network'"""
        if isinstance(cli, str):
            try:
                cli = CLIType(cli)
            except ValueError:
                return
        self._degraded[cli] = (time.monotonic(), error_type)

    def is_degraded(self, cli: CLIType) -> bool:
        """Returns True if CLI is within its TTL window."""
        if cli not in self._degraded:
            return False
        failed_at, error_type = self._degraded[cli]
        ttl = self._TTL.get(error_type, 60.0)
        if ttl == float("inf"):
            return True
        if time.monotonic() - failed_at > ttl:
            del self._degraded[cli]
            return False
        return True

    def should_warn_auth(self, cli: CLIType) -> bool:
        """Returns True once per session for auth-degraded CLIs."""
        if cli in self._auth_warned:
            return False
        self._auth_warned.add(cli)
        return True

    def clear(self, cli: CLIType) -> None:
        """Manually clear degraded state (e.g., after user fixes auth)."""
        self._degraded.pop(cli, None)
        self._auth_warned.discard(cli)


class SmartRouter:
    """
    Intelligently routes tasks to the best available CLI and model.
    """

    def __init__(self):
        """Initialize router and detect available CLIs."""
        self._available_clis: Dict[CLIType, bool] = {}
        self.health_monitor = CliHealthMonitor()
        self._detect_clis()

    def _detect_clis(self) -> None:
        """Detect which AI CLIs are installed."""
        self._available_clis = {
            CLIType.OLLAMA: shutil.which("ollama") is not None,
            CLIType.GEMINI: shutil.which("gemini") is not None,
            CLIType.CODEX: shutil.which("codex") is not None,
            CLIType.CLAUDE: shutil.which("claude") is not None,
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
        memory: Optional["AnalysisMemory"] = None,
        no_adaptive: bool = False,
    ) -> Tuple[CLIConfig, str]:
        """
        Select the best CLI and model for a task.

        Phases (when memory provided and not no_adaptive):
          0. Health gate: skip degraded CLIs
          1. Priors: sort by win_rate from cli_performance (decisive from run 1)
          2. Streak correction (runs 3+): lock winning streak, skip losing CLI
          3. Win rate override (runs 10+): permanent override if delta >=15pp
          Anti-thrash: >=3 distinct CLIs in last 3 runs -> hold static

        Args:
            task_type: Task type (audit, analyze, etc.)
            prefer_structured_output: Prefer CLIs that support JSON output
            memory: AnalysisMemory for adaptive routing (None = static only)
            no_adaptive: If True, use static priority map only

        Returns:
            Tuple of (CLIConfig, model_name)

        Raises:
            RuntimeError: If no CLI is available
        """
        _default = [
            (CLIType.OLLAMA, OLLAMA_CONFIG),
            (CLIType.GEMINI, GEMINI_CONFIG),
            (CLIType.CODEX, CODEX_CONFIG),
            (CLIType.CLAUDE, CLAUDE_CONFIG),
        ]
        _task_priority_map = {
            TaskTypes.AUDIT: _default,
            TaskTypes.ANALYZE: _default,
            TaskTypes.ARCHITECTURE: [
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ],
            TaskTypes.REVIEW: [
                (CLIType.OLLAMA, OLLAMA_CONFIG),
                (CLIType.CODEX, CODEX_CONFIG),
                (CLIType.GEMINI, GEMINI_CONFIG),
                (CLIType.CLAUDE, CLAUDE_CONFIG),
            ],
        }
        priority_order = _task_priority_map.get(task_type, _default)

        # Step 0: Health gate — installed + not degraded
        available = [
            (cli_type, config)
            for cli_type, config in priority_order
            if self.is_available(cli_type) and not self.health_monitor.is_degraded(cli_type)
        ]

        # Warn once per session for auth-degraded CLIs
        for cli_type, _ in priority_order:
            if self.is_available(cli_type) and self.health_monitor.is_degraded(cli_type):
                state = self.health_monitor._degraded.get(cli_type)
                if state and state[1] == "auth" and self.health_monitor.should_warn_auth(cli_type):
                    logger.warning(f"⚠ {cli_type.value} unavailable (auth error) — skipping")

        if not available:
            raise RuntimeError(
                "No AI CLI available. Install one of: ollama, gemini, codex, or claude"
            )

        def _select_from(candidates: List[Tuple[CLIType, CLIConfig]]) -> Tuple[CLIConfig, str]:
            """Pick first candidate respecting prefer_structured_output."""
            for ct, cfg in candidates:
                if prefer_structured_output and not cfg.structured_output:
                    if len(candidates) == 1:
                        break
                    continue
                return cfg, cfg.models.get(task_type, FALLBACK_MODEL)
            cfg = candidates[0][1]
            return cfg, cfg.models.get(task_type, FALLBACK_MODEL)

        # Static selection (reference for Phase 3 + fallback when no_adaptive)
        static_config, static_model = _select_from(available)

        if no_adaptive or memory is None:
            logger.info(
                f"Selected {static_config.cli_type.value} with model {static_model} "
                f"for task {task_type} (static)"
            )
            return static_config, static_model

        # Phase 1: Sort by win_rate — batch both queries in one DB round-trip
        perf_rows, recent = memory.get_routing_context(
            task_type, recent_limit=AdaptiveConfig.ANTI_THRASH_WINDOW
        )
        perf_map = {row["cli_name"]: row for row in perf_rows}

        sorted_available = sorted(
            available,
            key=lambda x: (
                -perf_map.get(x[0].value, {}).get("win_rate", 0.0),
                x[1].fallback_priority,
            ),
        )
        current_best_type, current_best_config = sorted_available[0]

        # Anti-thrash guard: >=3 distinct CLIs in last ANTI_THRASH_WINDOW runs -> hold static
        if len(set(recent)) >= AdaptiveConfig.ANTI_THRASH_DISTINCT_LIMIT:
            logger.info(
                f"Anti-thrash: holding static CLI {static_config.cli_type.value} for {task_type}"
            )
            return static_config, static_model

        # Phase 2: Streak correction (need at least STREAK_WINDOW runs)
        if len(recent) >= AdaptiveConfig.STREAK_WINDOW:
            last_n = recent[:AdaptiveConfig.STREAK_WINDOW]

            # Winning streak: all same CLI AND it's the Phase 1 best -> lock it
            if len(set(last_n)) == 1 and last_n[0] == current_best_type.value:
                winner_name = last_n[0]
                for cli_type, config in available:
                    if cli_type.value == winner_name:
                        model = config.models.get(task_type, FALLBACK_MODEL)
                        logger.info(
                            f"Streak lock: {winner_name} for {task_type} "
                            f"({AdaptiveConfig.STREAK_WINDOW} consecutive runs)"
                        )
                        return config, model

            # Losing streak: current_best not in last N runs -> skip to next
            if current_best_type.value not in last_n:
                remaining = [(ct, cfg) for ct, cfg in sorted_available[1:]]
                if remaining:
                    logger.info(
                        f"Streak skip: {current_best_type.value} not in last "
                        f"{AdaptiveConfig.STREAK_WINDOW} runs for {task_type}"
                    )
                    return _select_from(remaining)

        # Phase 3: Win rate override (10+ rated runs, delta >=15pp)
        current_best_perf = perf_map.get(current_best_type.value, {})
        if current_best_perf.get("run_count", 0) >= AdaptiveConfig.MIN_RUNS_BEFORE_OVERRIDE:
            static_perf = perf_map.get(static_config.cli_type.value, {})
            delta = (
                current_best_perf.get("win_rate", 0.0)
                - static_perf.get("win_rate", 0.0)
            )
            if delta >= AdaptiveConfig.WIN_RATE_DELTA_THRESHOLD:
                model = current_best_config.models.get(task_type, FALLBACK_MODEL)
                logger.info(
                    f"[adaptive] {task_type} -> {current_best_type.value} "
                    f"(was {static_config.cli_type.value}) — "
                    f"{current_best_type.value}: {current_best_perf['win_rate']:.0%} win rate "
                    f"vs {static_config.cli_type.value}: {static_perf.get('win_rate', 0.0):.0%} "
                    f"({current_best_perf['run_count']} runs)"
                )
                return current_best_config, model

        # Default: Phase 1 winner
        model = current_best_config.models.get(task_type, FALLBACK_MODEL)
        logger.info(
            f"Selected {current_best_type.value} with model {model} "
            f"for task {task_type} (adaptive phase 1)"
        )
        return current_best_config, model

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


def _reset_router() -> None:
    """Reset the global router instance. Used for testing."""
    global _router
    _router = None


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