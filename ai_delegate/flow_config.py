"""Workflow mode configuration for ai-delegate."""
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class FlowMode(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    BMAD = "bmad"
    ENTERPRISE = "enterprise"

    ALL = "all"  # not a real mode, kept for back-compat

    @classmethod
    def values(cls) -> list:
        return [m.value for m in cls if m != cls.ALL]


@dataclass
class FlowConfig:
    mode: FlowMode
    max_experts: Optional[int] = None
    force_tier: Optional[str] = None
    elicitation_enabled: bool = False
    party_mode_enabled: bool = False
    checkpoint_enabled: bool = False

    @classmethod
    def default(cls) -> "FlowConfig":
        return cls(mode=FlowMode.STANDARD)

    @classmethod
    def from_mode(cls, mode: str) -> "FlowConfig":
        if mode == FlowMode.QUICK or mode == "quick":
            return cls(
                mode=FlowMode.QUICK,
                max_experts=2,
                force_tier="fast",
                elicitation_enabled=False,
                party_mode_enabled=False,
                checkpoint_enabled=False,
            )
        elif mode == FlowMode.STANDARD or mode == "standard":
            return cls.default()
        elif mode == FlowMode.BMAD or mode == "bmad":
            return cls(
                mode=FlowMode.BMAD,
                max_experts=None,
                force_tier=None,
                elicitation_enabled=True,
                party_mode_enabled=True,
                checkpoint_enabled=True,
            )
        elif mode == FlowMode.ENTERPRISE or mode == "enterprise":
            return cls(
                mode=FlowMode.ENTERPRISE,
                max_experts=None,
                force_tier="deep",
                elicitation_enabled=True,
                party_mode_enabled=True,
                checkpoint_enabled=True,
            )
        else:
            valid = ", ".join(FlowMode.values())
            raise ValueError(f"Unknown flow mode: {mode}. Valid: {valid}")

    def limit_experts(self, experts: Dict[str, str]) -> Dict[str, str]:
        """Limit expert count based on flow config."""
        if self.max_experts is None:
            return experts
        return dict(list(experts.items())[: self.max_experts])

    # Derived properties for backward-compat with CLI that uses tier/elicit
    @property
    def tier(self) -> str:
        return self.force_tier or "auto"

    @property
    def elicit(self) -> Optional[str]:
        if not self.elicitation_enabled:
            return None
        return "all" if self.mode == FlowMode.BMAD else "red-team"
