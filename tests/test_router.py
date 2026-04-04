"""
Tests for SmartRouter and CLI selection logic.

Covers:
- CLI detection and availability
- Task-based CLI selection
- Fallback chain ordering
- Model selection for complexity
"""

import time
import pytest
from unittest.mock import patch, MagicMock
from ai_delegate.router import CliHealthMonitor, SmartRouter, detect_complexity, get_model_for_complexity, CLIType, ComplexityLevel
from ai_delegate.constants import Models, TaskTypes, ComplexityThresholds, HealthConfig, AdaptiveConfig
from ai_delegate.memory import AnalysisMemory, MemoryRecord


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


# =============================================================================
# Task 4: CliHealthMonitor + health gate in select_cli_for_task
# =============================================================================

class TestCliHealthMonitor:
    def test_new_cli_is_not_degraded(self):
        monitor = CliHealthMonitor()
        assert not monitor.is_degraded(CLIType.OLLAMA)

    def test_mark_failed_degrades_cli(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.OLLAMA, "rate_limit")
        assert monitor.is_degraded(CLIType.OLLAMA)

    def test_rate_limit_ttl_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "rate_limit")
        assert monitor.is_degraded(CLIType.CODEX)
        monitor._degraded[CLIType.CODEX] = (
            time.monotonic() - HealthConfig.RATE_LIMIT_TTL - 1,
            "rate_limit",
        )
        assert not monitor.is_degraded(CLIType.CODEX)

    def test_auth_degradation_never_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.GEMINI, "auth")
        monitor._degraded[CLIType.GEMINI] = (
            time.monotonic() - 10_000,
            "auth",
        )
        assert monitor.is_degraded(CLIType.GEMINI)

    def test_network_ttl_expires(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CLAUDE, "network")
        monitor._degraded[CLIType.CLAUDE] = (
            time.monotonic() - HealthConfig.NETWORK_TTL - 1,
            "network",
        )
        assert not monitor.is_degraded(CLIType.CLAUDE)

    def test_clear_removes_degraded_state(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.OLLAMA, "auth")
        assert monitor.is_degraded(CLIType.OLLAMA)
        monitor.clear(CLIType.OLLAMA)
        assert not monitor.is_degraded(CLIType.OLLAMA)

    def test_clear_nonexistent_cli_is_noop(self):
        monitor = CliHealthMonitor()
        monitor.clear(CLIType.OLLAMA)  # Should not raise

    def test_should_warn_auth_first_time(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "auth")
        assert monitor.should_warn_auth(CLIType.CODEX)

    def test_should_warn_auth_only_once(self):
        monitor = CliHealthMonitor()
        monitor.mark_failed(CLIType.CODEX, "auth")
        monitor.should_warn_auth(CLIType.CODEX)  # consume first warning
        assert not monitor.should_warn_auth(CLIType.CODEX)


class TestSmartRouterHealthGate:
    @patch("ai_delegate.router.shutil.which")
    def test_degraded_cli_is_skipped_in_routing(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"  # all available
        router = SmartRouter()
        router.health_monitor.mark_failed(CLIType.OLLAMA, "auth")
        config, model = router.select_cli_for_task("audit")
        assert config.cli_type != CLIType.OLLAMA

    @patch("ai_delegate.router.shutil.which")
    def test_all_degraded_raises_runtime_error(self, mock_which):
        mock_which.return_value = "/usr/bin/tool"
        router = SmartRouter()
        for cli in CLIType:
            router.health_monitor.mark_failed(cli, "auth")
        with pytest.raises(RuntimeError, match="No AI CLI available"):
            router.select_cli_for_task("audit")


# =============================================================================
# Task 5: 3-phase adaptive routing
# =============================================================================

class TestAdaptiveRouting:
    @pytest.fixture
    def memory(self, tmp_path):
        return AnalysisMemory(db_path=tmp_path / "test.db")

    @pytest.fixture
    def router(self):
        with patch("ai_delegate.router.shutil.which", return_value="/usr/bin/tool"):
            return SmartRouter()

    def _add_run(self, memory, task_type, cli_name):
        record = MemoryRecord(
            file_path="src/x.py", task_type=task_type,
            consensus_score=0.75, finding_count=1,
            critical_count=0, high_count=1, findings_summary="X",
        )
        run_id = memory.store(record)
        memory.record_cli_run(run_id, cli_name)
        return run_id

    def test_no_adaptive_uses_static_priority(self, router, memory):
        config, _ = router.select_cli_for_task(
            "audit", memory=memory, no_adaptive=True
        )
        assert config.cli_type == CLIType.OLLAMA

    def test_phase1_priors_select_higher_win_rate(self, router, memory):
        # Claude prior for audit = 0.80, ollama = 0.70
        config, _ = router.select_cli_for_task("audit", memory=memory)
        assert config.cli_type == CLIType.CLAUDE

    def test_phase2_winning_streak_locks_cli(self, router, memory):
        for _ in range(3):
            self._add_run(memory, "refactor", "ollama")
        config, _ = router.select_cli_for_task("refactor", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_phase2_losing_streak_skips_current_best(self, router, memory):
        for _ in range(3):
            self._add_run(memory, "architecture", "gemini")
        # codex is current_best for architecture (prior 0.80) but wasn't used → skip
        config, _ = router.select_cli_for_task("architecture", memory=memory)
        assert config.cli_type != CLIType.CODEX

    def test_anti_thrash_guard_holds_static(self, router, memory):
        self._add_run(memory, "audit", "ollama")
        self._add_run(memory, "audit", "gemini")
        self._add_run(memory, "audit", "codex")
        # 3 distinct CLIs → hold static (ollama for audit per _task_priority_map)
        config, _ = router.select_cli_for_task("audit", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_phase3_win_rate_override(self, router, memory):
        # Add claude losses first (so they're not the most recent)
        for _ in range(5):
            run_id = self._add_run(memory, "audit", "claude")
            memory.store_rating(run_id, 0)
        # Add ollama wins last (most recent = last 3 are ollama, no losing streak)
        for _ in range(15):
            run_id = self._add_run(memory, "audit", "ollama")
            memory.store_rating(run_id, 1)
        config, _ = router.select_cli_for_task("audit", memory=memory)
        assert config.cli_type == CLIType.OLLAMA

    def test_no_memory_uses_static_priority(self, router):
        config, _ = router.select_cli_for_task("audit")
        assert config.cli_type == CLIType.OLLAMA