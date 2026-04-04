"""
AI Delegation Framework

Multi-agent adaptive delegation framework with domain expert debate system.
Supports multiple backends: ollama, gemini, codex.
"""

__version__ = "0.3.0"
__author__ = "KoBig"

from .client import AIClient, BackendClient
from .config import (
    TASK_DISPLAY_NAMES,
    TASK_EXPERT_DESCRIPTIONS,
    TASK_ADJUDICATOR_ROLES,
    TASK_OUTPUT_FORMATS,
    DEFAULT_MODELS,
    EXPERT_CONFIGS,
)
from .models import Finding, Verdict, ExpertResult, ConsensusResult, TaskConfig, Tier
from .debate.orchestrator import (
    DebateOrchestrator,
    ConsensusCalculator,
    ExpertRunner,
    Adjudicator,
    DebatePhase,
)
from .router import (
    SmartRouter,
    CLIType,
    ComplexityLevel,
    detect_complexity,
    get_model_for_complexity,
    get_router,
    select_cli_and_model,
)
from .supervisor import (
    Supervisor,
    WorkerType,
    WorkerConfig,
    TaskResult,
    create_supervisor,
)
from .constants import (
    Models,
    TokenLimits,
    ComplexityThresholds,
    QualityThresholds,
    RetryConfig,
    CLIPriority,
    TaskTypes,
    ExpertDomains,
)

__all__ = [
    # Clients
    "AIClient",
    "BackendClient",
    # Models
    "Finding",
    "Verdict",
    "ExpertResult",
    "ConsensusResult",
    "TaskConfig",
    "Tier",
    # Orchestrator components
    "DebateOrchestrator",
    "ConsensusCalculator",
    "ExpertRunner",
    "Adjudicator",
    "DebatePhase",
    # Router
    "SmartRouter",
    "CLIType",
    "ComplexityLevel",
    "detect_complexity",
    "get_model_for_complexity",
    "get_router",
    "select_cli_and_model",
    # Supervisor
    "Supervisor",
    "WorkerType",
    "WorkerConfig",
    "TaskResult",
    "create_supervisor",
    # Constants
    "Models",
    "TokenLimits",
    "ComplexityThresholds",
    "QualityThresholds",
    "RetryConfig",
    "CLIPriority",
    "TaskTypes",
    "ExpertDomains",
    # Config
    "TASK_DISPLAY_NAMES",
    "TASK_EXPERT_DESCRIPTIONS",
    "TASK_ADJUDICATOR_ROLES",
    "TASK_OUTPUT_FORMATS",
    "DEFAULT_MODELS",
    "EXPERT_CONFIGS",
]