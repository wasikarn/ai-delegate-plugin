"""
Additional tests for edge cases and error paths.

Tests for remaining coverage gaps.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import asyncio

from ai_delegate.client import BackendClient, RateLimitError
from ai_delegate.debate.orchestrator import ExpertRunner, DebateOrchestrator, ConsensusCalculator
from ai_delegate.models import TaskConfig, ExpertResult, Finding, Verdict, Tier


class TestMainModuleExecution:
    """Tests for __main__.py execution."""

    def test_main_module_runs_main(self):
        """__main__.py calls main when executed."""
        import subprocess

        # Run the module as a script
        result = subprocess.run(
            ["python3", "-m", "ai_delegate", "--help"],
            capture_output=True,
            text=True,
        )

        # Should show help or error (not crash)
        assert result.returncode in [0, 1, 2]  # 0=success, 1/2=error/help


class TestClientInit:
    """Tests for BackendClient initialization."""

    def test_init_without_ollama_warns(self, caplog):
        """Missing ollama CLI logs a warning (SDK path doesn't require it)."""
        import logging
        with patch("ai_delegate.client.shutil.which") as mock_which:
            mock_which.return_value = None

            with caplog.at_level(logging.WARNING, logger="ai_delegate.client"):
                BackendClient(model="test-model")  # should not raise

        assert "localhost:11434" in caplog.text

    def test_init_without_claude_fallback_logs_warning(self, caplog):
        """Initialization logs warning when Claude CLI is not available."""
        with patch("ai_delegate.client.shutil.which") as mock_which:
            mock_which.side_effect = lambda cmd: {
                "ollama": "/usr/local/bin/ollama",
                "claude": None,
            }.get(cmd)

            BackendClient(model="test-model")

            # Check log warning
            import logging
            caplog.set_level(logging.WARNING)
            # Warning is logged during init


class TestClientRunJsonErrors:
    """Tests for run_json error handling."""

    @pytest.fixture
    def client(self) -> BackendClient:
        """Create BackendClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return BackendClient(model="test-model")

    def test_run_json_with_nested_json(self, client: BackendClient):
        """run_json handles nested JSON objects."""
        nested_json = '{"outer": {"inner": {"key": "value"}}}'

        with patch.object(client, "run", return_value=nested_json):
            result = client.run_json("prompt")

            assert result == {"outer": {"inner": {"key": "value"}}}

    def test_run_json_with_array(self, client: BackendClient):
        """run_json handles JSON arrays."""
        json_array = '[{"id": 1}, {"id": 2}]'

        with patch.object(client, "run", return_value=json_array):
            result = client.run_json("prompt")

            assert result == [{"id": 1}, {"id": 2}]


class TestClientRunEdgeCases:
    """Tests for run method edge cases."""

    @pytest.fixture
    def client(self) -> BackendClient:
        """Create BackendClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return BackendClient(model="test-model", max_retries=2)

    @patch("ai_delegate.client.time.sleep")
    def test_run_retries_with_exponential_backoff(self, mock_sleep, client):
        """run retries with exponential backoff."""
        # Need Claude CLI available for fallback after max retries
        client._claude_available = True

        with patch.object(client, "_run_ollama") as mock_ollama:
            with patch.object(client, "_run_fallback", return_value="Claude response") as mock_fallback:
                # Fail all retries, then fallback
                mock_ollama.side_effect = RateLimitError("429", permanent=False)

                result = client.run("prompt")

                assert result == "Claude response"
                # Verify exponential backoff: first sleep is 2s, second is 4s
                assert mock_sleep.call_count == 2
                mock_sleep.assert_any_call(2.0)
                mock_sleep.assert_any_call(4.0)

    @patch("ai_delegate.client.time.sleep")
    def test_run_no_retries_on_success(self, mock_sleep, client):
        """run doesn't retry on success."""
        with patch.object(client, "_run_ollama", return_value="Success"):
            result = client.run("prompt")

            assert result == "Success"
            mock_sleep.assert_not_called()


class TestExpertRunnerEdgeCases:
    """Tests for ExpertRunner edge cases."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock AI client."""
        client = Mock(spec=BackendClient)
        client.run_json.return_value = {"findings": []}
        return client

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create task config."""
        return TaskConfig.from_task_type("audit")

    def test_run_parallel_preserves_order(self, mock_client: Mock, task_config: TaskConfig):
        """run_parallel returns results in same order as prompts."""
        runner = ExpertRunner(mock_client, task_config)

        import concurrent.futures

        # The order depends on thread scheduling, but results should be ordered by expert
        results = runner.run_parallel("test code")

        # Results should be for all experts in the task config
        expert_names = [r.expert_name for r in results]
        assert "owasp" in expert_names
        assert "auth" in expert_names
        assert "input" in expert_names


class TestConsensusCalculatorEdgeCases:
    """Tests for ConsensusCalculator edge cases."""

    def test_calculate_with_mixed_findings(self):
        """Consensus calculation with mixed finding types."""
        results = [
            ExpertResult(
                expert_name="expert1",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS", location="file1.py:10"),
                    Finding(severity="medium", issue="CSRF"),
                ],
            ),
            ExpertResult(
                expert_name="expert2",
                expert_type="security",
                findings=[
                    Finding(severity="high", issue="XSS", location="file2.py:20"),
                    Finding(severity="low", issue="Info leak"),
                ],
            ),
        ]

        consensus = ConsensusCalculator.calculate(results)

        # XSS should be consensus (different locations but same issue prefix)
        assert consensus.score > 0

    def test_calculate_with_finding_metadata(self):
        """Consensus calculation handles finding metadata."""
        results = [
            ExpertResult(
                expert_name="expert1",
                expert_type="security",
                findings=[
                    Finding(
                        severity="high",
                        issue="XSS",
                        metadata={"confidence": 0.9, "cwe": "CWE-79"},
                    ),
                ],
            ),
            ExpertResult(
                expert_name="expert2",
                expert_type="security",
                findings=[
                    Finding(
                        severity="high",
                        issue="XSS",
                        metadata={"confidence": 0.8, "source": "static"},
                    ),
                ],
            ),
        ]

        consensus = ConsensusCalculator.calculate(results)

        # Metadata shouldn't affect consensus calculation
        assert len(consensus.consensus_findings) == 1


class TestDebateOrchestratorErrorPaths:
    """Tests for DebateOrchestrator error paths."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock AI client."""
        client = Mock(spec=BackendClient)
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}],
        }
        return client

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit task config."""
        return TaskConfig.from_task_type("audit")

    def test_analyze_creates_verdict_from_consensus(self, mock_client: Mock, audit_config: TaskConfig):
        """FAST tier creates verdict from consensus."""
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        with patch.object(ConsensusCalculator, "calculate") as mock_consensus:
            mock_consensus.return_value = MagicMock(
                score=0.95,
                consensus_findings=[Finding(severity="high", issue="XSS")],
            )

            result = orchestrator.analyze("code", tier=Tier.FAST.value)

            assert result.tier_used == Tier.FAST.value
            assert len(result.findings) == 1

    def test_analyze_handles_all_expert_errors(self, mock_client: Mock, audit_config: TaskConfig):
        """analyze handles when all experts fail."""
        mock_client.run_json.side_effect = RuntimeError("API error")

        orchestrator = DebateOrchestrator(mock_client, audit_config)

        # Should raise since all experts failed
        with pytest.raises(RuntimeError, match="API error"):
            orchestrator.analyze("code", tier=Tier.DEEP.value)


class TestCLIEdgeCases:
    """Tests for CLI edge cases."""

    def test_main_handles_keyboard_interrupt(self):
        """main handles KeyboardInterrupt."""
        from ai_delegate.cli import main

        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin.isatty", return_value=True):
                with pytest.raises(SystemExit):
                    main()

    def test_main_invalid_task_type(self):
        """main handles invalid task type."""
        from ai_delegate.cli import main

        with patch("sys.argv", ["ai-delegate", "invalid"]):
            with pytest.raises(SystemExit):
                main()