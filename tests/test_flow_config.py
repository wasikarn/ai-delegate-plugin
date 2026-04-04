"""Tests for FlowConfig workflow modes (plan spec + additional coverage)."""
import pytest
from ai_delegate.flow_config import FlowConfig, FlowMode


class TestFlowConfig:
    def test_quick_mode(self):
        config = FlowConfig.from_mode("quick")
        assert config.mode == FlowMode.QUICK
        assert config.max_experts == 2
        assert config.force_tier == "fast"
        assert config.elicitation_enabled is False
        assert config.party_mode_enabled is False

    def test_bmad_mode(self):
        config = FlowConfig.from_mode("bmad")
        assert config.mode == FlowMode.BMAD
        assert config.max_experts is None
        assert config.force_tier is None
        assert config.elicitation_enabled is True
        assert config.party_mode_enabled is True

    def test_enterprise_mode(self):
        config = FlowConfig.from_mode("enterprise")
        assert config.mode == FlowMode.ENTERPRISE
        assert config.elicitation_enabled is True
        assert config.party_mode_enabled is True
        assert config.force_tier == "deep"

    def test_default_mode(self):
        config = FlowConfig.default()
        assert config.mode == FlowMode.STANDARD
        assert config.elicitation_enabled is False
        assert config.party_mode_enabled is False
        assert config.force_tier is None

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown flow mode"):
            FlowConfig.from_mode("turbo")

    def test_quick_mode_limits_experts(self):
        config = FlowConfig.from_mode("quick")
        experts = {"owasp": "p1", "auth": "p2", "input": "p3"}
        limited = config.limit_experts(experts)
        assert len(limited) == 2

    def test_non_quick_mode_keeps_all_experts(self):
        config = FlowConfig.from_mode("bmad")
        experts = {"owasp": "p1", "auth": "p2", "input": "p3"}
        limited = config.limit_experts(experts)
        assert len(limited) == 3

    def test_standard_mode_string(self):
        config = FlowConfig.from_mode("standard")
        assert config.mode == FlowMode.STANDARD

    def test_tier_property(self):
        assert FlowConfig.from_mode("quick").tier == "fast"
        assert FlowConfig.from_mode("enterprise").tier == "deep"
        assert FlowConfig.from_mode("standard").tier == "auto"

    def test_elicit_property(self):
        assert FlowConfig.from_mode("quick").elicit is None
        assert FlowConfig.from_mode("bmad").elicit == "all"
        assert FlowConfig.from_mode("enterprise").elicit == "red-team"
