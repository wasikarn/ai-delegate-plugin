"""
AI Delegation Framework

Multi-agent adaptive delegation framework with domain expert debate system.
Supports multiple backends: ollama, gemini, codex.
"""

__version__ = "2.1.0"
__author__ = "KoBig"

from .client import AIClient, OllamaClient
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

__all__ = [
    # Clients
    "AIClient",
    "OllamaClient",
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
    # Config
    "TASK_DISPLAY_NAMES",
    "TASK_EXPERT_DESCRIPTIONS",
    "TASK_ADJUDICATOR_ROLES",
    "TASK_OUTPUT_FORMATS",
    "DEFAULT_MODELS",
    "EXPERT_CONFIGS",
]