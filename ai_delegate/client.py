"""
AI Client with rate limiting and fallback support.

Supports multiple backends: ollama (default), gemini, codex.

Architecture follows Single Responsibility Principle:
- CLIExecutor: subprocess execution
- RateLimiter: retry & backoff logic
- OutputProcessor: stripping thinking prefix
- ResponseParser: JSON parsing
- OllamaClient: orchestrates components
"""

import subprocess
import json
import time
import shutil
import logging
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

from .constants import Models, RetryConfig, TokenLimits
from .validation import validate_prompt, validate_model_name, ValidationResult

logger = logging.getLogger(__name__)


@dataclass
class RateLimitError(Exception):
    """Rate limit error from AI API."""
    message: str
    retry_after: int = RetryConfig.INITIAL_DELAY
    permanent: bool = False


class AIClient(ABC):
    """
    Abstract base class for AI clients.

    Subclasses implement backend-specific logic.
    """

    @abstractmethod
    def run(self, prompt: str, json_output: bool = True) -> str:
        """Run prompt and return response."""
        pass

    @abstractmethod
    def run_json(self, prompt: str) -> Dict[str, Any]:
        """Run prompt and parse JSON response."""
        pass


# =============================================================================
# Single Responsibility Components
# =============================================================================

class CLIExecutor:
    """
    Executes CLI commands via subprocess.

    Single responsibility: subprocess execution and error handling.
    """

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def execute(
        self,
        cmd: List[str],
        timeout: int = RetryConfig.API_TIMEOUT,
        input: Optional[str] = None,
    ) -> str:
        """
        Execute command and return stdout.

        Args:
            cmd: Command and arguments as list
            timeout: Timeout in seconds
            input: Optional stdin input string

        Returns:
            stdout from command

        Raises:
            RuntimeError: If command fails or times out
        """
        if self.verbose:
            logger.info(f"Running: {' '.join(cmd[:3])}...")

        try:
            result = subprocess.run(
                cmd,
                input=input,
                capture_output=True,
                text=True,
                timeout=timeout,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Command failed: {result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Command timed out after {timeout}s")

    def check_available(self, cli_name: str) -> bool:
        """Check if a CLI tool is available."""
        return shutil.which(cli_name) is not None


class RateLimiter:
    """
    Handles retry logic with exponential backoff.

    Single responsibility: rate limit detection and retry management.
    """

    def __init__(
        self,
        max_retries: int = RetryConfig.MAX_RETRIES,
        initial_delay: float = RetryConfig.INITIAL_DELAY,
        backoff_multiplier: float = RetryConfig.BACKOFF_MULTIPLIER,
    ):
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.backoff_multiplier = backoff_multiplier

    def execute_with_retry(
        self,
        operation: Callable[[], str],
        on_rate_limit: Optional[Callable[[RateLimitError], None]] = None,
    ) -> str:
        """
        Execute operation with retry on rate limit.

        Args:
            operation: Function to execute
            on_rate_limit: Optional callback for rate limit events

        Returns:
            Operation result

        Raises:
            RateLimitError: If rate limit persists after all retries
        """
        delay = self.initial_delay

        for attempt in range(self.max_retries):
            try:
                return operation()
            except RateLimitError as e:
                if e.permanent:
                    raise

                if on_rate_limit:
                    on_rate_limit(e)

                logger.warning(
                    f"Rate limited, retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                delay *= self.backoff_multiplier

        raise RateLimitError(
            message=f"Max retries ({self.max_retries}) exceeded",
            permanent=True,
        )

    def detect_rate_limit(self, output: str) -> Optional[RateLimitError]:
        """
        Detect if output indicates rate limit.

        Returns:
            RateLimitError if detected, None otherwise
        """
        indicators = ["429", "rate limit", "Too Many Requests", "usage limit"]
        if not any(indicator in output for indicator in indicators):
            return None

        permanent_indicators = ["usage limit", "quota", "exceeded"]
        is_permanent = any(indicator in output for indicator in permanent_indicators)

        return RateLimitError(
            message="Rate limit exceeded",
            permanent=is_permanent,
        )


class OutputProcessor:
    """
    Processes model output.

    Single responsibility: output cleaning and filtering.
    """

    def __init__(
        self,
        thinking_limit: int = TokenLimits.THINKING_LINE_LIMIT,
        output_limit: int = TokenLimits.OUTPUT_LINE_LIMIT,
    ):
        self.thinking_limit = thinking_limit
        self.output_limit = output_limit

    def strip_thinking(self, output: str) -> str:
        """Strip thinking prefix from model output."""
        lines = output.split("\n")[:self.thinking_limit]
        filtered = [
            line for line in lines
            if not line.startswith(("Thinking", "The user wants"))
            and not line.strip().startswith("Identify")
        ]
        return "\n".join(filtered[:self.output_limit])

    def process(self, output: str) -> str:
        """Apply all output processing."""
        return self.strip_thinking(output)


class ResponseParser:
    """
    Parses JSON responses.

    Single responsibility: JSON extraction and parsing.
    """

    def parse_json(self, output: str) -> Dict[str, Any]:
        """
        Parse JSON from output.

        Args:
            output: Raw output string

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If output is not valid JSON
        """
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            # Try to extract JSON from mixed output
            return self._extract_json(output, e)

    def _extract_json(self, output: str, original_error: json.JSONDecodeError) -> Dict[str, Any]:
        """Extract JSON from mixed output."""
        json_start = output.find("{")
        json_end = output.rfind("}") + 1

        if json_start >= 0 and json_end > json_start:
            try:
                return json.loads(output[json_start:json_end])
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not parse JSON output: {original_error}")


# =============================================================================
# Error Classification
# =============================================================================

def _classify_cli_error(error_text: str) -> Optional[str]:
    """Classify CLI error for health monitoring.

    Returns:
        'rate_limit', 'auth', 'network', or None if unclassified.
    """
    text = error_text.lower()
    if any(s in text for s in ["429", "rate limit", "too many requests", "usage limit"]):
        return "rate_limit"
    if any(s in text for s in ["401", "unauthorized", "authentication", "forbidden"]):
        return "auth"
    if any(s in text for s in ["econnrefused", "timeout", "network", "connection refused"]):
        return "network"
    return None


# =============================================================================
# Main Client (Composed)
# =============================================================================

class OllamaClient(AIClient):
    """
    Client for Ollama CLI with rate limiting and fallback support.

    This class orchestrates the SRP components:
    - CLIExecutor: subprocess execution
    - RateLimiter: retry logic
    - OutputProcessor: output cleaning
    - ResponseParser: JSON parsing
    """

    def __init__(
        self,
        model: str = Models.KIMI_K25_CLOUD,
        fallback_model: str = Models.CLAUDE_SONNET,
        max_retries: int = RetryConfig.MAX_RETRIES,
        initial_retry_delay: float = RetryConfig.INITIAL_DELAY,
        verbose: bool = False,
        strict_validation: bool = False,
        cli_type: str = "ollama",
        on_cli_error: Optional[Callable[[str, str], None]] = None,
        # Dependency injection for testing
        executor: Optional[CLIExecutor] = None,
        rate_limiter: Optional[RateLimiter] = None,
        output_processor: Optional[OutputProcessor] = None,
        response_parser: Optional[ResponseParser] = None,
    ):
        """
        Initialize Ollama client.

        Args:
            model: Primary model to use
            fallback_model: Fallback Claude model when rate limited
            max_retries: Maximum retry attempts for rate limits
            initial_retry_delay: Initial delay in seconds (doubles each retry)
            verbose: Enable verbose logging
            strict_validation: Enable strict prompt validation (reject on warnings)
            executor: Optional CLIExecutor (for testing)
            rate_limiter: Optional RateLimiter (for testing)
            output_processor: Optional OutputProcessor (for testing)
            response_parser: Optional ResponseParser (for testing)
        """
        # Validate model names
        for param_name, model_value in [("model", model), ("fallback_model", fallback_model)]:
            result = validate_model_name(model_value)
            if not result.valid:
                raise ValueError(f"Invalid {param_name} name: {result.error}")
            if result.warning:
                logger.warning(result.warning)

        # Configuration
        self.model = model
        self.fallback_model = fallback_model
        self.verbose = verbose
        self.strict_validation = strict_validation
        self.cli_type = cli_type
        self.on_cli_error = on_cli_error

        # Inject or create components
        self.executor = executor or CLIExecutor(verbose=verbose)
        self.rate_limiter = rate_limiter or RateLimiter(
            max_retries=max_retries,
            initial_delay=initial_retry_delay,
        )
        self.output_processor = output_processor or OutputProcessor()
        self.response_parser = response_parser or ResponseParser()

        # Check dependencies
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check that required dependencies are installed."""
        if not self.executor.check_available("ollama"):
            raise RuntimeError(
                "Ollama is not installed. Install from: https://ollama.ai"
            )

        self._claude_available = self.executor.check_available("claude")
        if not self._claude_available:
            logger.warning("Claude CLI not found — fallback unavailable")

    def run(self, prompt: str, json_output: bool = True) -> str:
        """
        Run Ollama with automatic retry and fallback.

        Args:
            prompt: The prompt to send
            json_output: Request JSON output format

        Returns:
            Model output as string

        Raises:
            RateLimitError: If rate limit persists after all retries
            RuntimeError: If command fails for other reasons
            ValueError: If prompt validation fails in strict mode
        """
        # Validate prompt for security
        validation_result = validate_prompt(prompt, strict=self.strict_validation)
        if not validation_result.valid:
            raise ValueError(f"Invalid prompt: {validation_result.error}")

        effective_prompt = validation_result.sanitized if validation_result.sanitized else prompt

        if validation_result.warning:
            logger.warning(f"Prompt validation warning: {validation_result.warning}")

        if self.cli_type == "codex":
            return self._run_with_error_handling(
                lambda: self._run_codex(effective_prompt), "codex"
            )
        elif self.cli_type == "gemini":
            return self._run_with_error_handling(
                lambda: self._run_gemini(effective_prompt, json_output), "gemini"
            )
        elif self.cli_type == "claude":
            return self._run_with_error_handling(
                lambda: self._run_fallback(effective_prompt), "claude"
            )
        else:  # ollama (default)
            try:
                return self.rate_limiter.execute_with_retry(
                    operation=lambda: self._run_ollama(effective_prompt, json_output),
                    on_rate_limit=lambda e: logger.warning(
                        "Rate limited, falling back..." if e.permanent else "Retrying..."
                    ),
                )
            except RateLimitError:
                logger.warning("Max retries exceeded — falling back to Claude")
                return self._run_fallback(effective_prompt)

    def _run_with_error_handling(self, fn: Callable[[], str], cli_name: str) -> str:
        """Run fn, classify errors, and invoke on_cli_error callback if set."""
        try:
            return fn()
        except RuntimeError as e:
            error_type = _classify_cli_error(str(e))
            if error_type and self.on_cli_error:
                self.on_cli_error(cli_name, error_type)
            raise

    def _run_ollama(self, prompt: str, json_output: bool) -> str:
        """Execute Ollama command via stdin (not prompt-as-arg)."""
        cmd = ["ollama", "run", self.model, "--nowordwrap"]
        if json_output:
            cmd.extend(["--format", "json"])

        try:
            output = self.executor.execute(cmd, input=prompt + "\n")
            rate_limit_error = self.rate_limiter.detect_rate_limit(output)
            if rate_limit_error:
                raise rate_limit_error
            return self.output_processor.process(output)
        except RuntimeError as e:
            error_type = _classify_cli_error(str(e))
            if error_type and self.on_cli_error:
                self.on_cli_error("ollama", error_type)
            rate_limit_error = self.rate_limiter.detect_rate_limit(str(e))
            if rate_limit_error:
                raise rate_limit_error
            raise

    def _run_codex(self, prompt: str) -> str:
        """Execute Codex CLI non-interactively via stdin."""
        model = self.model if self.model in ("o3-mini", "gpt-4o") else "o3-mini"
        cmd = ["codex", "exec", "--full-auto", "-m", model]
        output = self.executor.execute(cmd, input=prompt)
        return self.output_processor.process(output)

    def _run_gemini(self, prompt: str, json_output: bool) -> str:
        """Execute Gemini CLI non-interactively."""
        model = self.model if "gemini" in self.model else "gemini-2.0-flash"
        cmd = ["gemini", "-p", prompt, "-m", model, "--yolo"]
        if json_output:
            cmd.extend(["-o", "json"])
        output = self.executor.execute(cmd)
        return self.output_processor.process(output)

    def _run_fallback(self, prompt: str) -> str:
        """Run fallback using Claude CLI."""
        if not self._claude_available:
            raise RuntimeError(
                "Rate limited and Claude CLI not available for fallback"
            )

        cmd = [
            "claude",
            "-p", prompt,
            "--model", self.fallback_model,
        ]

        if self.verbose:
            logger.info(f"Fallback: {' '.join(cmd)}")

        return self.executor.execute(cmd)

    def run_json(self, prompt: str) -> Dict[str, Any]:
        """
        Run Ollama and parse JSON output.

        Args:
            prompt: The prompt to send

        Returns:
            Parsed JSON dict

        Raises:
            ValueError: If output is not valid JSON
        """
        output = self.run(prompt, json_output=True)
        return self.response_parser.parse_json(output)

    async def run_parallel(self, prompts: List[str]) -> List[str]:
        """
        Run multiple prompts in parallel using asyncio.

        Args:
            prompts: List of prompts to run

        Returns:
            List of outputs in same order as prompts
        """
        import asyncio

        async def run_single(prompt: str) -> str:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.run(prompt)
            )

        tasks = [run_single(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)


# =============================================================================
# Factory for easy client creation
# =============================================================================

def create_client(
    model: str = Models.KIMI_K25_CLOUD,
    fallback_model: str = Models.CLAUDE_SONNET,
    verbose: bool = False,
    strict_validation: bool = False,
) -> OllamaClient:
    """
    Create an OllamaClient with default configuration.

    Args:
        model: Primary model to use
        fallback_model: Fallback Claude model
        verbose: Enable verbose logging
        strict_validation: Enable strict prompt validation

    Returns:
        Configured OllamaClient
    """
    return OllamaClient(
        model=model,
        fallback_model=fallback_model,
        verbose=verbose,
        strict_validation=strict_validation,
    )