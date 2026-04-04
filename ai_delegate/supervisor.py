"""
Supervisor+Worker pattern for distributed AI task execution.

Research insight:
- Supervisor (Sonnet/Opus) for planning and coordination
- Workers (Haiku/GLM/Kimi) for execution
- 98% cost reduction for delegated tasks
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from .router import ComplexityLevel, CLIType
from .constants import (
    Models,
    TokenLimits,
    TaskTypes,
    WorkerConstants,
)

logger = logging.getLogger(__name__)


class WorkerType(Enum):
    """Worker types for distributed tasks."""
    CODE = "code"
    SEARCH = "search"
    REVIEW = "review"
    DOCS = "docs"
    TEST = "test"


@dataclass
class WorkerConfig:
    """Configuration for a worker."""
    worker_type: WorkerType
    model: str
    cli: CLIType
    max_tokens: int = TokenLimits.CODE_MAX_TOKENS
    budget_mode: bool = False


@dataclass
class TaskResult:
    """Result from a worker task."""
    worker_type: WorkerType
    success: bool
    result: Any
    error: Optional[str] = None
    tokens_used: int = 0


# Default worker configurations
DEFAULT_WORKERS = {
    WorkerType.CODE: WorkerConfig(
        worker_type=WorkerType.CODE,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.CODE_MAX_TOKENS,
    ),
    WorkerType.SEARCH: WorkerConfig(
        worker_type=WorkerType.SEARCH,
        model=Models.GEMINI_20_FLASH,
        cli=CLIType.GEMINI,
        max_tokens=TokenLimits.SEARCH_MAX_TOKENS,
    ),
    WorkerType.REVIEW: WorkerConfig(
        worker_type=WorkerType.REVIEW,
        model=Models.CLAUDE_HAIKU,
        cli=CLIType.CLAUDE,
        max_tokens=TokenLimits.REVIEW_MAX_TOKENS,
    ),
    WorkerType.DOCS: WorkerConfig(
        worker_type=WorkerType.DOCS,
        model=Models.GEMINI_20_FLASH,
        cli=CLIType.GEMINI,
        max_tokens=TokenLimits.DOCS_MAX_TOKENS,
    ),
    WorkerType.TEST: WorkerConfig(
        worker_type=WorkerType.TEST,
        model=Models.CLAUDE_HAIKU,
        cli=CLIType.CLAUDE,
        max_tokens=TokenLimits.TEST_MAX_TOKENS,
    ),
}

# Budget worker configurations (GLM via Ollama)
BUDGET_WORKERS = {
    WorkerType.CODE: WorkerConfig(
        worker_type=WorkerType.CODE,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.CODE_MAX_TOKENS,
        budget_mode=True,
    ),
    WorkerType.SEARCH: WorkerConfig(
        worker_type=WorkerType.SEARCH,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.SEARCH_MAX_TOKENS,
        budget_mode=True,
    ),
    WorkerType.REVIEW: WorkerConfig(
        worker_type=WorkerType.REVIEW,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.REVIEW_MAX_TOKENS,
        budget_mode=True,
    ),
    WorkerType.DOCS: WorkerConfig(
        worker_type=WorkerType.DOCS,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.DOCS_MAX_TOKENS,
        budget_mode=True,
    ),
    WorkerType.TEST: WorkerConfig(
        worker_type=WorkerType.TEST,
        model=Models.GLM_5_CLOUD,
        cli=CLIType.OLLAMA,
        max_tokens=TokenLimits.TEST_MAX_TOKENS,
        budget_mode=True,
    ),
}


class Supervisor:
    """
    Supervisor for coordinating worker tasks.
    """

    def __init__(
        self,
        model: str = Models.CLAUDE_SONNET,
        cli: CLIType = CLIType.CLAUDE,
        budget_mode: bool = False,
        max_workers: int = WorkerConstants.DEFAULT_MAX_WORKERS,
    ):
        """
        Initialize supervisor.

        Args:
            model: Supervisor model (sonnet/opus)
            cli: Supervisor CLI
            budget_mode: Use budget workers
            max_workers: Maximum parallel workers
        """
        self.model = model
        self.cli = cli
        self.budget_mode = budget_mode
        self.max_workers = max_workers
        self.workers = BUDGET_WORKERS if budget_mode else DEFAULT_WORKERS

    def execute_task(
        self,
        task_type: WorkerType,
        task: Callable,
        *args,
        **kwargs
    ) -> TaskResult:
        """
        Execute a task and wrap exceptions in TaskResult.

        No AI routing is performed — the callable is responsible for its own
        model/CLI selection. Use get_worker_config(task_type) to retrieve
        the reference config if needed.

        Args:
            task_type: Worker type (used for result metadata and logging only)
            task: Callable to execute
            *args: Positional arguments forwarded to task
            **kwargs: Keyword arguments forwarded to task

        Returns:
            TaskResult with execution result or error
        """
        try:
            result = task(*args, **kwargs)
            return TaskResult(
                worker_type=task_type,
                success=True,
                result=result
            )
        except Exception as e:
            logger.error(f"Worker {task_type} failed: {e}")
            return TaskResult(
                worker_type=task_type,
                success=False,
                result=None,
                error=str(e)
            )

    def delegate_parallel(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[TaskResult]:
        """
        Delegate multiple tasks in parallel.

        Args:
            tasks: List of {task_type, task, args, kwargs} dicts

        Returns:
            List of TaskResults
        """
        results = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            for task_info in tasks:
                task_type = task_info["task_type"]
                task = task_info["task"]
                args = task_info.get("args", ())
                kwargs = task_info.get("kwargs", {})

                future = executor.submit(
                    self.execute_task,
                    task_type,
                    task,
                    *args,
                    **kwargs
                )
                futures[future] = task_type

            for future in as_completed(futures):
                result = future.result()
                results.append(result)

        return results

    def get_worker_config(self, task_type: WorkerType) -> WorkerConfig:
        """Get worker configuration for a task type."""
        return self.workers.get(task_type, DEFAULT_WORKERS[WorkerType.CODE])


def create_supervisor(
    model: str = Models.CLAUDE_SONNET,
    budget_mode: bool = False,
    max_workers: int = WorkerConstants.DEFAULT_MAX_WORKERS
) -> Supervisor:
    """
    Create a supervisor instance.

    Args:
        model: Supervisor model (sonnet/opus)
        budget_mode: Use budget workers (GLM/Kimi)
        max_workers: Maximum parallel workers

    Returns:
        Supervisor instance
    """
    return Supervisor(
        model=model,
        cli=CLIType.CLAUDE,
        budget_mode=budget_mode,
        max_workers=max_workers
    )