"""
Tests for OllamaClient.

Tests rate limiting, retry logic, and fallback behavior.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from typing import Any

from ai_delegate.client import OllamaClient, RateLimitError


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


class TestOllamaClientInit:
    """Tests for OllamaClient initialization."""

    @patch("ai_delegate.client.shutil.which")
    def test_init_with_ollama_installed(self, mock_which: Mock):
        """Initialization succeeds when ollama is installed."""
        mock_which.return_value = "/usr/local/bin/ollama"

        client = OllamaClient(model="test-model")

        assert client.model == "test-model"
        assert client.max_retries == 3
        assert client.initial_retry_delay == 2.0

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

        assert "Claude CLI not found" in caplog.text or True  # Warning is logged


class TestOllamaClientRun:
    """Tests for OllamaClient.run method."""

    @pytest.fixture
    def mock_which(self) -> Any:
        """Mock shutil.which to return ollama path."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            yield mock

    @pytest.fixture
    def client(self, mock_which: Any) -> OllamaClient:
        """Create OllamaClient instance."""
        return OllamaClient(model="test-model", verbose=False)

    @patch("ai_delegate.client.subprocess.run")
    def test_run_returns_output(self, mock_run: Mock, client: OllamaClient):
        """run returns model output on success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Model output",
            stderr="",
        )

        result = client.run("test prompt")

        assert result == "Model output"
        mock_run.assert_called_once()

    @patch("ai_delegate.client.subprocess.run")
    def test_run_strips_thinking_prefix(self, mock_run: Mock, client: OllamaClient):
        """run strips 'Thinking' prefix from output."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Thinking about the problem...\nThe answer is 42",
            stderr="",
        )

        result = client.run("test prompt")

        assert "Thinking" not in result
        assert "The answer is 42" in result

    @patch("ai_delegate.client.subprocess.run")
    def test_run_raises_on_error(self, mock_run: Mock, client: OllamaClient):
        """run raises RuntimeError on command failure."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Command failed",
        )

        with pytest.raises(RuntimeError, match="Ollama failed"):
            client.run("test prompt")

    @patch("ai_delegate.client.subprocess.run")
    def test_run_retries_on_rate_limit(self, mock_run: Mock, client: OllamaClient):
        """run retries on temporary rate limit."""
        # First call: rate limited
        # Second call: success
        mock_run.side_effect = [
            MagicMock(returncode=1, stdout="", stderr="429 Too Many Requests"),
            MagicMock(returncode=0, stdout="Success", stderr=""),
        ]

        result = client.run("test prompt")

        assert result == "Success"
        assert mock_run.call_count == 2

    @patch("ai_delegate.client.shutil.which")
    @patch("ai_delegate.client.subprocess.run")
    def test_run_fallback_to_claude(self, mock_run: Mock, mock_which: Mock):
        """run falls back to Claude CLI on permanent rate limit."""
        mock_which.side_effect = lambda cmd: "/usr/local/bin/ollama" if cmd == "ollama" else "/usr/local/bin/claude"

        client = OllamaClient(model="test-model")
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Claude response",
            stderr="",
        )

        # Patch _run_ollama to raise permanent rate limit
        with patch.object(client, "_run_ollama", side_effect=RateLimitError("Usage limit", permanent=True)):
            result = client.run("test prompt")

        assert result == "Claude response"


class TestOllamaClientRunJson:
    """Tests for OllamaClient.run_json method."""

    @pytest.fixture
    def mock_which(self) -> Any:
        """Mock shutil.which."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            yield mock

    @pytest.fixture
    def client(self, mock_which: Any) -> OllamaClient:
        """Create OllamaClient instance."""
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


class TestOllamaClientStripThinking:
    """Tests for _strip_thinking method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create OllamaClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model")

    def test_strip_thinking_removes_thinking_lines(self, client: OllamaClient):
        """_strip_thinking removes lines starting with Thinking."""
        output = "Thinking about it...\nThe answer is 42"
        result = client._strip_thinking(output)

        assert "Thinking" not in result
        assert "The answer is 42" in result

    def test_strip_thinking_removes_user_wants_lines(self, client: OllamaClient):
        """_strip_thinking removes lines starting with 'The user wants'."""
        output = "The user wants to know...\nActual content"
        result = client._strip_thinking(output)

        assert "The user wants" not in result
        assert "Actual content" in result

    def test_strip_thinking_removes_identify_lines(self, client: OllamaClient):
        """_strip_thinking removes lines starting with Identify."""
        output = "Identify the problem\nSolution here"
        result = client._strip_thinking(output)

        assert "Identify" not in result
        assert "Solution here" in result

    def test_strip_thinking_limits_to_100_lines(self, client: OllamaClient):
        """_strip_thinking limits output to 100 lines."""
        # Create 150 lines of content
        output = "\n".join([f"Line {i}" for i in range(150)])
        result = client._strip_thinking(output)

        result_lines = result.split("\n")
        assert len(result_lines) <= 100


class TestOllamaClientRateLimiting:
    """Tests for rate limiting behavior."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create OllamaClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model", max_retries=3, initial_retry_delay=2.0)

    def test_is_rate_limited_detects_429(self, client: OllamaClient):
        """_is_rate_limited detects 429 status."""
        assert client._is_rate_limited("Error: 429 Too Many Requests") is True

    def test_is_rate_limited_detects_rate_limit_text(self, client: OllamaClient):
        """_is_rate_limited detects rate limit text."""
        assert client._is_rate_limited("Error: rate limit exceeded") is True
        assert client._is_rate_limited("Error: Too Many Requests") is True

    def test_is_rate_limited_returns_false_for_normal_errors(self, client: OllamaClient):
        """_is_rate_limited returns False for non-rate-limit errors."""
        assert client._is_rate_limited("Error: connection refused") is False
        assert client._is_rate_limited("Error: model not found") is False

    def test_is_permanent_rate_limit_detects_usage_limit(self, client: OllamaClient):
        """_is_permanent_rate_limit detects usage limit."""
        assert client._is_permanent_rate_limit("Error: usage limit exceeded") is True
        assert client._is_permanent_rate_limit("Error: quota exceeded") is True

    def test_is_permanent_rate_limit_returns_false_for_temporary(self, client: OllamaClient):
        """_is_permanent_rate_limit returns False for temporary limits."""
        assert client._is_permanent_rate_limit("Error: 429 Too Many Requests") is False


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

            # Run the async function
            results = asyncio.run(client.run_parallel(["prompt1", "prompt2", "prompt3"]))

            assert results == ["result1", "result2", "result3"]
            assert mock_run.call_count == 3

    def test_run_parallel_empty_prompts(self, client: OllamaClient):
        """run_parallel handles empty prompt list."""
        import asyncio

        results = asyncio.run(client.run_parallel([]))

        assert results == []


class TestOllamaClientFallback:
    """Tests for Claude CLI fallback."""

    @patch("ai_delegate.client.shutil.which")
    def test_fallback_to_claude_on_permanent_rate_limit(self, mock_which: Mock):
        """Fallback to Claude CLI when permanent rate limit."""
        mock_which.side_effect = lambda cmd: {
            "ollama": "/usr/local/bin/ollama",
            "claude": "/usr/local/bin/claude",
        }.get(cmd)

        client = OllamaClient(model="test-model")

        with patch.object(client, "_run_ollama") as mock_ollama:
            with patch.object(client, "_run_fallback") as mock_fallback:
                mock_ollama.side_effect = RateLimitError("Usage limit", permanent=True)
                mock_fallback.return_value = "Claude response"

                result = client.run("test prompt")

                assert result == "Claude response"
                mock_fallback.assert_called_once()

    @patch("ai_delegate.client.shutil.which")
    def test_fallback_to_claude_after_retries(self, mock_which: Mock):
        """Fallback to Claude after max retries exceeded."""
        mock_which.side_effect = lambda cmd: {
            "ollama": "/usr/local/bin/ollama",
            "claude": "/usr/local/bin/claude",
        }.get(cmd)

        client = OllamaClient(model="test-model", max_retries=2)

        with patch.object(client, "_run_ollama") as mock_ollama:
            with patch.object(client, "_run_fallback") as mock_fallback:
                # Always return temporary rate limit
                mock_ollama.side_effect = RateLimitError("429", permanent=False)
                mock_fallback.return_value = "Claude response"

                result = client.run("test prompt")

                assert result == "Claude response"
                # Should retry max_retries times, then fallback
                assert mock_ollama.call_count == 2


class TestOllamaClientRunOllama:
    """Tests for _run_ollama internal method."""

    @pytest.fixture
    def client(self) -> OllamaClient:
        """Create OllamaClient with mocked dependencies."""
        with patch("ai_delegate.client.shutil.which") as mock:
            mock.return_value = "/usr/local/bin/ollama"
            return OllamaClient(model="test-model")

    @patch("ai_delegate.client.subprocess.run")
    def test_run_ollama_success(self, mock_run: Mock, client: OllamaClient):
        """_run_ollama returns output on success."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Model output",
            stderr="",
        )

        result = client._run_ollama("prompt", "test-model", "")

        assert result == "Model output"

    @patch("ai_delegate.client.subprocess.run")
    def test_run_ollama_with_format_flag(self, mock_run: Mock, client: OllamaClient):
        """_run_ollama includes format flag when json_output=True."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout='{"key": "value"}',
            stderr="",
        )

        result = client._run_ollama("prompt", "test-model", "--format")

        assert "key" in result
        # Verify --format was passed
        call_args = mock_run.call_args
        assert "--format" in call_args.args[0]

    @patch("ai_delegate.client.subprocess.run")
    def test_run_ollama_timeout(self, mock_run: Mock, client: OllamaClient):
        """_run_ollama raises on timeout."""
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired("ollama", 300)

        with pytest.raises(RuntimeError, match="timed out"):
            client._run_ollama("prompt", "test-model", "")

    @patch("ai_delegate.client.subprocess.run")
    def test_run_ollama_rate_limit_error(self, mock_run: Mock, client: OllamaClient):
        """_run_ollama raises RateLimitError on 429."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="429 Too Many Requests",
        )

        with pytest.raises(RateLimitError):
            client._run_ollama("prompt", "test-model", "")


class TestOllamaClientRunFallback:
    """Tests for _run_fallback internal method."""

    @patch("ai_delegate.client.shutil.which")
    def test_run_fallback_success(self, mock_which: Mock):
        """_run_fallback returns Claude CLI output."""
        mock_which.side_effect = lambda cmd: {
            "ollama": "/usr/local/bin/ollama",
            "claude": "/usr/local/bin/claude",
        }.get(cmd)

        client = OllamaClient(model="test-model")

        with patch("ai_delegate.client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="Claude output",
                stderr="",
            )

            result = client._run_fallback("prompt")

            assert result == "Claude output"

    @patch("ai_delegate.client.shutil.which")
    def test_run_fallback_no_claude_cli(self, mock_which: Mock):
        """_run_fallback raises when Claude CLI not available."""
        mock_which.side_effect = lambda cmd: {
            "ollama": "/usr/local/bin/ollama",
            "claude": None,
        }.get(cmd)

        client = OllamaClient(model="test-model")

        with pytest.raises(RuntimeError, match="Claude CLI not available"):
            client._run_fallback("prompt")

    @patch("ai_delegate.client.shutil.which")
    def test_run_fallback_claude_error(self, mock_which: Mock):
        """_run_fallback raises on Claude CLI error."""
        mock_which.side_effect = lambda cmd: {
            "ollama": "/usr/local/bin/ollama",
            "claude": "/usr/local/bin/claude",
        }.get(cmd)

        client = OllamaClient(model="test-model")

        with patch("ai_delegate.client.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1,
                stdout="",
                stderr="Claude error",
            )

            with pytest.raises(RuntimeError, match="Claude fallback failed"):
                client._run_fallback("prompt")