"""
Tests for SmartRouter and CLI selection logic.

Covers:
- CLI detection and availability
- Task-based CLI selection
- Fallback chain ordering
- Model selection for complexity
"""

import pytest
from unittest.mock import patch, MagicMock
from ai_delegate.router import SmartRouter, detect_complexity, get_model_for_complexity, CLIType, ComplexityLevel
from ai_delegate.constants import Models, TaskTypes, ComplexityThresholds


class TestCLIDetection:
    """Tests for CLI availability detection."""

    @patch('ai_delegate.router.shutil.which')
    def test_detect_clis_all_available(self, mock_which):
        """All CLIs available."""
        mock_which.return_value = '/usr/bin/ollama'  # All CLIs found
        router = SmartRouter()

        available = router.get_available_clis()
        assert CLIType.OLLAMA in available
        assert CLIType.GEMINI in available
        assert CLIType.CODEX in available
        assert CLIType.CLAUDE in available

    @patch('ai_delegate.router.shutil.which')
    def test_detect_clis_partial_availability(self, mock_which):
        """Only some CLIs available."""
        def which_side_effect(cmd):
            if cmd == 'ollama':
                return '/usr/bin/ollama'
            elif cmd == 'claude':
                return '/usr/bin/claude'
            return None

        mock_which.side_effect = which_side_effect
        router = SmartRouter()

        available = router.get_available_clis()
        assert CLIType.OLLAMA in available
        assert CLIType.CLAUDE in available
        assert CLIType.GEMINI not in available
        assert CLIType.CODEX not in available

    @patch('ai_delegate.router.shutil.which')
    def test_detect_clis_none_available(self, mock_which):
        """No CLIs available."""
        mock_which.return_value = None
        router = SmartRouter()

        available = router.get_available_clis()
        assert len(available) == 0


class TestSelectCLIForTask:
    """Tests for CLI selection based on task type."""

    @patch('ai_delegate.router.shutil.which')
    def test_select_cli_for_audit(self, mock_which):
        """Audit task should prefer Ollama."""
        mock_which.return_value = '/usr/bin/ollama'
        router = SmartRouter()

        config, model = router.select_cli_for_task(TaskTypes.AUDIT)

        assert config.cli_type == CLIType.OLLAMA
        assert model == Models.GLM_5_CLOUD

    @patch('ai_delegate.router.shutil.which')
    def test_select_cli_for_architecture(self, mock_which):
        """Architecture task should prefer Codex."""
        def which_side_effect(cmd):
            if cmd in ('ollama', 'codex'):
                return f'/usr/bin/{cmd}'
            return None

        mock_which.side_effect = which_side_effect
        router = SmartRouter()

        config, model = router.select_cli_for_task(TaskTypes.ARCHITECTURE)

        assert config.cli_type == CLIType.CODEX

    @patch('ai_delegate.router.shutil.which')
    def test_select_cli_fallback_chain(self, mock_which):
        """Should fallback through priority chain."""
        def which_side_effect(cmd):
            if cmd == 'claude':
                return '/usr/bin/claude'
            return None

        mock_which.side_effect = which_side_effect
        router = SmartRouter()

        config, model = router.select_cli_for_task(TaskTypes.AUDIT)

        # Should fallback to Claude when Ollama not available
        assert config.cli_type == CLIType.CLAUDE

    @patch('ai_delegate.router.shutil.which')
    def test_select_cli_no_available(self, mock_which):
        """No CLI available raises error."""
        mock_which.return_value = None
        router = SmartRouter()

        with pytest.raises(RuntimeError, match="No AI CLI available"):
            router.select_cli_for_task(TaskTypes.AUDIT)

    @patch('ai_delegate.router.shutil.which')
    def test_select_cli_with_prefer_structured_output(self, mock_which):
        """Should prefer CLI with structured output when flag is True."""
        mock_which.return_value = '/usr/bin/ollama'
        router = SmartRouter()

        config, model = router.select_cli_for_task(
            TaskTypes.AUDIT,
            prefer_structured_output=True
        )

        assert config.cli_type == CLIType.OLLAMA


class TestComplexityDetection:
    """Tests for content complexity detection."""

    def test_detect_complexity_low(self):
        """Content under 100 lines is LOW complexity."""
        content = "print('hello')\n" * 50  # 50 lines

        complexity = detect_complexity(content, TaskTypes.AUDIT)

        assert complexity == ComplexityLevel.LOW

    def test_detect_complexity_medium(self):
        """Content 100-500 lines is MEDIUM complexity."""
        content = "print('hello')\n" * 200  # 200 lines

        complexity = detect_complexity(content, TaskTypes.ANALYZE)

        assert complexity == ComplexityLevel.MEDIUM

    def test_detect_complexity_high(self):
        """Content over 500 lines is HIGH complexity."""
        content = "print('hello')\n" * 600  # 600 lines

        complexity = detect_complexity(content, TaskTypes.REVIEW)

        assert complexity == ComplexityLevel.HIGH

    def test_detect_complexity_architecture_always_high(self):
        """Architecture tasks are always HIGH complexity."""
        content = "print('hello')\n" * 10  # Only 10 lines

        complexity = detect_complexity(content, TaskTypes.ARCHITECTURE)

        assert complexity == ComplexityLevel.HIGH

    def test_detect_complexity_audit_small_is_low(self):
        """Audit tasks with small content are LOW complexity."""
        content = "def vulnerable():\n    pass\n"

        complexity = detect_complexity(content, TaskTypes.AUDIT)

        assert complexity == ComplexityLevel.LOW


class TestModelForComplexity:
    """Tests for model selection based on complexity."""

    def test_get_model_for_low_complexity(self):
        """LOW complexity should use haiku."""
        config = get_model_for_complexity(ComplexityLevel.LOW)

        assert config["model"] == Models.CLAUDE_HAIKU

    def test_get_model_for_medium_complexity(self):
        """MEDIUM complexity should use glm-5:cloud."""
        config = get_model_for_complexity(ComplexityLevel.MEDIUM)

        assert config["model"] == Models.GLM_5_CLOUD

    def test_get_model_for_high_complexity(self):
        """HIGH complexity should use sonnet."""
        config = get_model_for_complexity(ComplexityLevel.HIGH)

        assert config["model"] == Models.CLAUDE_SONNET

    def test_get_model_budget_mode_low(self):
        """Budget mode LOW should use glm-5:cloud."""
        config = get_model_for_complexity(ComplexityLevel.LOW, budget_mode=True)

        assert config["model"] == Models.GLM_5_CLOUD

    def test_get_model_budget_mode_high(self):
        """Budget mode HIGH should use kimi-k2.5:cloud."""
        config = get_model_for_complexity(ComplexityLevel.HIGH, budget_mode=True)

        assert config["model"] == Models.KIMI_K25_CLOUD


class TestFallbackChain:
    """Tests for CLI fallback chain."""

    @patch('ai_delegate.router.shutil.which')
    def test_fallback_chain_order(self, mock_which):
        """Fallback chain should follow priority order."""
        mock_which.return_value = '/usr/bin/ollama'
        router = SmartRouter()

        chain = router.get_fallback_chain(TaskTypes.AUDIT)

        # Ollama -> Gemini -> Codex -> Claude
        assert chain[0][0] == CLIType.OLLAMA
        assert chain[1][0] == CLIType.GEMINI
        assert chain[2][0] == CLIType.CODEX
        assert chain[3][0] == CLIType.CLAUDE

    @patch('ai_delegate.router.shutil.which')
    def test_fallback_chain_gemini_available(self, mock_which):
        """Fallback chain with Gemini available."""
        mock_which.return_value = '/usr/bin/gemini'
        router = SmartRouter()

        chain = router.get_fallback_chain(TaskTypes.ANALYZE)

        # Should include all available CLIs
        assert len(chain) > 0

    @patch('ai_delegate.router.shutil.which')
    def test_fallback_chain_claude_is_last(self, mock_which):
        """Claude should always be last in fallback chain."""
        mock_which.return_value = '/usr/bin/claude'
        router = SmartRouter()

        chain = router.get_fallback_chain(TaskTypes.AUDIT)
        # Claude is last in priority order
        assert chain[-1][0] == CLIType.CLAUDE


class TestRouterSingleton:
    """Tests for global router singleton."""

    @patch('ai_delegate.router.shutil.which')
    def test_get_router_returns_singleton(self, mock_which):
        """get_router should return the same instance."""
        mock_which.return_value = '/usr/bin/ollama'

        from ai_delegate.router import get_router, _reset_router

        _reset_router()  # Clear any existing singleton

        router1 = get_router()
        router2 = get_router()

        assert router1 is router2

    @patch('ai_delegate.router.shutil.which')
    def test_reset_router_clears_singleton(self, mock_which):
        """_reset_router should clear the singleton."""
        mock_which.return_value = '/usr/bin/ollama'

        from ai_delegate.router import get_router, _reset_router

        _reset_router()
        router1 = get_router()
        _reset_router()
        router2 = get_router()

        # After reset, should be different instances
        assert router1 is not router2