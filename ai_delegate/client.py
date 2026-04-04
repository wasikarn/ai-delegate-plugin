"""
AI Client with rate limiting and fallback support.

Supports multiple backends: ollama (default), gemini, codex.
"""

import subprocess
import json
import time
import shutil
import logging
from typing import Dict, Any, List
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class RateLimitError(Exception):
    """Rate limit error from AI API."""
    message: str
    retry_after: int = 2
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


class OllamaClient(AIClient):
    """
    Client for Ollama CLI with rate limiting and fallback support.

    Features:
    - Automatic retry with exponential backoff for rate limits
    - Fallback to Claude CLI when rate limit exceeded
    - Structured JSON output support
    - Verbose logging option
    """

    def __init__(
        self,
        model: str = "kimi-k2.5:cloud",
        fallback_model: str = "sonnet",
        max_retries: int = 3,
        initial_retry_delay: float = 2.0,
        verbose: bool = False,
    ):
        """
        Initialize Ollama client.

        Args:
            model: Primary model to use
            fallback_model: Fallback Claude model when rate limited
            max_retries: Maximum retry attempts for rate limits
            initial_retry_delay: Initial delay in seconds (doubles each retry)
            verbose: Enable verbose logging
        """
        self.model = model
        self.fallback_model = fallback_model
        self.max_retries = max_retries
        self.initial_retry_delay = initial_retry_delay
        self.verbose = verbose
        self._check_dependencies()

    def _check_dependencies(self) -> None:
        """Check that required dependencies are installed."""
        if not shutil.which("ollama"):
            raise RuntimeError(
                "Ollama is not installed. Install from: https://ollama.ai"
            )

        # Check Claude CLI for fallback
        self._claude_available = shutil.which("claude") is not None
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
        """
        output_arg = "--format" if json_output else ""

        # Try with retries
        delay = self.initial_retry_delay

        for attempt in range(self.max_retries):
            try:
                return self._run_ollama(prompt, self.model, output_arg)
            except RateLimitError as e:
                if e.permanent:
                    # Usage limit - try fallback
                    logger.warning("Usage limit exceeded — falling back to Claude")
                    return self._run_fallback(prompt)

                # Temporary rate limit - retry
                logger.warning(
                    f"Rate limited (429), retrying in {delay}s... "
                    f"(attempt {attempt + 1}/{self.max_retries})"
                )
                time.sleep(delay)
                delay *= 2

        # All retries failed - try fallback
        logger.warning(f"Max retries ({self.max_retries}) exceeded — falling back to Claude")
        return self._run_fallback(prompt)

    def _run_ollama(
        self,
        prompt: str,
        model: str,
        output_arg: str,
    ) -> str:
        """
        Execute Ollama command.

        Args:
            prompt: The prompt to send
            model: Model to use
            output_arg: Output format argument

        Returns:
            Model output

        Raises:
            RateLimitError: If rate limited
            RuntimeError: If command fails
        """
        cmd = ["ollama", "run", model]
        if output_arg:
            cmd.append(output_arg)
        cmd.append(prompt)

        if self.verbose:
            logger.info(f"Running: {' '.join(cmd[:3])}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            if result.returncode != 0:
                # Check for rate limit
                output = result.stderr + result.stdout
                if self._is_rate_limited(output):
                    raise RateLimitError(
                        message="Rate limit exceeded",
                        permanent=self._is_permanent_rate_limit(output),
                    )
                raise RuntimeError(f"Ollama failed: {result.stderr}")

            # Strip thinking prefix if present
            return self._strip_thinking(result.stdout)

        except subprocess.TimeoutExpired:
            raise RuntimeError("Ollama command timed out after 5 minutes")

    def _run_fallback(self, prompt: str) -> str:
        """
        Run fallback using Claude CLI.

        Args:
            prompt: The prompt to send

        Returns:
            Model output

        Raises:
            RuntimeError: If fallback not available or fails
        """
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

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )

            if result.returncode != 0:
                raise RuntimeError(f"Claude fallback failed: {result.stderr}")

            return result.stdout

        except subprocess.TimeoutExpired:
            raise RuntimeError("Claude fallback timed out after 5 minutes")

    def _is_rate_limited(self, output: str) -> bool:
        """Check if output indicates rate limit."""
        indicators = ["429", "rate limit", "Too Many Requests", "usage limit"]
        return any(indicator in output for indicator in indicators)

    def _is_permanent_rate_limit(self, output: str) -> bool:
        """Check if rate limit is permanent (usage limit exceeded)."""
        permanent_indicators = ["usage limit", "quota", "exceeded"]
        return any(indicator in output for indicator in permanent_indicators)

    def _strip_thinking(self, output: str) -> str:
        """Strip thinking prefix from model output."""
        # Slice first for memory efficiency, then filter
        lines = output.split("\n")[:150]  # Take extra for filtering margin
        filtered = [
            line for line in lines
            if not line.startswith(("Thinking", "The user wants"))
            and not line.strip().startswith("Identify")
        ]
        return "\n".join(filtered[:100])

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
        try:
            return json.loads(output)
        except json.JSONDecodeError as e:
            # Try to extract JSON from mixed output
            json_start = output.find("{")
            json_end = output.rfind("}") + 1
            if json_start >= 0 and json_end > json_start:
                try:
                    return json.loads(output[json_start:json_end])
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Could not parse JSON output: {e}")

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
            # Run in executor since subprocess is blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self.run(prompt)
            )

        tasks = [run_single(prompt) for prompt in prompts]
        return await asyncio.gather(*tasks)