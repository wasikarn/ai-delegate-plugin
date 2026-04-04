"""Tests for ElicitationEngine (BMAD reasoning lenses)."""
from unittest.mock import MagicMock
from ai_delegate.elicitation import ElicitationEngine, ElicitationMethod
from ai_delegate.models import Finding, ExpertResult


def make_results():
    return [
        ExpertResult(
            expert_name="OWASP",
            expert_type="audit",
            findings=[Finding(severity="high", issue="SQL injection on line 42")],
            raw_output='{"findings": [{"severity": "high", "issue": "SQL injection on line 42"}]}',
        )
    ]


class TestElicitationEngine:
    def test_all_methods_are_available(self):
        assert ElicitationMethod.PRE_MORTEM == "pre-mortem"
        assert ElicitationMethod.FIRST_PRINCIPLES == "first-principles"
        assert ElicitationMethod.INVERSION == "inversion"
        assert ElicitationMethod.RED_TEAM == "red-team"
        assert ElicitationMethod.CONSTRAINT_REMOVAL == "constraint-removal"

    def test_elicitation_calls_llm_with_method_prompt(self):
        """ElicitationEngine should call LLM with method-specific prompt."""
        client = MagicMock()
        client.run_json.return_value = {
            "elicitation_method": "pre-mortem",
            "new_risks": ["What if the parameterized query library has a bug?"],
            "refined_findings": [
                {"severity": "critical", "issue": "SQL injection — confirmed by pre-mortem analysis"}
            ]
        }

        engine = ElicitationEngine(client=client)
        result = engine.apply(
            method=ElicitationMethod.PRE_MORTEM,
            expert_results=make_results(),
            content="SELECT * FROM users WHERE id = 'user_input'",
        )

        assert client.run_json.called
        call_args = client.run_json.call_args[0][0]
        assert "pre-mortem" in call_args.lower() or "fail" in call_args.lower()
        assert result is not None

    def test_elicitation_returns_refined_expert_results(self):
        """ElicitationEngine returns updated ExpertResult list with new findings."""
        client = MagicMock()
        client.run_json.return_value = {
            "refined_findings": [
                {"severity": "critical", "issue": "SQL injection — critical after elicitation"},
                {"severity": "high", "issue": "New risk discovered via pre-mortem"},
            ]
        }

        engine = ElicitationEngine(client=client)
        refined = engine.apply(
            method=ElicitationMethod.PRE_MORTEM,
            expert_results=make_results(),
            content="some code",
        )

        all_findings = [f for r in refined for f in r.findings]
        assert len(all_findings) >= 1

    def test_invalid_method_raises_value_error(self):
        """Unknown elicitation method raises ValueError."""
        engine = ElicitationEngine(client=MagicMock())
        try:
            engine.apply(method="unknown-method", expert_results=make_results(), content="code")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "unknown-method" in str(e)

    def test_empty_refined_findings_returns_originals(self):
        """When elicitation returns no refined findings, original results are returned."""
        client = MagicMock()
        client.run_json.return_value = {"refined_findings": []}

        engine = ElicitationEngine(client=client)
        result = engine.apply(
            method=ElicitationMethod.INVERSION,
            expert_results=make_results(),
            content="code",
        )

        # Returns original results unchanged
        assert result == make_results()
