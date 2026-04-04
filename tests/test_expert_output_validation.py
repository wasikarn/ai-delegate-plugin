"""Tests for ExpertRunner schema validation of expert output."""
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import ExpertRunner
from ai_delegate.models import TaskConfig


def make_config():
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "You are OWASP expert."},
        display_name="AUDIT",
        description="Security audit",
        adjudicator_role="Adjudicator",
        output_format="...",
        default_model="glm-5:cloud",
    )


class TestExpertOutputValidation:
    def test_null_findings_produces_empty_list(self):
        """When expert returns {"findings": null}, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"findings": None}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "You are OWASP expert.", "some code")

        assert result.findings == []
        assert result.error is None

    def test_missing_findings_key_produces_empty_list(self):
        """When expert returns {} with no findings key, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"analysis": "Code looks clean"}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert result.findings == []

    def test_non_list_findings_produces_empty_list(self):
        """When expert returns {"findings": "some string"}, result has empty findings list."""
        client = MagicMock()
        client.run_json.return_value = {"findings": "No issues found"}

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert result.findings == []

    def test_finding_missing_issue_field_uses_empty_string(self):
        """Finding dict without 'issue' key defaults to empty string, not crashes."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high"}]  # missing 'issue'
        }

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert len(result.findings) == 1
        assert result.findings[0].issue == ""
        assert result.findings[0].severity == "high"

    def test_valid_findings_are_parsed_correctly(self):
        """Well-formed findings are parsed into Finding objects."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [
                {"severity": "critical", "issue": "SQL injection", "location": "line 42"},
                {"severity": "high", "issue": "XSS", "recommendation": "Sanitize output"},
            ]
        }

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert len(result.findings) == 2
        assert result.findings[0].severity == "critical"
        assert result.findings[0].issue == "SQL injection"
        assert result.findings[0].location == "line 42"
        assert result.findings[1].recommendation == "Sanitize output"

    def test_integer_findings_entry_is_skipped(self):
        """Non-dict entries in findings list are silently skipped."""
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [42, "string", {"severity": "high", "issue": "Real finding"}, None]
        }

        runner = ExpertRunner(client=client, task_config=make_config())
        result = runner._run_single_expert("OWASP", "...", "code")

        assert len(result.findings) == 1
        assert result.findings[0].issue == "Real finding"
