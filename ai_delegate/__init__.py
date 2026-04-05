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
from .consensus import ConsensusCalculator, normalize_finding
from .complexity import ComplexityAssessor, ComplexityScore
from .catalog import AgentCatalog, AgentMetadata, DOMAIN_KEYWORDS
from .debate_runner import DisputedFindingsBundle, DebateResult
from .debate.orchestrator import (
    DebateOrchestrator,
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
    # Consensus
    "ConsensusCalculator",
    "normalize_finding",
    # Complexity
    "ComplexityAssessor",
    "ComplexityScore",
    # Catalog
    "AgentCatalog",
    "AgentMetadata",
    "DOMAIN_KEYWORDS",
    # Debate Runner (Path D)
    "DisputedFindingsBundle",
    "DebateResult",
    # Orchestrator components
    "DebateOrchestrator",
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