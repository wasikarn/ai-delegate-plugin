"""Token usage and cost tracking for analysis runs."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


# Cost per 1M tokens (USD)
# Note: Ollama Cloud uses subscription model ($0/20/100/mo), not per-token billing.
# Costs below are for Claude models only. Ollama cloud models have $0 cost.
TOKEN_COSTS: Dict[str, Dict[str, float]] = {
    # Ollama Cloud models (subscription-based, no per-token cost)
    "glm-5:cloud": {"input": 0.0, "output": 0.0},
    "kimi-k2.5:cloud": {"input": 0.0, "output": 0.0},
    "gemma4:31b-cloud": {"input": 0.0, "output": 0.0},
    # Claude models (actual per-token pricing)
    "claude-haiku": {"input": 0.25, "output": 1.25},
    "claude-sonnet": {"input": 3.0, "output": 15.0},
    # Default fallback
    "default": {"input": 0.0, "output": 0.0},
}


@dataclass
class TokenUsage:
    """Token usage for a single LLM call."""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    expert_name: str = ""

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def cost_usd(self) -> float:
        rates = TOKEN_COSTS.get(self.model, TOKEN_COSTS["default"])
        return (
            self.input_tokens * rates["input"] / 1_000_000
            + self.output_tokens * rates["output"] / 1_000_000
        )


@dataclass
class CostReport:
    """Aggregated cost report for an analysis run."""
    usages: List[TokenUsage] = field(default_factory=list)

    @property
    def total_input_tokens(self) -> int:
        return sum(u.input_tokens for u in self.usages)

    @property
    def total_output_tokens(self) -> int:
        return sum(u.output_tokens for u in self.usages)

    @property
    def total_tokens(self) -> int:
        return self.total_input_tokens + self.total_output_tokens

    @property
    def total_cost_usd(self) -> float:
        return sum(u.cost_usd for u in self.usages)

    def to_dict(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "per_expert": [
                {
                    "expert": u.expert_name or u.model,
                    "model": u.model,
                    "input_tokens": u.input_tokens,
                    "output_tokens": u.output_tokens,
                    "cost_usd": round(u.cost_usd, 6),
                }
                for u in self.usages
            ],
        }

    def format_summary(self) -> str:
        lines = [
            "## Cost Report",
            f"  Total tokens:  {self.total_tokens:,} ({self.total_input_tokens:,} in / {self.total_output_tokens:,} out)",
            f"  Estimated cost: ${self.total_cost_usd:.4f} USD",
            "",
            "  Per expert:",
        ]
        for u in self.usages:
            label = u.expert_name or u.model
            lines.append(f"    {label:<20} {u.total_tokens:>6,} tokens  ${u.cost_usd:.4f}")
        return "\n".join(lines)


class CostTracker:
    """Thread-safe accumulator for token usage across expert calls."""

    def __init__(self) -> None:
        self._usages: List[TokenUsage] = []

    def record(self, usage: TokenUsage) -> None:
        self._usages.append(usage)

    def report(self) -> CostReport:
        return CostReport(usages=list(self._usages))

    def estimate_from_content(self, content: str, model: str, expert_name: str = "") -> TokenUsage:
        """Rough token estimate from character count (4 chars ≈ 1 token)."""
        estimated_input = len(content) // 4
        estimated_output = estimated_input // 3
        return TokenUsage(
            model=model,
            input_tokens=estimated_input,
            output_tokens=estimated_output,
            expert_name=expert_name,
        )
