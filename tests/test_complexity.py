"""
Unit tests for complexity detection and model selection.

Tests behavior, not implementation details.
"""

import pytest
from ai_delegate.router import (
    ComplexityLevel,
    detect_complexity,
    get_model_for_complexity,
    CLIType,
)


class TestDetectComplexity:
    """Tests for detect_complexity function."""

    # --- Empty/None content ---

    def test_empty_content_returns_low(self):
        """Empty content should return LOW complexity."""
        result = detect_complexity("", "audit")
        assert result == ComplexityLevel.LOW

    def test_none_content_returns_low(self):
        """None content should return LOW complexity."""
        result = detect_complexity(None, "audit")
        assert result == ComplexityLevel.LOW

    # --- Architecture tasks ---

    def test_architecture_always_high(self):
        """Architecture tasks should always be HIGH complexity."""
        small_code = "def foo(): pass"  # Very small
        result = detect_complexity(small_code, "architecture")
        assert result == ComplexityLevel.HIGH

    def test_architecture_large_high(self):
        """Large architecture tasks should be HIGH."""
        large_code = "\n".join([f"def func_{i}(): pass" for i in range(100)])
        result = detect_complexity(large_code, "architecture")
        assert result == ComplexityLevel.HIGH

    # --- Audit tasks ---

    def test_audit_small_code_low(self):
        """Small code (<100 lines) should be LOW complexity for audit."""
        small_code = "\n".join([f"# line {i}" for i in range(50)])
        result = detect_complexity(small_code, "audit")
        assert result == ComplexityLevel.LOW

    def test_audit_medium_code_medium(self):
        """Medium code (100-500 lines) should be MEDIUM complexity."""
        medium_code = "\n".join([f"# line {i}" for i in range(200)])
        result = detect_complexity(medium_code, "audit")
        assert result == ComplexityLevel.MEDIUM

    def test_audit_large_code_high(self):
        """Large code (>500 lines) should be HIGH complexity."""
        large_code = "\n".join([f"# line {i}" for i in range(600)])
        result = detect_complexity(large_code, "audit")
        assert result == ComplexityLevel.HIGH

    # --- Other task types ---

    def test_analyze_small_medium(self):
        """Non-audit tasks use standard complexity rules."""
        small_code = "\n".join([f"# line {i}" for i in range(50)])
        result = detect_complexity(small_code, "analyze")
        assert result == ComplexityLevel.MEDIUM  # <500 lines

    def test_analyze_large_high(self):
        """Large analyze tasks should be HIGH."""
        large_code = "\n".join([f"# line {i}" for i in range(600)])
        result = detect_complexity(large_code, "analyze")
        assert result == ComplexityLevel.HIGH

    # --- Edge cases ---

    def test_exactly_100_lines(self):
        """Code with exactly 100 lines (boundary)."""
        code = "\n".join([f"# line {i}" for i in range(100)])
        result = detect_complexity(code, "audit")
        # 100 lines is >= 100, so MEDIUM
        assert result == ComplexityLevel.MEDIUM

    def test_exactly_500_lines(self):
        """Code with exactly 500 lines (boundary)."""
        code = "\n".join([f"# line {i}" for i in range(500)])
        result = detect_complexity(code, "analyze")
        # 500 lines is >= 500, so HIGH
        assert result == ComplexityLevel.HIGH


class TestGetModelForComplexity:
    """Tests for get_model_for_complexity function."""

    # --- Default mode (non-budget) ---

    def test_low_complexity_returns_haiku(self):
        """LOW complexity should return haiku model."""
        config = get_model_for_complexity(ComplexityLevel.LOW)
        assert config["model"] == "haiku"
        assert config["cli"] == CLIType.CLAUDE
        assert config["max_tokens"] == 2000

    def test_medium_complexity_returns_glm(self):
        """MEDIUM complexity should return glm-5:cloud model."""
        config = get_model_for_complexity(ComplexityLevel.MEDIUM)
        assert config["model"] == "glm-5:cloud"
        assert config["cli"] == CLIType.OLLAMA
        assert config["max_tokens"] == 4000

    def test_high_complexity_returns_sonnet(self):
        """HIGH complexity should return sonnet model."""
        config = get_model_for_complexity(ComplexityLevel.HIGH)
        assert config["model"] == "sonnet"
        assert config["cli"] == CLIType.CLAUDE
        assert config["max_tokens"] == 8000

    # --- Budget mode ---

    def test_low_complexity_budget_mode(self):
        """LOW complexity with budget mode should return deepseek-chat."""
        config = get_model_for_complexity(ComplexityLevel.LOW, budget_mode=True)
        assert config["model"] == "deepseek-chat"
        assert config["cli"] == CLIType.DEEPSEEK
        assert "Budget mode" in config["reason"]

    def test_medium_complexity_budget_mode(self):
        """MEDIUM complexity with budget mode should return deepseek-chat."""
        config = get_model_for_complexity(ComplexityLevel.MEDIUM, budget_mode=True)
        assert config["model"] == "deepseek-chat"
        assert config["cli"] == CLIType.DEEPSEEK

    def test_high_complexity_budget_mode(self):
        """HIGH complexity with budget mode should return deepseek-reasoner."""
        config = get_model_for_complexity(ComplexityLevel.HIGH, budget_mode=True)
        assert config["model"] == "deepseek-reasoner"
        assert config["cli"] == CLIType.DEEPSEEK

    # --- Unknown complexity ---

    def test_unknown_complexity_returns_medium_default(self):
        """Unknown complexity should default to MEDIUM."""
        # Pass an invalid value - should return MEDIUM default
        config = get_model_for_complexity("invalid")  # type: ignore
        assert config["model"] == "glm-5:cloud"
        assert config["max_tokens"] == 4000

    # --- Config immutability ---

    def test_config_has_required_keys(self):
        """Returned config should have all required keys."""
        for level in [ComplexityLevel.LOW, ComplexityLevel.MEDIUM, ComplexityLevel.HIGH]:
            config = get_model_for_complexity(level)
            assert "model" in config
            assert "cli" in config
            assert "max_tokens" in config
            assert "reason" in config


class TestComplexityLevelEnum:
    """Tests for ComplexityLevel enum."""

    def test_low_value(self):
        """LOW should have value 'low'."""
        assert ComplexityLevel.LOW.value == "low"

    def test_medium_value(self):
        """MEDIUM should have value 'medium'."""
        assert ComplexityLevel.MEDIUM.value == "medium"

    def test_high_value(self):
        """HIGH should have value 'high'."""
        assert ComplexityLevel.HIGH.value == "high"

    def test_all_levels_defined(self):
        """All complexity levels should be defined."""
        levels = list(ComplexityLevel)
        assert len(levels) == 3
        assert ComplexityLevel.LOW in levels
        assert ComplexityLevel.MEDIUM in levels
        assert ComplexityLevel.HIGH in levels