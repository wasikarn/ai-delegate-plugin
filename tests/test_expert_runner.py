"""
Tests for ExpertRunner component.

Tests parallel expert execution with mocked clients.
"""

import pytest
from unittest.mock import Mock

from ai_delegate.client import OllamaClient
from ai_delegate.models import TaskConfig
from ai_delegate.debate.orchestrator import ExpertRunner


class TestExpertRunner:
    """Tests for ExpertRunner."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock OllamaClient."""
        client = Mock(spec=OllamaClient)
        client.run_json.return_value = {
            "findings": [
                {"severity": "high", "issue": "XSS vulnerability"},
                {"severity": "medium", "issue": "Info leak"},
            ]
        }
        return client

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create sample task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def runner(self, mock_client: Mock, task_config: TaskConfig) -> ExpertRunner:
        """Create ExpertRunner instance."""
        return ExpertRunner(mock_client, task_config, verbose=False)

    def test_run_parallel_returns_results_for_all_experts(
        self, runner: ExpertRunner, sample_code: str
    ):
        """All experts should return results."""
        results = runner.run_parallel(sample_code)

        # Audit has 3 experts: owasp, auth, input
        assert len(results) == 3
        for result in results:
            assert result.expert_name in ["owasp", "auth", "input"]
            assert result.expert_type == "audit"

    def test_run_parallel_processes_findings(
        self, runner: ExpertRunner, sample_code: str
    ):
        """Expert results should contain parsed findings."""
        results = runner.run_parallel(sample_code)

        for result in results:
            assert result.success is True
            assert len(result.findings) == 2
            assert result.findings[0].severity == "high"
            assert result.findings[1].severity == "medium"

    def test_run_parallel_handles_expert_error(
        self, mock_client: Mock, task_config: TaskConfig, sample_code: str
    ):
        """Failed experts should return error result, not raise."""
        # Make one expert fail
        call_count = 0

        def side_effect(prompt):
            nonlocal call_count
            call_count += 1
            if call_count == 1:  # First expert fails
                raise RuntimeError("API timeout")
            return {"findings": [{"severity": "low", "issue": "Minor issue"}]}

        mock_client.run_json.side_effect = side_effect
        runner = ExpertRunner(mock_client, task_config, verbose=False)

        results = runner.run_parallel(sample_code)

        # Should still get results for all experts
        assert len(results) == 3

        # First result should have error
        error_results = [r for r in results if r.error]
        assert len(error_results) == 1
        assert error_results[0].error == "API timeout"

    def test_run_parallel_measures_duration(
        self, runner: ExpertRunner, sample_code: str
    ):
        """Expert results should include duration."""
        results = runner.run_parallel(sample_code)

        for result in results:
            if result.success:
                assert result.duration_ms is not None
                assert result.duration_ms >= 0

    def test_run_single_expert_builds_correct_prompt(
        self, mock_client: Mock, task_config: TaskConfig
    ):
        """Expert prompt should include task content."""
        runner = ExpertRunner(mock_client, task_config, verbose=False)

        runner._run_single_expert(
            "owasp",
            "You are an OWASP expert.",
            "def hello(): pass",
        )

        # Verify prompt includes content
        call_args = mock_client.run_json.call_args
        assert call_args is not None
        prompt_text = str(call_args.args[0])
        assert "OWASP expert" in prompt_text
        assert "def hello(): pass" in prompt_text

    def test_run_single_expert_handles_invalid_json(
        self, mock_client: Mock, task_config: TaskConfig
    ):
        """Invalid JSON should result in empty findings."""
        mock_client.run_json.side_effect = ValueError("Invalid JSON")
        runner = ExpertRunner(mock_client, task_config, verbose=False)

        result = runner._run_single_expert(
            "owasp",
            "You are an OWASP expert.",
            "code",
        )

        assert result.error is not None
        assert "Invalid JSON" in result.error

    def test_uses_pooled_thread_executor(self, mock_client: Mock, task_config: TaskConfig):
        """ExpertRunner should use shared thread pool."""
        runner1 = ExpertRunner(mock_client, task_config)
        runner2 = ExpertRunner(mock_client, task_config)

        # Both should share the same executor
        assert runner1._executor is runner2._executor


class TestExpertRunnerParallelExecution:
    """Tests for parallel execution behavior."""

    @pytest.fixture
    def slow_client(self) -> Mock:
        """Create client that simulates slow responses."""
        client = Mock(spec=OllamaClient)
        import time

        def slow_response(prompt):
            time.sleep(0.1)  # Simulate 100ms delay
            return {"findings": [{"severity": "low", "issue": "test"}]}

        client.run_json.side_effect = slow_response
        return client

    def test_parallel_is_faster_than_sequential(
        self, slow_client: Mock, sample_code: str
    ):
        """Parallel execution should be faster than sequential."""
        import time

        task_config = TaskConfig.from_task_type("audit")
        runner = ExpertRunner(slow_client, task_config)

        start = time.time()
        results = runner.run_parallel(sample_code)
        parallel_duration = time.time() - start

        # 3 experts at 100ms each would be 300ms sequential
        # Parallel should be ~100ms + overhead
        assert len(results) == 3
        assert parallel_duration < 0.35  # Allow some overhead


class TestExpertRunnerEdgeCases:
    """Edge case tests for ExpertRunner."""

    @pytest.fixture
    def mock_client(self) -> Mock:
        """Create mock client for edge cases."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def task_config(self) -> TaskConfig:
        """Create task config for edge cases."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def runner(self, mock_client: Mock, task_config: TaskConfig) -> ExpertRunner:
        """Create ExpertRunner with mock client."""
        return ExpertRunner(mock_client, task_config)

    def test_empty_content(self, runner: ExpertRunner):
        """Empty content should still work."""
        results = runner.run_parallel("")
        assert len(results) == 3

    def test_very_long_content(self, runner: ExpertRunner):
        """Very long content should be handled."""
        long_code = "x = 1\n" * 10000
        results = runner.run_parallel(long_code)
        assert len(results) == 3

    def test_unicode_content(self, runner: ExpertRunner):
        """Unicode content should be handled."""
        unicode_code = "def hello(): return 'สวัสดี'"
        results = runner.run_parallel(unicode_code)
        assert len(results) == 3

    def test_special_characters_in_content(self, runner: ExpertRunner):
        """Special characters should not break prompt."""
        special_code = "code = '''\\n\\t\\r\\n'''"
        results = runner.run_parallel(special_code)
        assert len(results) == 3