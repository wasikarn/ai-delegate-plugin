"""
model_assigner.py — Route each expert to Path A, B, or C based on tool requirements
and content complexity.

ExecutionPath: enum for the three execution paths.
ExpertAssignment: agent + resolved path + resolved model.
ModelAssigner: stateless routing logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from ai_delegate.catalog import AgentMetadata
from ai_delegate.complexity import ComplexityScore
from ai_delegate.constants import Models

FILE_ACCESS_TOOLS = frozenset({"Read", "Glob", "Grep", "Bash"})
DEEP_DOMAINS = frozenset({"architecture", "migration"})


class ExecutionPath(str, Enum):
    SDK = "sdk"      # Path A — Anthropic SDK → localhost:11434, no tools
    CLI = "cli"      # Path B — ollama launch claude subprocess, file tools
    AGENT = "agent"  # Path C — Claude Code Agent tool (Sonnet), all tools


@dataclass
class ExpertAssignment:
    agent: AgentMetadata
    path: ExecutionPath
    model: str  # resolved model name, after overrides applied


class ModelAssigner:
    """Route agents to Path A/B/C. All methods are stateless."""

    @staticmethod
    def assign(
        agent: AgentMetadata,
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> ExpertAssignment:
        """Assign a single agent to the correct execution path.

        Routing rules:
        - No file-access tools → Path A (SDK)
        - File tools + (deep domain OR high complexity) → Path C (Agent/Sonnet)
        - File tools + standard domain + low/medium complexity → Path B (CLI/kimi)
        """
        overrides = model_overrides or {}
        needs_file_access = bool(set(agent.tools) & FILE_ACCESS_TOOLS)
        needs_deep = bool(set(agent.domains) & DEEP_DOMAINS)
        is_complex = complexity.level == "high"

        if not needs_file_access:
            path = ExecutionPath.SDK
            default_model = agent.model or Models.KIMI_K25_CLOUD
        elif needs_deep or is_complex:
            path = ExecutionPath.AGENT
            default_model = agent.model or Models.CLAUDE_SONNET
        else:
            path = ExecutionPath.CLI
            default_model = agent.model or Models.KIMI_K25_CLOUD

        return ExpertAssignment(
            agent=agent,
            path=path,
            model=overrides.get(agent.name, default_model),
        )

    @staticmethod
    def assign_all(
        agents: list[AgentMetadata],
        complexity: ComplexityScore,
        model_overrides: dict[str, str] | None = None,
    ) -> list[ExpertAssignment]:
        """Assign all agents. Preserves input order."""
        return [ModelAssigner.assign(a, complexity, model_overrides) for a in agents]
