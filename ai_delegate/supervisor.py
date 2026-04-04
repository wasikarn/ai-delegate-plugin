"""
Supervisor+Worker pattern for distributed AI task execution.

Research insight:
- Supervisor (Sonnet/Opus) for planning and coordination
- Workers (Haiku/GLM/DeepSeek) for execution
- 98% cost reduction for delegated tasks
"""

import logging
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, as_completed

from .router import ComplexityLevel, get_model_for_complexity, CLIType

logger = logging.getLogger(__name__)


class WorkerType(Enum):
    """Worker types for distributed tasks."""
    CODE = "code"          # Code generation/analysis
    SEARCH = "search"      # Documentation search
    REVIEW = "review"      # Code review
    DOCS = "docs"          # Documentation generation
    TEST = "test"          # Test generation


@dataclass
class WorkerConfig:
    """Configuration for a worker."""
    worker_type: WorkerType
    model: str
    cli: CLIType
    max_tokens: int = 4000
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
        model="glm-5:cloud",
        cli=CLIType.OLLAMA,
        max_tokens=4000,
    ),
    WorkerType.SEARCH: WorkerConfig(
        worker_type=WorkerType.SEARCH,
        model="gemini-2.0-flash",
        cli=CLIType.GEMINI,
        max_tokens=2000,
    ),
    WorkerType.REVIEW: WorkerConfig(
        worker_type=WorkerType.REVIEW,
        model="haiku",
        cli=CLIType.CLAUDE,
        max_tokens=3000,
    ),
    WorkerType.DOCS: WorkerConfig(
        worker_type=WorkerType.DOCS,
        model="gemini-2.0-flash",
        cli=CLIType.GEMINI,
        max_tokens=4000,
    ),
    WorkerType.TEST: WorkerConfig(
        worker_type=WorkerType.TEST,
        model="haiku",
        cli=CLIType.CLAUDE,
        max_tokens=3000,
    ),
}

# Budget worker configurations (DeepSeek)
BUDGET_WORKERS = {
    WorkerType.CODE: WorkerConfig(
        worker_type=WorkerType.CODE,
        model="deepseek-chat",
        cli=CLIType.DEEPSEEK,
        max_tokens=4000,
        budget_mode=True,
    ),
    WorkerType.SEARCH: WorkerConfig(
        worker_type=WorkerType.SEARCH,
        model="deepseek-chat",
        cli=CLIType.DEEPSEEK,
        max_tokens=2000,
        budget_mode=True,
    ),
    WorkerType.REVIEW: WorkerConfig(
        worker_type=WorkerType.REVIEW,
        model="deepseek-chat",
        cli=CLIType.DEEPSEEK,
        max_tokens=3000,
        budget_mode=True,
    ),
    WorkerType.DOCS: WorkerConfig(
        worker_type=WorkerType.DOCS,
        model="deepseek-chat",
        cli=CLIType.DEEPSEEK,
        max_tokens=4000,
        budget_mode=True,
    ),
    WorkerType.TEST: WorkerConfig(
        worker_type=WorkerType.TEST,
        model="deepseek-chat",
        cli=CLIType.DEEPSEEK,
        max_tokens=3000,
        budget_mode=True,
    ),
}


class Supervisor:
    """
    Supervisor for coordinating worker tasks.

    Uses Sonnet/Opus for planning, delegates to workers for execution.
    """

    def __init__(
        self,
        model: str = "sonnet",
        cli: CLIType = CLIType.CLAUDE,
        budget_mode: bool = False,
        max_workers: int = 4,
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

    def delegate(
        self,
        task_type: WorkerType,
        task: Callable,
        *args,
        **kwargs
    ) -> TaskResult:
        """
        Delegate a task to a worker.

        Args:
            task_type: Type of worker to use
            task: Task function to execute
            *args: Task arguments
            **kwargs: Task keyword arguments

        Returns:
            TaskResult with execution result
        """
        worker_config = self.workers.get(task_type)
        if not worker_config:
            return TaskResult(
                worker_type=task_type,
                success=False,
                result=None,
                error=f"No worker configured for {task_type}"
            )

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
                    self.delegate,
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
    model: str = "sonnet",
    budget_mode: bool = False,
    max_workers: int = 4
) -> Supervisor:
    """
    Create a supervisor instance.

    Args:
        model: Supervisor model (sonnet/opus)
        budget_mode: Use budget workers (DeepSeek)
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