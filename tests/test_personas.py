"""Tests for Agent Personas (named expert identities)."""
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import ExpertRunner
from ai_delegate.models import TaskConfig
from ai_delegate.config import EXPERT_PERSONAS


class TestAgentPersonas:
    def test_expert_personas_defined_for_all_domains(self):
        """All expert domains must have persona entries."""
        required = ["OWASP", "AUTH", "INPUT", "COMPLEXITY", "DATABASE", "MEMORY",
                    "PATTERNS", "SOLID", "SCALABILITY"]
        for key in required:
            assert key in EXPERT_PERSONAS, f"Missing persona for {key}"

    def test_persona_has_required_fields(self):
        """Each persona must have name, title, and style fields."""
        for key, persona in EXPERT_PERSONAS.items():
            assert "name" in persona, f"{key} missing 'name'"
            assert "title" in persona, f"{key} missing 'title'"
            assert "style" in persona, f"{key} missing 'style'"

    def test_expert_result_includes_persona_name(self):
        """ExpertResult should carry persona_name from the runner."""
        client = MagicMock()
        client.run_json.return_value = {"findings": []}

        config = TaskConfig(
            task_type="audit",
            experts={"OWASP": "You are OWASP expert."},
            display_name="AUDIT",
            description="",
            adjudicator_role="",
            output_format="",
            default_model="glm-5:cloud",
        )
        runner = ExpertRunner(client=client, task_config=config)
        result = runner._run_single_expert("OWASP", "You are OWASP expert.", "code")

        assert result.persona_name is not None
        assert result.persona_name != ""

    def test_unknown_expert_has_no_persona(self):
        """Unknown expert domain gets None persona_name."""
        client = MagicMock()
        client.run_json.return_value = {"findings": []}

        config = TaskConfig(
            task_type="audit",
            experts={"CUSTOM": "You are custom expert."},
            display_name="AUDIT",
            description="",
            adjudicator_role="",
            output_format="",
            default_model="glm-5:cloud",
        )
        runner = ExpertRunner(client=client, task_config=config)
        result = runner._run_single_expert("CUSTOM", "You are custom expert.", "code")

        assert result.persona_name is None
