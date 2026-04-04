"""Tests for FlowConfig workflow modes."""
import pytest
from ai_delegate.flow_config import FlowConfig, FlowMode


class TestFlowMode:
    def test_all_modes_defined(self):
        assert set(FlowMode.ALL) == {"quick", "standard", "bmad", "enterprise"}


class TestFlowConfig:
    def test_quick_mode(self):
        cfg = FlowConfig.from_mode(FlowMode.QUICK)
        assert cfg.mode == "quick"
        assert cfg.tier == "fast"
        assert cfg.elicit is None
        assert cfg.debate_rounds == 0

    def test_standard_mode(self):
        cfg = FlowConfig.from_mode(FlowMode.STANDARD)
        assert cfg.mode == "standard"
        assert cfg.tier == "standard"
        assert cfg.elicit is None
        assert cfg.debate_rounds == 1

    def test_bmad_mode(self):
        cfg = FlowConfig.from_mode(FlowMode.BMAD)
        assert cfg.mode == "bmad"
        assert cfg.tier == "deep"
        assert cfg.elicit == "all"
        assert cfg.debate_rounds == 2

    def test_enterprise_mode(self):
        cfg = FlowConfig.from_mode(FlowMode.ENTERPRISE)
        assert cfg.mode == "enterprise"
        assert cfg.tier == "deep"
        assert cfg.elicit == "red-team"
        assert cfg.debate_rounds == 3

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown flow mode"):
            FlowConfig.from_mode("invalid-mode")

    def test_all_modes_have_description(self):
        for mode in FlowMode.ALL:
            cfg = FlowConfig.from_mode(mode)
            assert cfg.description
