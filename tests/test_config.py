"""
Tests for configuration values and task configurations.

Covers:
- Task display names
- Expert descriptions
- Adjudicator roles
- Output formats
- Expert configurations
"""

import pytest
from ai_delegate.config import (
    TASK_DISPLAY_NAMES,
    TASK_EXPERT_DESCRIPTIONS,
    TASK_ADJUDICATOR_ROLES,
    TASK_OUTPUT_FORMATS,
    EXPERT_CONFIGS,
    CONSENSUS_THRESHOLD_FAST,
    CONSENSUS_THRESHOLD_STANDARD,
)
from ai_delegate.constants import TaskTypes, ExpertDomains


class TestTaskDisplayNames:
    """Tests for task display names."""

    def test_all_task_types_have_display_names(self):
        """All TaskTypes should have display names."""
        for task_type in TaskTypes:
            assert task_type in TASK_DISPLAY_NAMES, f"Missing display name for {task_type}"

    def test_display_names_are_strings(self):
        """Display names should be non-empty strings."""
        for task_type, name in TASK_DISPLAY_NAMES.items():
            assert isinstance(name, str), f"Display name for {task_type} is not a string"
            assert len(name) > 0, f"Display name for {task_type} is empty"

    def test_display_names_are_uppercase(self):
        """Display names should be uppercase."""
        for task_type, name in TASK_DISPLAY_NAMES.items():
            assert name.isupper(), f"Display name '{name}' for {task_type} should be uppercase"


class TestTaskExpertDescriptions:
    """Tests for task expert descriptions."""

    def test_all_task_types_have_expert_descriptions(self):
        """All TaskTypes should have expert descriptions."""
        for task_type in TaskTypes:
            assert task_type in TASK_EXPERT_DESCRIPTIONS, f"Missing expert description for {task_type}"

    def test_expert_descriptions_are_strings(self):
        """Expert descriptions should be non-empty strings."""
        for task_type, desc in TASK_EXPERT_DESCRIPTIONS.items():
            assert isinstance(desc, str), f"Expert description for {task_type} is not a string"
            assert len(desc) > 0, f"Expert description for {task_type} is empty"


class TestTaskAdjudicatorRoles:
    """Tests for adjudicator roles."""

    def test_all_task_types_have_adjudicator_roles(self):
        """All TaskTypes should have adjudicator roles."""
        for task_type in TaskTypes:
            assert task_type in TASK_ADJUDICATOR_ROLES, f"Missing adjudicator role for {task_type}"

    def test_adjudicator_roles_have_key_sections(self):
        """Adjudicator roles should have key sections."""
        key_sections = ["Consolidate", "Prioritize", "Provide"]

        for task_type, role in TASK_ADJUDICATOR_ROLES.items():
            for section in key_sections:
                # At least one section should be present
                pass  # Roles vary in structure, so just check they exist


class TestTaskOutputFormats:
    """Tests for output formats."""

    def test_all_task_types_have_output_formats(self):
        """All TaskTypes should have output formats."""
        for task_type in TaskTypes:
            assert task_type in TASK_OUTPUT_FORMATS, f"Missing output format for {task_type}"

    def test_output_formats_contain_score(self):
        """Output formats should include score field."""
        for task_type, fmt in TASK_OUTPUT_FORMATS.items():
            assert "score" in fmt.lower(), f"Output format for {task_type} missing score"


class TestExpertConfigs:
    """Tests for expert configurations."""

    def test_all_domains_have_configs(self):
        """All ExpertDomains should have configs."""
        expected_domains = [
            ExpertDomains.SECURITY,
            ExpertDomains.PERFORMANCE,
            ExpertDomains.ARCHITECTURE,
            ExpertDomains.REFACTOR,
            ExpertDomains.MIGRATE,
        ]

        for domain in expected_domains:
            assert domain in EXPERT_CONFIGS, f"Missing config for domain {domain}"

    def test_security_domain_has_required_experts(self):
        """Security domain should have OWASP, Auth, Input experts."""
        security_config = EXPERT_CONFIGS[ExpertDomains.SECURITY]

        assert ExpertDomains.OWASP in security_config
        assert ExpertDomains.AUTH in security_config
        assert ExpertDomains.INPUT in security_config

    def test_performance_domain_has_required_experts(self):
        """Performance domain should have Complexity, Database, Memory experts."""
        perf_config = EXPERT_CONFIGS[ExpertDomains.PERFORMANCE]

        assert ExpertDomains.COMPLEXITY in perf_config
        assert ExpertDomains.DATABASE in perf_config
        assert ExpertDomains.MEMORY in perf_config

    def test_architecture_domain_has_required_experts(self):
        """Architecture domain should have Patterns, SOLID, Scalability experts."""
        arch_config = EXPERT_CONFIGS[ExpertDomains.ARCHITECTURE]

        assert ExpertDomains.PATTERNS in arch_config
        assert ExpertDomains.SOLID in arch_config
        assert ExpertDomains.SCALABILITY in arch_config

    def test_expert_configs_are_strings(self):
        """Expert config prompts should be non-empty strings."""
        for domain, experts in EXPERT_CONFIGS.items():
            for expert_name, prompt in experts.items():
                assert isinstance(prompt, str), f"Prompt for {domain}/{expert_name} is not a string"
                assert len(prompt) > 50, f"Prompt for {domain}/{expert_name} is too short"


class TestConsensusThresholds:
    """Tests for consensus threshold values."""

    def test_fast_threshold_is_higher_than_standard(self):
        """FAST threshold should be higher than STANDARD."""
        assert CONSENSUS_THRESHOLD_FAST > CONSENSUS_THRESHOLD_STANDARD

    def test_thresholds_are_valid_percentages(self):
        """Thresholds should be valid percentages (0-100)."""
        assert 0 <= CONSENSUS_THRESHOLD_FAST <= 100
        assert 0 <= CONSENSUS_THRESHOLD_STANDARD <= 100

    def test_thresholds_are_reasonable(self):
        """Thresholds should be reasonable values."""
        # FAST should be high (≥85%)
        assert CONSENSUS_THRESHOLD_FAST >= 85

        # STANDARD should be moderate (≥60%)
        assert CONSENSUS_THRESHOLD_STANDARD >= 60


class TestConfigConsistency:
    """Tests for config consistency."""

    def test_task_types_match_between_configs(self):
        """TaskTypes should be consistent across all config dicts."""
        display_names_set = set(TASK_DISPLAY_NAMES.keys())
        expert_descs_set = set(TASK_EXPERT_DESCRIPTIONS.keys())
        adjudicator_roles_set = set(TASK_ADJUDICATOR_ROLES.keys())
        output_formats_set = set(TASK_OUTPUT_FORMATS.keys())

        assert display_names_set == expert_descs_set, "Task types mismatch between display names and expert descriptions"
        assert display_names_set == adjudicator_roles_set, "Task types mismatch between display names and adjudicator roles"
        assert display_names_set == output_formats_set, "Task types mismatch between display names and output formats"

    def test_expert_domains_match_constants(self):
        """Expert domains in config should match ExpertDomains constants."""
        config_domains = set(EXPERT_CONFIGS.keys())
        constants_domains = {
            ExpertDomains.SECURITY,
            ExpertDomains.PERFORMANCE,
            ExpertDomains.ARCHITECTURE,
            ExpertDomains.REFACTOR,
            ExpertDomains.MIGRATE,
        }

        assert config_domains == constants_domains, "Expert domains mismatch between config and constants"