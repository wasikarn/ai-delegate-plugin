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
    # Config
    "TASK_DISPLAY_NAMES",
    "TASK_EXPERT_DESCRIPTIONS",
    "TASK_ADJUDICATOR_ROLES",
    "TASK_OUTPUT_FORMATS",
    "DEFAULT_MODELS",
    "EXPERT_CONFIGS",
]