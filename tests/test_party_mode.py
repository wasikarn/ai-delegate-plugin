"""Tests for PartyDebate (multi-turn adversarial debate)."""
from unittest.mock import MagicMock
from ai_delegate.party_mode import PartyDebate
from ai_delegate.models import ExpertResult, Finding, TaskConfig, Verdict


def make_config():
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "OWASP prompt", "AUTH": "AUTH prompt"},
        display_name="AUDIT",
        description="",
        adjudicator_role="Synthesize the debate into final findings.",
        output_format="findings array",
        default_model="glm-5:cloud",
    )


class TestPartyDebate:
    def test_experts_see_each_others_responses(self):
        """In party mode, each expert's round 2 prompt must include other experts' round 1 output."""
        client = MagicMock()
        round1_output = {"findings": [{"severity": "high", "issue": "SQL injection"}]}
        round2_output = {"response": "I agree with OWASP. Also noting timing attack risk.", "findings": []}
        client.run_json.side_effect = [
            round1_output,  # OWASP round 1
            round1_output,  # AUTH round 1
            round2_output,  # OWASP round 2 (sees AUTH's findings)
            round2_output,  # AUTH round 2 (sees OWASP's findings)
            {"findings": [{"severity": "high", "issue": "SQL injection"}]},  # adjudication
        ]

        party = PartyDebate(client=client, task_config=make_config())
        verdict = party.run(content="some vulnerable code")

        # Should have been called 5 times (2 experts × 2 rounds + 1 adjudication)
        assert client.run_json.call_count == 5

    def test_party_mode_produces_valid_verdict(self):
        """Party mode must return a Verdict object."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "SQL injection"}]
        }

        party = PartyDebate(client=client, task_config=make_config())
        verdict = party.run(content="SELECT * FROM users WHERE id = 'user_input'")

        assert isinstance(verdict, Verdict)
        assert verdict.task_type == "audit"

    def test_party_mode_round2_prompts_include_other_expert_findings(self):
        """Round 2 prompt for OWASP must contain AUTH's round 1 output."""
        client = MagicMock()
        round1 = {"findings": [{"severity": "high", "issue": "SQL injection"}]}
        round2 = {"findings": [], "agreements": []}
        adjudication = {"findings": []}
        client.run_json.side_effect = [round1, round1, round2, round2, adjudication]

        party = PartyDebate(client=client, task_config=make_config())
        party.run(content="some code")

        # Round 2 calls (index 2 and 3) should reference the other expert's output
        round2_prompts = [client.run_json.call_args_list[2][0][0],
                          client.run_json.call_args_list[3][0][0]]
        # Each round 2 prompt should include "OTHER EXPERTS" section
        for prompt in round2_prompts:
            assert "ROUND 2" in prompt or "other" in prompt.lower()
