"""
AI Delegation Framework

Multi-agent adaptive delegation framework with domain expert debate system.
Supports Ollama (GLM/Kimi cloud) with Claude fallback.
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
from .model_assigner import ExecutionPath, ExpertAssignment, ModelAssigner
from .agent_executor import AgentExecutorConfig, AgentExecutor, AgentPool
from .debate.orchestrator import (
    DebateOrchestrator,
    ExpertRunner,
    Adjudicator,
    DebatePhase,
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
    MODEL_INFO,
    ModelSpec,
)
from .model_selector import (
    get_model_for_context,
    get_vision_capable_models,
    get_tools_capable_models,
    get_best_for_coding,
    get_best_for_reasoning,
    get_best_for_long_context,
    get_cheapest_model,
    get_fastest_model,
    supports_vision,
    supports_tools,
    supports_extended_thinking,
    get_model_for_task,
    get_model_info,
    list_models,
    get_context_window,
    get_benchmark,
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
    # Agent Executor (Path B)
    "AgentExecutorConfig",
    "AgentExecutor",
    "AgentPool",
    # Model Assigner
    "ExecutionPath",
    "ExpertAssignment",
    "ModelAssigner",
    # Orchestrator components
    "DebateOrchestrator",
    "ExpertRunner",
    "Adjudicator",
    "DebatePhase",
    # Constants
    "Models",
    "TokenLimits",
    "ComplexityThresholds",
    "QualityThresholds",
    "RetryConfig",
    "CLIPriority",
    "TaskTypes",
    "ExpertDomains",
    "MODEL_INFO",
    "ModelSpec",
    # Model Selector
    "get_model_for_context",
    "get_vision_capable_models",
    "get_tools_capable_models",
    "get_best_for_coding",
    "get_best_for_reasoning",
    "get_best_for_long_context",
    "get_cheapest_model",
    "get_fastest_model",
    "supports_vision",
    "supports_tools",
    "supports_extended_thinking",
    "get_model_for_task",
    "get_model_info",
    "list_models",
    "get_context_window",
    "get_benchmark",
    # Config
    "TASK_DISPLAY_NAMES",
    "TASK_EXPERT_DESCRIPTIONS",
    "TASK_ADJUDICATOR_ROLES",
    "TASK_OUTPUT_FORMATS",
    "DEFAULT_MODELS",
    "EXPERT_CONFIGS",
]