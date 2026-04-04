"""
Unit tests for Supervisor+Worker pattern.

Tests behavior, not implementation details.
"""

import pytest
from unittest.mock import Mock, patch
from ai_delegate.supervisor import (
    Supervisor,
    WorkerType,
    WorkerConfig,
    TaskResult,
    create_supervisor,
    DEFAULT_WORKERS,
    BUDGET_WORKERS,
)


class TestWorkerType:
    """Tests for WorkerType enum."""

    def test_all_worker_types_defined(self):
        """All worker types should be defined."""
        types = list(WorkerType)
        assert len(types) == 5
        assert WorkerType.CODE in types
        assert WorkerType.SEARCH in types
        assert WorkerType.REVIEW in types
        assert WorkerType.DOCS in types
        assert WorkerType.TEST in types

    def test_worker_type_values(self):
        """Worker type values should be lowercase."""
        assert WorkerType.CODE.value == "code"
        assert WorkerType.SEARCH.value == "search"
        assert WorkerType.REVIEW.value == "review"
        assert WorkerType.DOCS.value == "docs"
        assert WorkerType.TEST.value == "test"


class TestWorkerConfig:
    """Tests for WorkerConfig dataclass."""

    def test_worker_config_creation(self):
        """WorkerConfig should be created with all fields."""
        config = WorkerConfig(
            worker_type=WorkerType.CODE,
            model="haiku",
            cli="claude",  # type: ignore
            max_tokens=4000,
            budget_mode=False,
        )
        assert config.worker_type == WorkerType.CODE
        assert config.model == "haiku"
        assert config.max_tokens == 4000

    def test_worker_config_defaults(self):
        """WorkerConfig should have default max_tokens."""
        config = WorkerConfig(
            worker_type=WorkerType.CODE,
            model="haiku",
            cli="claude",  # type: ignore
        )
        assert config.max_tokens == 4000
        assert config.budget_mode == False


class TestTaskResult:
    """Tests for TaskResult dataclass."""

    def test_success_result(self):
        """TaskResult should store success result."""
        result = TaskResult(
            worker_type=WorkerType.CODE,
            success=True,
            result={"findings": ["issue1"]},
        )
        assert result.success == True
        assert result.result == {"findings": ["issue1"]}
        assert result.error is None

    def test_failure_result(self):
        """TaskResult should store error."""
        result = TaskResult(
            worker_type=WorkerType.CODE,
            success=False,
            result=None,
            error="Task failed",
        )
        assert result.success == False
        assert result.result is None
        assert result.error == "Task failed"


class TestSupervisor:
    """Tests for Supervisor class."""

    def test_supervisor_creation(self):
        """Supervisor should be created with defaults."""
        supervisor = Supervisor()
        assert supervisor.model == "sonnet"
        assert supervisor.cli == "claude"  # type: ignore
        assert supervisor.budget_mode == False
        assert supervisor.max_workers == 4

    def test_supervisor_custom_params(self):
        """Supervisor should accept custom parameters."""
        supervisor = Supervisor(
            model="opus",
            cli="claude",  # type: ignore
            budget_mode=True,
            max_workers=8,
        )
        assert supervisor.model == "opus"
        assert supervisor.budget_mode == True
        assert supervisor.max_workers == 8

    def test_supervisor_budget_mode_uses_budget_workers(self):
        """Budget mode should use budget workers."""
        supervisor = Supervisor(budget_mode=True)
        assert supervisor.workers == BUDGET_WORKERS

    def test_supervisor_default_mode_uses_default_workers(self):
        """Default mode should use default workers."""
        supervisor = Supervisor(budget_mode=False)
        assert supervisor.workers == DEFAULT_WORKERS

    def test_get_worker_config(self):
        """get_worker_config should return correct config."""
        supervisor = Supervisor()
        config = supervisor.get_worker_config(WorkerType.CODE)
        assert config.worker_type == WorkerType.CODE
        assert config.model == "glm-5:cloud"

    def test_get_worker_config_budget_mode(self):
        """Budget mode should return budget config."""
        supervisor = Supervisor(budget_mode=True)
        config = supervisor.get_worker_config(WorkerType.CODE)
        assert config.budget_mode == True
        assert config.model == "deepseek-chat"

    def test_delegate_success(self):
        """delegate should execute task and return result."""
        supervisor = Supervisor()
        task = Mock(return_value={"result": "success"})

        result = supervisor.delegate(WorkerType.CODE, task, "arg1", key="value")

        assert result.success == True
        assert result.result == {"result": "success"}
        task.assert_called_once_with("arg1", key="value")

    def test_delegate_failure(self):
        """delegate should catch exceptions."""
        supervisor = Supervisor()
        task = Mock(side_effect=ValueError("Task error"))

        result = supervisor.delegate(WorkerType.CODE, task)

        assert result.success == False
        assert result.error == "Task error"

    def test_delegate_unknown_worker_type(self):
        """delegate should handle unknown worker type."""
        supervisor = Supervisor()
        task = Mock()

        # Create an invalid worker type scenario
        result = supervisor.delegate("unknown", task)  # type: ignore

        assert result.success == False
        assert "No worker configured" in result.error  # type: ignore

    def test_delegate_parallel(self):
        """delegate_parallel should run tasks in parallel."""
        supervisor = Supervisor(max_workers=4)
        results = []

        def task1():
            results.append("task1")
            return "result1"

        def task2():
            results.append("task2")
            return "result2"

        tasks = [
            {"task_type": WorkerType.CODE, "task": task1},
            {"task_type": WorkerType.REVIEW, "task": task2},
        ]

        results_list = supervisor.delegate_parallel(tasks)

        assert len(results_list) == 2
        assert all(r.success for r in results_list)

    def test_delegate_parallel_with_args(self):
        """delegate_parallel should pass args and kwargs."""
        supervisor = Supervisor()
        task = Mock(return_value="done")

        tasks = [
            {
                "task_type": WorkerType.CODE,
                "task": task,
                "args": ("arg1", "arg2"),
                "kwargs": {"key": "value"},
            }
        ]

        results = supervisor.delegate_parallel(tasks)

        assert len(results) == 1
        assert results[0].success == True
        task.assert_called_once_with("arg1", "arg2", key="value")


class TestCreateSupervisor:
    """Tests for create_supervisor factory function."""

    def test_create_supervisor_defaults(self):
        """create_supervisor should use defaults."""
        supervisor = create_supervisor()
        assert supervisor.model == "sonnet"
        assert supervisor.budget_mode == False
        assert supervisor.max_workers == 4

    def test_create_supervisor_custom_params(self):
        """create_supervisor should accept custom params."""
        supervisor = create_supervisor(
            model="opus",
            budget_mode=True,
            max_workers=8,
        )
        assert supervisor.model == "opus"
        assert supervisor.budget_mode == True
        assert supervisor.max_workers == 8


class TestDefaultWorkers:
    """Tests for DEFAULT_WORKERS configuration."""

    def test_all_worker_types_have_config(self):
        """All worker types should have default config."""
        for worker_type in WorkerType:
            assert worker_type in DEFAULT_WORKERS

    def test_default_models_are_cost_effective(self):
        """Default workers should use cost-effective models."""
        assert DEFAULT_WORKERS[WorkerType.CODE].model == "glm-5:cloud"
        assert DEFAULT_WORKERS[WorkerType.REVIEW].model == "haiku"
        assert DEFAULT_WORKERS[WorkerType.SEARCH].model == "gemini-2.0-flash"


class TestBudgetWorkers:
    """Tests for BUDGET_WORKERS configuration."""

    def test_all_worker_types_have_budget_config(self):
        """All worker types should have budget config."""
        for worker_type in WorkerType:
            assert worker_type in BUDGET_WORKERS

    def test_budget_models_are_deepseek(self):
        """Budget workers should use DeepSeek models."""
        for worker_type in WorkerType:
            config = BUDGET_WORKERS[worker_type]
            assert "deepseek" in config.model
            assert config.budget_mode == True