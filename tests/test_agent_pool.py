"""Tests for AgentPool (parallel Path B execution)."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ai_delegate.agent_executor import AgentExecutor, AgentExecutorConfig, AgentPool
from ai_delegate.catalog import AgentMetadata
from ai_delegate.model_assigner import ExpertAssignment, ExecutionPath
from ai_delegate.models import ExpertResult


def _make_agent(name: str = "test-agent") -> AgentMetadata:
    return AgentMetadata(
        name=name,
        description="test",
        source_plugin="test",
        model="kimi-k2.5:cloud",
        tools=["Read"],
        path=Path("/fake/agent.md"),
        domains=["security"],
    )


def _make_assignment(name: str = "test-agent") -> ExpertAssignment:
    return ExpertAssignment(
        agent=_make_agent(name),
        path=ExecutionPath.CLI,
        model="kimi-k2.5:cloud",
    )


def _make_result(name: str) -> ExpertResult:
    return ExpertResult(expert_name=name, expert_type="security", findings=[])


@pytest.fixture
def mock_executor() -> MagicMock:
    return MagicMock(spec=AgentExecutor)


@pytest.fixture
def pool(mock_executor: MagicMock) -> AgentPool:
    return AgentPool(executor=mock_executor, max_workers=2)


class TestAgentPoolRunParallel:
    def test_returns_all_on_success(
        self, pool: AgentPool, mock_executor: MagicMock
    ) -> None:
        assignments = [_make_assignment("a"), _make_assignment("b"), _make_assignment("c")]
        mock_executor.run.side_effect = [
            _make_result("a"),
            _make_result("b"),
            _make_result("c"),
        ]
        results = pool.run_parallel(assignments, task="audit")
        assert len(results) == 3

    def test_skips_failed_agent(
        self, pool: AgentPool, mock_executor: MagicMock
    ) -> None:
        assignments = [_make_assignment("ok"), _make_assignment("fail")]
        mock_executor.run.side_effect = [
            _make_result("ok"),
            RuntimeError("timeout"),
        ]
        results = pool.run_parallel(assignments, task="audit")
        assert len(results) == 1
        assert results[0].expert_name == "ok"

    def test_empty_assignments_returns_empty(self, pool: AgentPool) -> None:
        results = pool.run_parallel([], task="audit")
        assert results == []

    def test_all_fail_returns_empty(
        self, pool: AgentPool, mock_executor: MagicMock
    ) -> None:
        assignments = [_make_assignment("a"), _make_assignment("b")]
        mock_executor.run.side_effect = RuntimeError("all fail")
        results = pool.run_parallel(assignments, task="audit")
        assert results == []

    def test_single_assignment_succeeds(
        self, pool: AgentPool, mock_executor: MagicMock
    ) -> None:
        mock_executor.run.return_value = _make_result("only")
        results = pool.run_parallel([_make_assignment("only")], task="audit")
        assert len(results) == 1
        assert results[0].expert_name == "only"
