"""Tests for AgentExecutor and AgentPool (Path B execution)."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ai_delegate.agent_executor import AgentExecutor, AgentExecutorConfig, AgentPool
from ai_delegate.catalog import AgentMetadata
from ai_delegate.model_assigner import ExpertAssignment, ExecutionPath
from ai_delegate.models import ExpertResult


# ─── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture
def config(tmp_path: Path) -> AgentExecutorConfig:
    return AgentExecutorConfig(repo_path=tmp_path)


@pytest.fixture
def agent() -> AgentMetadata:
    return AgentMetadata(
        name="owasp-expert",
        description="OWASP security expert",
        source_plugin="ai-delegate",
        model="kimi-k2.5:cloud",
        tools=["Read", "Grep"],
        path=Path("/fake/agent.md"),
        domains=["security"],
    )


@pytest.fixture
def assignment(agent: AgentMetadata) -> ExpertAssignment:
    return ExpertAssignment(agent=agent, path=ExecutionPath.CLI, model="kimi-k2.5:cloud")


@pytest.fixture
def executor(config: AgentExecutorConfig) -> AgentExecutor:
    return AgentExecutor(config)


def _make_proc(returncode: int = 0, stdout: str = "", stderr: str = "") -> MagicMock:
    proc = MagicMock()
    proc.returncode = returncode
    proc.stdout = stdout
    proc.stderr = stderr
    return proc


# ─── AgentExecutor.run ───────────────────────────────────────────────────────

class TestAgentExecutorRun:
    def test_run_returns_expert_result(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        findings_json = '{"findings": [{"severity": "high", "issue": "SQL injection", "recommendation": "use params"}]}'
        stdout = json.dumps({"result": findings_json})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit src/")
        assert isinstance(result, ExpertResult)
        assert result.expert_name == "owasp-expert"
        assert result.expert_type == "security"
        assert len(result.findings) == 1
        assert result.findings[0].severity == "high"
        assert result.findings[0].issue == "SQL injection"

    def test_run_raises_on_nonzero_returncode(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        with patch("subprocess.run", return_value=_make_proc(returncode=1, stderr="model not found")):
            with pytest.raises(RuntimeError, match="failed"):
                executor.run(assignment, task="audit")

    def test_run_returns_empty_findings_on_parse_failure(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        stdout = json.dumps({"result": "not valid json"})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert result.findings == []

    def test_run_returns_empty_findings_when_no_findings_key(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        stdout = json.dumps({"result": '{"other": "data"}'})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert result.findings == []

    def test_run_skips_non_dict_findings(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        findings_json = '{"findings": ["not a dict", {"severity": "low", "issue": "test", "recommendation": "fix"}]}'
        stdout = json.dumps({"result": findings_json})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert len(result.findings) == 1

    def test_run_uses_agent_name_from_assignment(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        stdout = json.dumps({"result": '{"findings": []}'})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert result.expert_name == assignment.agent.name

    def test_run_uses_first_domain_as_expert_type(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        stdout = json.dumps({"result": '{"findings": []}'})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert result.expert_type == "security"

    def test_run_uses_general_when_no_domains(
        self, executor: AgentExecutor, agent: AgentMetadata, config: AgentExecutorConfig
    ) -> None:
        agent_no_domain = AgentMetadata(
            name="generic",
            description="generic",
            source_plugin="test",
            model="",
            tools=[],
            path=Path("/fake/agent.md"),
            domains=[],
        )
        assignment = ExpertAssignment(agent=agent_no_domain, path=ExecutionPath.CLI, model="kimi")
        stdout = json.dumps({"result": '{"findings": []}'})
        with patch("subprocess.run", return_value=_make_proc(stdout=stdout)):
            result = executor.run(assignment, task="audit")
        assert result.expert_type == "general"


# ─── AgentExecutor._build_cmd ────────────────────────────────────────────────

class TestBuildCmd:
    def test_includes_required_flags(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit src/")
        assert cmd[0] == "ollama"
        assert "--bare" in cmd
        assert "--dangerously-skip-permissions" in cmd
        assert "--output-format" in cmd
        assert "json" in cmd

    def test_includes_model(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert "--model" in cmd
        model_idx = cmd.index("--model")
        assert cmd[model_idx + 1] == "kimi-k2.5:cloud"

    def test_includes_repo_path(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert "--add-dir" in cmd

    def test_includes_budget(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert "--max-budget-usd" in cmd
        budget_idx = cmd.index("--max-budget-usd")
        assert cmd[budget_idx + 1] == "0.2"

    def test_includes_effort(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert "--effort" in cmd
        effort_idx = cmd.index("--effort")
        assert cmd[effort_idx + 1] == "low"

    def test_never_uses_shell(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert isinstance(cmd, list)
        # shell=True would mean cmd is a string, not a list
        assert "shell=True" not in str(cmd)

    def test_allowed_tools_joined(
        self, executor: AgentExecutor, assignment: ExpertAssignment
    ) -> None:
        cmd = executor._build_cmd(assignment, task="audit")
        assert "--allowedTools" in cmd
        tools_idx = cmd.index("--allowedTools")
        tools_str = cmd[tools_idx + 1]
        assert "Read" in tools_str
        assert "Grep" in tools_str
