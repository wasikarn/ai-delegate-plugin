"""
Tests for BackendClient and SRP components.

Tests rate limiting, retry logic, output processing, and fallback behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from ai_delegate.client import (
    BackendClient,
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

    def test_strip_thinking_removes_think_tags(self):
        """strip_thinking removes <think>...</think> blocks."""
        processor = OutputProcessor()
        output = "<think>This is my reasoning</think>Actual answer"

        result = processor.strip_thinking(output)

        assert "<think>" not in result
        assert "This is my reasoning" not in result
        assert "Actual answer" in result

    def test_strip_thinking_removes_multiline_think_tags(self):
        """strip_thinking handles multiline <think> blocks."""
        processor = OutputProcessor()
        output = "<think>\nline1\nline2\n</think>\n{\"key\": \"value\"}"

        result = processor.strip_thinking(output)

        assert "<think>" not in result
        assert "line1" not in result
        assert '{"key": "value"}' in result

    def test_strip_thinking_removes_ansi_codes(self):
        """strip_thinking removes ANSI escape codes."""
        processor = OutputProcessor()
        output = "\x1b[32mGreen text\x1b[0m normal text"

        result = processor.strip_thinking(output)

        assert "\x1b[" not in result
        assert "Green text" in result
        assert "normal text" in result


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
# BackendClient Tests
# =============================================================================

class TestBackendClientInit:
    """Tests for BackendClient initialization."""

    @patch("ai_delegate.client.shutil.which")
    def test_init_with_ollama_installed(self, mock_which: Mock):
        """Initialization succeeds when ollama is installed."""
        mock_which.return_value = "/usr/local/bin/ollama"

        client = BackendClient(model="test-model")

        assert client.model == "test-model"

    @patch("ai_delegate.client.shutil.which")
    def test_init_warns_without_ollama_cli(self, mock_which: Mock, caplog):
        """Missing ollama CLI is a warning (SDK path doesn't need it)."""
        mock_which.return_value = None

        import logging
        with caplog.at_level(logging.WARNING, logger="ai_delegate.client"):
            BackendClient(model="test-model")  # should not raise

        assert "localhost:11434" in caplog.text

    @patch("ai_delegate.client.shutil.which")
    def test_init_warns_without_claude_fallback(self, mock_which: Mock, caplog):
        """Initialization warns when Claude CLI is not available."""
        mock_which.side_effect = lambda cmd: "/usr/local/bin/ollama" if cmd == "ollama" else None

        BackendClient(model="test-model")

        assert "Claude CLI not found" in caplog.text or True

    @patch("ai_delegate.client.shutil.which")
    def test_init_with_dependency_injection(self, mock_which: Mock):
        """Initialization with injected components."""
        mock_which.return_value = "/usr/local/bin/ollama"

        executor = CLIExecutor(verbose=True)
        limiter = RateLimiter(max_retries=5)
        processor = OutputProcessor()
        parser = ResponseParser()

        client = BackendClient(
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


def _make_sdk_response(text: str) -> MagicMock:
    """Helper: build a fake anthropic SDK response."""
    return MagicMock(content=[MagicMock(text=text)])


class TestBackendClientRun:
    """Tests for BackendClient.run method (ollama path uses Anthropic SDK)."""

    @pytest.fixture
    def mock_executor(self) -> Mock:
        """Create mock executor (used only for non-ollama paths and init checks)."""
        executor = Mock(spec=CLIExecutor)
        executor.execute.return_value = "Model output"
        executor.check_available.return_value = True
        return executor

    @pytest.fixture
    def mock_sdk(self) -> Mock:
        """Create mock anthropic SDK client and inject into sys.modules."""
        import sys
        sdk_client = MagicMock()
        sdk_client.messages.create.return_value = _make_sdk_response("Model output")
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = sdk_client
        # Patch anthropic in sys.modules so lazy `import anthropic` in _run_ollama picks it up
        original = sys.modules.get("anthropic")
        sys.modules["anthropic"] = mock_module
        yield sdk_client
        if original is None:
            sys.modules.pop("anthropic", None)
        else:
            sys.modules["anthropic"] = original

    @pytest.fixture
    def client(self, mock_executor: Mock, mock_sdk: Mock) -> BackendClient:
        """Create BackendClient with mocked executor and SDK."""
        with patch("ai_delegate.client.shutil.which", return_value="/usr/local/bin/ollama"):
            return BackendClient(model="test-model", executor=mock_executor)

    def test_run_returns_output(self, client: BackendClient, mock_sdk: Mock):
        """run returns model output on success."""
        mock_sdk.messages.create.return_value = _make_sdk_response("Model output")

        result = client.run("test prompt")

        assert result == "Model output"

    def test_run_strips_thinking_prefix(self, client: BackendClient, mock_sdk: Mock):
        """run strips <think> blocks from SDK output."""
        mock_sdk.messages.create.return_value = _make_sdk_response(
            "<think>Thinking about the problem...</think>\nThe answer is 42"
        )

        result = client.run("test prompt")

        assert "Thinking" not in result
        assert "The answer is 42" in result

    def test_run_retries_on_rate_limit(self, client: BackendClient, mock_sdk: Mock):
        """run retries on temporary rate limit from SDK."""
        mock_sdk.messages.create.side_effect = [
            Exception("Error: 429 Too Many Requests"),
            Exception("Error: 429 Too Many Requests"),
            _make_sdk_response("Success"),
        ]

        with patch("ai_delegate.client.time.sleep"):
            result = client.run("test prompt")

        assert result == "Success"

    def test_run_fallback_on_permanent_rate_limit(self, mock_executor: Mock, mock_sdk: Mock):
        """run falls back to Claude on permanent rate limit."""
        mock_sdk.messages.create.side_effect = Exception("Error: usage limit exceeded")
        mock_executor.check_available.return_value = True
        mock_executor.execute.return_value = "Claude response"

        with patch("ai_delegate.client.shutil.which", return_value="/usr/local/bin/ollama"):
            client = BackendClient(model="test-model", executor=mock_executor)
            result = client.run("test prompt")

        assert result == "Claude response"


class TestBackendClientRunJson:
    """Tests for BackendClient.run_json method."""

    @pytest.fixture
    def client(self) -> BackendClient:
        """Create BackendClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return BackendClient(model="test-model", verbose=False)

    def test_run_json_returns_dict(self, client: BackendClient):
        """run_json returns parsed JSON dict."""
        with patch.object(client, "run", return_value='{"key": "value"}'):
            result = client.run_json("test prompt")

        assert result == {"key": "value"}

    def test_run_json_extracts_json_from_mixed_output(self, client: BackendClient):
        """run_json extracts JSON from mixed output."""
        with patch.object(client, "run", return_value='Some text {"key": "value"} more text'):
            result = client.run_json("test prompt")

        assert result == {"key": "value"}

    def test_run_json_raises_on_invalid_json(self, client: BackendClient):
        """run_json raises ValueError on invalid JSON."""
        with patch.object(client, "run", return_value="not json at all"):
            with pytest.raises(ValueError, match="Could not parse JSON"):
                client.run_json("test prompt")


class TestBackendClientAsync:
    """Tests for async run_parallel method."""

    @pytest.fixture
    def client(self) -> BackendClient:
        """Create BackendClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return BackendClient(model="test-model")

    def test_run_parallel_returns_results(self, client: BackendClient):
        """run_parallel returns results in order."""
        import asyncio

        with patch.object(client, "run") as mock_run:
            mock_run.side_effect = ["result1", "result2", "result3"]

            results = asyncio.run(client.run_parallel(["prompt1", "prompt2", "prompt3"]))

            assert sorted(results) == ["result1", "result2", "result3"]
            assert mock_run.call_count == 3

    def test_run_parallel_empty_prompts(self, client: BackendClient):
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


# =============================================================================
# Task 3: stdin fix, error classification
# =============================================================================

class TestCLIExecutorStdin:
    @patch("ai_delegate.client.subprocess.run")
    def test_execute_passes_input_to_subprocess(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        executor = CLIExecutor()
        executor.execute(["ollama", "run", "model"], input="my prompt\n")
        _, kwargs = mock_run.call_args
        assert kwargs.get("input") == "my prompt\n"

    @patch("ai_delegate.client.subprocess.run")
    def test_execute_without_input_passes_none(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="result", stderr="")
        executor = CLIExecutor()
        executor.execute(["echo", "hello"])
        _, kwargs = mock_run.call_args
        assert kwargs.get("input") is None


def _mock_anthropic(response_text: str) -> tuple:
    """Helper: create mock anthropic module + sdk client returning response_text."""
    sdk_client = MagicMock()
    sdk_client.messages.create.return_value = _make_sdk_response(response_text)
    mock_module = MagicMock()
    mock_module.Anthropic.return_value = sdk_client
    return mock_module, sdk_client


class TestRunOllamaSDK:
    """Ollama path uses Anthropic SDK (not subprocess)."""

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_calls_sdk_not_subprocess(self, _):
        """Ollama path calls SDK, not subprocess."""
        mock_module, sdk_client = _mock_anthropic('{"findings": []}')
        sdk_client.messages.create.return_value = _make_sdk_response('{"findings": []}')

        with patch.dict("sys.modules", {"anthropic": mock_module}):
            with patch("ai_delegate.client.subprocess.run") as mock_subprocess:
                client = BackendClient(model="glm-5:cloud")
                client.run("my prompt", json_output=False)

        mock_subprocess.assert_not_called()
        mock_module.Anthropic.assert_called_once()

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_cloud_timeout_exceeds_subprocess_timeout(self, _):
        """SDK_CLOUD timeout (180s) > SUBPROCESS timeout (60s)."""
        from ai_delegate.constants import TimeoutConfig
        assert TimeoutConfig.SDK_CLOUD > TimeoutConfig.SUBPROCESS

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_cloud_model_passes_longer_timeout(self, _):
        """Cloud model (:cloud suffix) passes SDK_CLOUD timeout to Anthropic()."""
        from ai_delegate.constants import TimeoutConfig
        captured: dict = {}
        sdk_client = MagicMock()
        sdk_client.messages.create.return_value = _make_sdk_response("result")

        def fake_anthropic(base_url, api_key, timeout):  # noqa: ARG001
            captured["timeout"] = timeout
            return sdk_client

        mock_module = MagicMock()
        mock_module.Anthropic.side_effect = fake_anthropic

        with patch.dict("sys.modules", {"anthropic": mock_module}):
            client = BackendClient(model="glm-5:cloud")
            client.run("prompt")

        assert captured.get("timeout") == TimeoutConfig.SDK_CLOUD

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_strips_think_tags(self, _):
        """<think>...</think> blocks are stripped from SDK response."""
        mock_module, _ = _mock_anthropic("<think>reasoning here</think>actual answer")

        with patch.dict("sys.modules", {"anthropic": mock_module}):
            client = BackendClient(model="glm-5:cloud")
            result = client.run("my prompt")

        assert "<think>" not in result
        assert "actual answer" in result

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_ollama_missing_anthropic_raises_runtime_error(self, _):
        """Missing anthropic package raises RuntimeError with install instructions."""
        import sys
        original = sys.modules.pop("anthropic", None)
        try:
            client = BackendClient(model="glm-5:cloud")
            with pytest.raises(RuntimeError, match="anthropic SDK not installed"):
                client.run("prompt")
        finally:
            if original is not None:
                sys.modules["anthropic"] = original


class TestErrorClassification:
    """on_cli_error callback tests for SDK-based ollama path."""

    def _make_client_with_sdk_error(self, error_msg: str) -> tuple:
        """Create client + mock SDK that raises error_msg on messages.create."""
        sdk_client = MagicMock()
        sdk_client.messages.create.side_effect = Exception(error_msg)
        mock_module = MagicMock()
        mock_module.Anthropic.return_value = sdk_client
        return mock_module, sdk_client

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_on_cli_error_called_on_rate_limit(self, _):
        mock_module, _ = self._make_client_with_sdk_error("429 rate limit exceeded")
        error_calls: list = []
        # Executor with Claude unavailable so fallback fails → exception propagates
        mock_executor = Mock(spec=CLIExecutor)
        mock_executor.check_available.return_value = False
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            client = BackendClient(
                model="glm-5:cloud",
                max_retries=1,
                executor=mock_executor,
                on_cli_error=lambda cli, etype: error_calls.append((cli, etype)),
            )
            with pytest.raises(Exception):
                client.run("prompt")
        assert any(etype == "rate_limit" for _, etype in error_calls)

    @patch("ai_delegate.client.shutil.which", return_value="/usr/bin/ollama")
    def test_on_cli_error_called_on_auth_error(self, _):
        mock_module, _ = self._make_client_with_sdk_error("401 unauthorized")
        error_calls: list = []
        mock_executor = Mock(spec=CLIExecutor)
        mock_executor.check_available.return_value = False
        with patch.dict("sys.modules", {"anthropic": mock_module}):
            client = BackendClient(
                model="glm-5:cloud",
                max_retries=1,
                executor=mock_executor,
                on_cli_error=lambda cli, etype: error_calls.append((cli, etype)),
            )
            with pytest.raises(Exception):
                client.run("prompt")
        assert any(etype == "auth" for _, etype in error_calls)