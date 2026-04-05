"""
agent_executor.py — Path B execution via `ollama launch claude` subprocess.

AgentExecutor: runs one expert as a subprocess with file-access tools.
AgentPool: runs N executors in parallel with ThreadPoolExecutor.
"""
from __future__ import annotations

import json
import logging
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ai_delegate.consensus import normalize_finding
from ai_delegate.constants import AgentExecutorDefaults, WorkerConstants
from ai_delegate.models import ExpertResult, Finding

if TYPE_CHECKING:
    from ai_delegate.catalog import AgentMetadata
    from ai_delegate.model_assigner import ExpertAssignment

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutorConfig:
    repo_path: Path
    allowed_tools: list[str] = field(
        default_factory=lambda: list(AgentExecutorDefaults.ALLOWED_TOOLS)
    )
    budget_usd: float = AgentExecutorDefaults.BUDGET_USD
    timeout_sec: int = AgentExecutorDefaults.TIMEOUT_SEC
    effort: str = AgentExecutorDefaults.EFFORT


class AgentExecutor:
    """Run one Path B expert via `ollama launch claude` subprocess."""

    def __init__(self, config: AgentExecutorConfig) -> None:
        self.config = config

    def run(self, assignment: ExpertAssignment, task: str) -> ExpertResult:
        """Run one Path B agent. Returns ExpertResult. Raises RuntimeError on failure."""
        cmd = self._build_cmd(assignment, task)
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_sec,
        )
        if proc.returncode != 0:
            raise RuntimeError(
                f"Agent {assignment.agent.name} failed: {proc.stderr[:200]}"
            )

        result_text = json.loads(proc.stdout)["result"]
        findings = self._parse_findings(result_text, assignment.agent.name)
        return ExpertResult(
            expert_name=assignment.agent.name,
            expert_type=assignment.agent.domains[0] if assignment.agent.domains else "general",
            findings=findings,
        )

    def _build_cmd(self, assignment: ExpertAssignment, task: str) -> list[str]:
        return [
            "ollama", "launch", "claude",
            "--model", assignment.model,
            "--yes", "--",
            "-p", task,
            "--add-dir", str(self.config.repo_path),
            "--output-format", "json",
            "--allowedTools", ",".join(self.config.allowed_tools),
            "--bare",
            "--dangerously-skip-permissions",
            "--system-prompt", self._system_prompt(assignment.agent),
            "--max-budget-usd", str(self.config.budget_usd),
            "--effort", self.config.effort,
        ]

    def _system_prompt(self, agent: AgentMetadata) -> str:
        return (
            f"You are {agent.name}. {agent.description}\n"
            "Respond with valid JSON only — no markdown, no explanation.\n"
            'Format: {"findings": [{"severity": "high|medium|low", '
            '"issue": "...", "recommendation": "..."}]}'
        )

    def _parse_findings(self, result_text: str, agent_name: str) -> list[Finding]:
        """Parse JSON findings from result text. Returns [] on parse failure."""
        try:
            data = json.loads(result_text)
            raw_findings = data.get("findings", [])
            return [normalize_finding(f) for f in raw_findings if isinstance(f, dict)]
        except Exception as e:
            logger.warning("Could not parse findings from %s: %s", agent_name, e)
            return []


class AgentPool:
    """Run N AgentExecutor calls in parallel. Failed agents are skipped."""

    def __init__(
        self,
        executor: AgentExecutor,
        max_workers: int = WorkerConstants.DEFAULT_MAX_WORKERS,
    ) -> None:
        self._executor = executor
        self._max_workers = max_workers

    def run_parallel(
        self,
        assignments: list[ExpertAssignment],
        task: str,
    ) -> list[ExpertResult]:
        """Run all Path B assignments in parallel. Failed agents are skipped (logged)."""
        if not assignments:
            return []

        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {
                pool.submit(self._executor.run, assignment, task): assignment
                for assignment in assignments
            }
            results: list[ExpertResult] = []
            for future in as_completed(futures):
                assignment = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.warning(
                        "Expert %s failed — skipping: %s",
                        assignment.agent.name,
                        e,
                    )
        return results
