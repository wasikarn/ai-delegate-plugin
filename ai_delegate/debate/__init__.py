"""
Debate module for multi-expert analysis.
"""

from .orchestrator import (
    DebateOrchestrator,
    ConsensusCalculator,
    ExpertRunner,
    Adjudicator,
    DebatePhase,
)

__all__ = [
    "DebateOrchestrator",
    "ConsensusCalculator",
    "ExpertRunner",
    "Adjudicator",
    "DebatePhase",
]