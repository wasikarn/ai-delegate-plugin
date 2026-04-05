"""Tests for ModelAssigner — routing agents to Path A/B/C."""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_delegate.catalog import AgentMetadata
from ai_delegate.complexity import ComplexityScore
from ai_delegate.model_assigner import ExecutionPath, ExpertAssignment, ModelAssigner


def _agent(
    name: str = "test",
    tools: list[str] | None = None,
    domains: list[str] | None = None,
    model: str = "",
) -> AgentMetadata:
    return AgentMetadata(
        name=name,
        description="test agent",
        source_plugin="test",
        model=model,
        tools=tools or [],
        path=Path("/fake/agent.md"),
        domains=domains or [],
    )


def _score(level: str = "medium", domains: list[str] | None = None) -> ComplexityScore:
    return ComplexityScore(level=level, domains=domains or [])


class TestModelAssignerAssign:
    def test_no_file_tools_routes_to_sdk(self) -> None:
        assignment = ModelAssigner.assign(_agent(tools=[]), _score("high"))
        assert assignment.path == ExecutionPath.SDK

    def test_no_tools_at_all_routes_to_sdk(self) -> None:
        assignment = ModelAssigner.assign(_agent(tools=[]), _score("low"))
        assert assignment.path == ExecutionPath.SDK

    def test_file_tools_medium_complexity_routes_to_cli(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Read", "Grep"], domains=["security"]),
            _score("medium"),
        )
        assert assignment.path == ExecutionPath.CLI

    def test_file_tools_low_complexity_routes_to_cli(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Read"], domains=["security"]),
            _score("low"),
        )
        assert assignment.path == ExecutionPath.CLI

    def test_deep_domain_architecture_routes_to_agent(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Read"], domains=["architecture"]),
            _score("low"),
        )
        assert assignment.path == ExecutionPath.AGENT

    def test_deep_domain_migration_routes_to_agent(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Read"], domains=["migration"]),
            _score("medium"),
        )
        assert assignment.path == ExecutionPath.AGENT

    def test_high_complexity_with_file_tools_routes_to_agent(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Read"], domains=["security"]),
            _score("high"),
        )
        assert assignment.path == ExecutionPath.AGENT

    def test_bash_tool_counts_as_file_access(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Bash"], domains=["security"]),
            _score("low"),
        )
        assert assignment.path == ExecutionPath.CLI

    def test_glob_tool_counts_as_file_access(self) -> None:
        assignment = ModelAssigner.assign(
            _agent(tools=["Glob"], domains=["security"]),
            _score("low"),
        )
        assert assignment.path == ExecutionPath.CLI


class TestModelAssignerModel:
    def test_model_override_applied(self) -> None:
        agent = _agent(name="owasp-expert", tools=["Read"], domains=["security"])
        assignment = ModelAssigner.assign(
            agent,
            _score("medium"),
            model_overrides={"owasp-expert": "claude-sonnet-4-6"},
        )
        assert assignment.model == "claude-sonnet-4-6"

    def test_model_override_not_applied_for_different_agent(self) -> None:
        agent = _agent(name="auth-expert", tools=["Read"], domains=["security"])
        assignment = ModelAssigner.assign(
            agent,
            _score("medium"),
            model_overrides={"owasp-expert": "claude-sonnet-4-6"},
        )
        assert assignment.model != "claude-sonnet-4-6"

    def test_agent_model_used_as_default(self) -> None:
        agent = _agent(name="custom", tools=[], model="my-custom-model")
        assignment = ModelAssigner.assign(agent, _score("low"))
        assert assignment.model == "my-custom-model"

    def test_fallback_to_kimi_for_sdk_path(self) -> None:
        agent = _agent(tools=[], model="")
        assignment = ModelAssigner.assign(agent, _score("low"))
        assert assignment.path == ExecutionPath.SDK
        assert assignment.model == "kimi-k2.5:cloud"

    def test_fallback_to_sonnet_for_agent_path(self) -> None:
        agent = _agent(tools=["Read"], domains=["architecture"], model="")
        assignment = ModelAssigner.assign(agent, _score("low"))
        assert assignment.path == ExecutionPath.AGENT
        assert assignment.model == "sonnet"

    def test_fallback_to_kimi_for_cli_path(self) -> None:
        agent = _agent(tools=["Read"], domains=["security"], model="")
        assignment = ModelAssigner.assign(agent, _score("medium"))
        assert assignment.path == ExecutionPath.CLI
        assert assignment.model == "kimi-k2.5:cloud"


class TestModelAssignerAssignAll:
    def test_preserves_input_order(self) -> None:
        agents = [
            _agent("a", tools=[]),
            _agent("b", tools=["Read"], domains=["security"]),
            _agent("c", tools=["Read"], domains=["architecture"]),
        ]
        assignments = ModelAssigner.assign_all(agents, _score("medium"))
        assert [a.agent.name for a in assignments] == ["a", "b", "c"]

    def test_empty_agents_returns_empty(self) -> None:
        assert ModelAssigner.assign_all([], _score("low")) == []

    def test_routes_each_agent_independently(self) -> None:
        agents = [
            _agent("sdk-agent", tools=[]),
            _agent("cli-agent", tools=["Read"], domains=["security"]),
        ]
        assignments = ModelAssigner.assign_all(agents, _score("medium"))
        assert assignments[0].path == ExecutionPath.SDK
        assert assignments[1].path == ExecutionPath.CLI


class TestExpertAssignment:
    def test_dataclass_fields(self) -> None:
        agent = _agent("test", tools=["Read"], domains=["security"])
        assignment = ExpertAssignment(
            agent=agent,
            path=ExecutionPath.CLI,
            model="kimi-k2.5:cloud",
        )
        assert assignment.agent is agent
        assert assignment.path == ExecutionPath.CLI
        assert assignment.model == "kimi-k2.5:cloud"


class TestExecutionPath:
    def test_string_values(self) -> None:
        assert ExecutionPath.SDK == "sdk"
        assert ExecutionPath.CLI == "cli"
        assert ExecutionPath.AGENT == "agent"
