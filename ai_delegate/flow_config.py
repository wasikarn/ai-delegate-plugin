"""Workflow mode configuration for ai-delegate analysis flows."""

from dataclasses import dataclass
from typing import Optional


class FlowMode:
    """Predefined workflow mode names."""
    QUICK = "quick"
    STANDARD = "standard"
    BMAD = "bmad"
    ENTERPRISE = "enterprise"

    ALL = [QUICK, STANDARD, BMAD, ENTERPRISE]


@dataclass
class FlowConfig:
    """Configuration for a workflow mode."""
    mode: str
    tier: str
    elicit: Optional[str]
    debate_rounds: int
    description: str

    @classmethod
    def from_mode(cls, mode: str) -> "FlowConfig":
        """Create FlowConfig from a named mode."""
        configs = {
            FlowMode.QUICK: cls(
                mode=FlowMode.QUICK,
                tier="fast",
                elicit=None,
                debate_rounds=0,
                description="Consensus-only, no debate (fastest)",
            ),
            FlowMode.STANDARD: cls(
                mode=FlowMode.STANDARD,
                tier="standard",
                elicit=None,
                debate_rounds=1,
                description="Debate + adjudication (default quality)",
            ),
            FlowMode.BMAD: cls(
                mode=FlowMode.BMAD,
                tier="deep",
                elicit="all",
                debate_rounds=2,
                description="Full BMAD elicitation + deep debate",
            ),
            FlowMode.ENTERPRISE: cls(
                mode=FlowMode.ENTERPRISE,
                tier="deep",
                elicit="red-team",
                debate_rounds=3,
                description="Red-team elicitation + maximum debate rounds",
            ),
        }
        if mode not in configs:
            raise ValueError(
                f"Unknown flow mode: {mode}. Valid: {', '.join(FlowMode.ALL)}"
            )
        return configs[mode]
