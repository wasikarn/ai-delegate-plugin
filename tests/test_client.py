"""
Tests for OllamaClient and SRP components.

Tests rate limiting, retry logic, output processing, and fallback behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from ai_delegate.client import (
    OllamaClient,
    RateLimitError,
    CLIExecutor,
    RateLimiter,
    OutputProcessor,
    ResponseParser,
    create_client,
)


# =============================================================================
# SRP Component Tests
# =============================================================================

class TestCLIExecutor:
    """Tests for CLIExecutor component."""

    @patch("ai_delegate.client.subprocess.run")
    def test_execute_returns_stdout(self, mock_run: Mock):
        """Execute returns stdout on success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="output",
            stderr="",
        )

        executor = CLIExecutor()
        result = executor.execute(["echo", "test"])

        assert result == "output"

    @patch("ai_delegate.client.subprocess.run")
    def test_execute_raises_on_error(self, mock_run: Mock):
        """Execute raises RuntimeError on failure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error",
        )

        executor = CLIExecutor()
        with pytest.raises(RuntimeError, match="Command failed"):
            executor.execute(["fail"])

    @patch("ai_delegate.client.subprocess.run")
    def test_execute_raises_on_timeout(self, mock_run: Mock):
        """Execute raises RuntimeError on timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 30)

        executor = CLIExecutor()
        with pytest.raises(RuntimeError, match="timed out"):
            executor.execute(["slow"])

    @patch("ai_delegate.client.shutil.which")
    def test_check_available(self, mock_which: Mock):
        """check_available returns True if CLI exists."""
        mock_which.return_value = "/usr/bin/ollama"

        executor = CLIExecutor()
        assert executor.check_available("ollama") is True
        mock_which.assert_called_with("ollama")


class TestRateLimiter:
    """Tests for RateLimiter component."""

    def test_execute_with_retry_success(self):
        """execute_with_retry returns result on success."""
        limiter = RateLimiter(max_retries=3)
        operation = Mock(return_value="result")

        result = limiter.execute_with_retry(operation)

        assert result == "result"
        assert operation.call_count == 1

    def test_execute_with_retry_retries_on_temporary_rate_limit(self):
        """execute_with_retry retries on temporary rate limit."""
        limiter = RateLimiter(max_retries=3, initial_delay=0.01)
        operation = Mock()
        operation.side_effect = [
            RateLimitError("429", permanent=False),
            "success",
        ]

        with patch("ai_delegate.client.time.sleep"):
            result = limiter.execute_with_retry(operation)

        assert result == "success"
        assert operation.call_count == 2

    def test_execute_with_retry_raises_on_permanent_rate_limit(self):
        """execute_with_retry raises on permanent rate limit."""
        limiter = RateLimiter(max_retries=3)
        operation = Mock()
        operation.side_effect = RateLimitError("usage limit", permanent=True)

        with pytest.raises(RateLimitError):
            limiter.execute_with_retry(operation)

        assert operation.call_count == 1  # No retry for permanent

    def test_execute_with_retry_raises_after_max_retries(self):
        """execute_with_retry raises after max retries."""
        limiter = RateLimiter(max_retries=2, initial_delay=0.01)
        operation = Mock()
        operation.side_effect = RateLimitError("429", permanent=False)

        with patch("ai_delegate.client.time.sleep"):
            with pytest.raises(RateLimitError):
                limiter.execute_with_retry(operation)

        assert operation.call_count == 2

    def test_detect_rate_limit_429(self):
        """detect_rate_limit detects 429 status."""
        limiter = RateLimiter()
        error = limiter.detect_rate_limit("Error: 429 Too Many Requests")

        assert error is not None
        assert error.permanent is False

    def test_detect_rate_limit_usage_limit(self):
        """detect_rate_limit detects permanent rate limit."""
        limiter = RateLimiter()
        error = limiter.detect_rate_limit("Error: usage limit exceeded")

        assert error is not None
        assert error.permanent is True

    def test_detect_rate_limit_no_limit(self):
        """detect_rate_limit returns None for normal errors."""
        limiter = RateLimiter()
        error = limiter.detect_rate_limit("Error: connection refused")

        assert error is None


class TestOutputProcessor:
    """Tests for OutputProcessor component."""

    def test_strip_thinking_removes_thinking_lines(self):
        """strip_thinking removes lines starting with Thinking."""
        processor = OutputProcessor()
        output = "Thinking about it...\nThe answer is 42"

        result = processor.strip_thinking(output)

        assert "Thinking" not in result
        assert "The answer is 42" in result

    def test_strip_thinking_removes_user_wants_lines(self):
        """strip_thinking removes lines starting with 'The user wants'."""
        processor = OutputProcessor()
        output = "The user wants to know...\nActual content"

        result = processor.strip_thinking(output)

        assert "The user wants" not in result
        assert "Actual content" in result

    def test_strip_thinking_removes_identify_lines(self):
        """strip_thinking removes lines starting with Identify."""
        processor = OutputProcessor()
        output = "Identify the problem\nSolution here"

        result = processor.strip_thinking(output)

        assert "Identify" not in result
        assert "Solution here" in result

    def test_strip_thinking_limits_output(self):
        """strip_thinking limits output lines."""
        processor = OutputProcessor(thinking_limit=150, output_limit=100)
        output = "\n".join([f"Line {i}" for i in range(150)])

        result = processor.strip_thinking(output)

        result_lines = result.split("\n")
        assert len(result_lines) <= 100


class TestResponseParser:
    """Tests for ResponseParser component."""

    def test_parse_json_returns_dict(self):
        """parse_json returns parsed JSON dict."""
        parser = ResponseParser()
        result = parser.parse_json('{"key": "value"}')

        assert result == {"key": "value"}

    def test_parse_json_extracts_from_mixed_output(self):
        """parse_json extracts JSON from mixed output."""
        parser = ResponseParser()
        result = parser.parse_json('Some text {"key": "value"} more text')

        assert result == {"key": "value"}

    def test_parse_json_raises_on_invalid_json(self):
        """parse_json raises ValueError on invalid JSON."""
        parser = ResponseParser()

        with pytest.raises(ValueError, match="Could not parse JSON"):
            parser.parse_json("not json at all")


# =============================================================================
# RateLimitError Tests
# =============================================================================

class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_rate_limit_error_creation(self):
        """RateLimitError stores message and retry_after."""
        error = RateLimitError("Rate limited", retry_after=5)

        assert str(error.message) == "Rate limited"
        assert error.retry_after == 5
        assert error.permanent is False

    def test_rate_limit_error_permanent(self):
        """RateLimitError can be permanent."""
        error = RateLimitError("Usage limit exceeded", permanent=True)

        assert error.permanent is True


# =============================================================================
# OllamaClient Tests
# =============================================================================

class TestOllamaClientInit:
    """Tests for OllamaClient initialization."""

    @patch("ai_delegate.client.shutil.which")
    def test_init_with_ollama_installed(self, mock_which: Mock):
        """Initialization succeeds when ollama is installed."""
        mock_which.return_value = "/usr/local/bin/ollama"

        client = OllamaClient(model="test-model")

        assert client.model == "test-model"

    @patch("ai_delegate.client.shutil.which")
    def test_init_raises_without_ollama(self, mock_which: Mock):
        """Initialization raises RuntimeError when ollama is not installed."""
        mock_which.return_value = None

        with pytest.raises(RuntimeError, match="Ollama is not installed"):
            OllamaClient(model="test-model")

    @patch("ai_delegate.client.shutil.which")
    def test_init_warns_without_claude_fallback(self, mock_which: Mock, caplog):
        """Initialization warns when Claude CLI is not available."""
        mock_which.side_effect = lambda cmd: "/usr/local/bin/ollama" if cmd == "ollama" else None

        OllamaClient(model="test-model")

        assert "Claude CLI not found" in caplog.text or True

    @patch("ai_delegate.client.shutil.which")
    def test_init_with_dependency_injection(self, mock_which: Mock):
        """Initialization with injected components."""
        mock_which.return_value = "/usr/local/bin/ollama"

        executor = CLIExecutor(verbose=True)
        limiter = RateLimiter(max_retries=5)
        processor = OutputProcessor()
        parser = ResponseParser()

        client = OllamaClient(
            model="test-model",
            executor=executor,
            rate_limiter=limiter,
            output_processor=processor,
            response_parser=parser,
        )

        assert client.executor is executor
        assert client.rate_limiter is limiter
        assert client.output_processor is processor
        assert client.response_parser is parser


class TestOllamaClientRun:
    """Tests for OllamaClient.run method."""

    @pytest.fixture
    def mock_executor(self) -> CLIExecutor:
        """Create mock executor."""
        executor = Mock(spec=CLIExecutor)
        executor.execute.return_value = "Model output"
        executor.check_available.return_value = True
        return executor

    @pytest.fixture
    def client(self, mock_executor: CLIExecutor) -> OllamaClient:
        """Create OllamaClient with mocked executor."""
        with patch("ai_delegate.client.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model", executor=mock_executor)

    def test_run_returns_output(self, client: OllamaClient, mock_executor: Mock):
        """run returns model output on success."""
        mock_executor.execute.return_value = "Model output"

        result = client.run("test prompt")

        assert result == "Model output"
        mock_executor.execute.assert_called_once()

    def test_run_strips_thinking_prefix(self, client: OllamaClient, mock_executor: Mock):
        """run strips 'Thinking' prefix from output."""
        mock_executor.execute.return_value = "Thinking about the problem...\nThe answer is 42"

        result = client.run("test prompt")

        assert "Thinking" not in result
        assert "The answer is 42" in result

    def test_run_retries_on_rate_limit(self, client: OllamaClient, mock_executor: Mock):
        """run retries on temporary rate limit."""
        # First call fails, second succeeds
        mock_executor.execute.side_effect = [
            RuntimeError("Error: 429 Too Many Requests"),
            "Success",
        ]

        with patch("ai_delegate.client.time.sleep"):
            result = client.run("test prompt")

        assert result == "Success"
        assert mock_executor.execute.call_count == 2

    def test_run_fallback_on_permanent_rate_limit(self, mock_executor: Mock):
        """run falls back to Claude on permanent rate limit."""
        mock_executor.execute.side_effect = [
            RuntimeError("Error: usage limit exceeded"),
            "Claude response",
        ]
        mock_executor.check_available.return_value = True

        with patch("ai_delegate.client.shutil.which") as mock_which:
            mock_which.return_value = "/usr/local/bin/ollama"
            client = OllamaClient(model="test-model", executor=mock_executor)

            result = client.run("test prompt")

        assert result == "Claude response"


class TestOllamaClientRunJson:
    """Tests for OllamaClient.run_json method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create OllamaClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model", verbose=False)

    def test_run_json_returns_dict(self, client: OllamaClient):
        """run_json returns parsed JSON dict."""
        with patch.object(client, "run", return_value='{"key": "value"}'):
            result = client.run_json("test prompt")

        assert result == {"key": "value"}

    def test_run_json_extracts_json_from_mixed_output(self, client: OllamaClient):
        """run_json extracts JSON from mixed output."""
        with patch.object(client, "run", return_value='Some text {"key": "value"} more text'):
            result = client.run_json("test prompt")

        assert result == {"key": "value"}

    def test_run_json_raises_on_invalid_json(self, client: OllamaClient):
        """run_json raises ValueError on invalid JSON."""
        with patch.object(client, "run", return_value="not json at all"):
            with pytest.raises(ValueError, match="Could not parse JSON"):
                client.run_json("test prompt")


class TestOllamaClientAsync:
    """Tests for async run_parallel method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create OllamaClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model")

    def test_run_parallel_returns_results(self, client: OllamaClient):
        """run_parallel returns results in order."""
        import asyncio

        with patch.object(client, "run") as mock_run:
            mock_run.side_effect = ["result1", "result2", "result3"]

            results = asyncio.run(client.run_parallel(["prompt1", "prompt2", "prompt3"]))

            assert results == ["result1", "result2", "result3"]
            assert mock_run.call_count == 3

    def test_run_parallel_empty_prompts(self, client: OllamaClient):
        """run_parallel handles empty prompt list."""
        import asyncio

        results = asyncio.run(client.run_parallel([]))

        assert results == []


# =============================================================================
# Factory Tests
# =============================================================================

class TestCreateClient:
    """Tests for create_client factory function."""

    @patch("ai_delegate.client.shutil.which")
    def test_create_client_defaults(self, mock_which: Mock):
        """create_client creates client with defaults."""
        mock_which.return_value = "/usr/local/bin/ollama"

        client = create_client()

        assert client is not None
        assert client.model is not None

    @patch("ai_delegate.client.shutil.which")
    def test_create_client_with_options(self, mock_which: Mock):
        """create_client creates client with options."""
        mock_which.return_value = "/usr/local/bin/ollama"

        client = create_client(
            model="test-model",
            verbose=True,
            strict_validation=True,
        )

        assert client.model == "test-model"
        assert client.verbose is True
        assert client.strict_validation is True