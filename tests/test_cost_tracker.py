"""Tests for CostTracker token usage and cost reporting."""
from ai_delegate.cost_tracker import CostTracker, CostReport, TokenUsage, TOKEN_COSTS


class TestTokenUsage:
    def test_total_tokens(self):
        u = TokenUsage(model="default", input_tokens=100, output_tokens=50)
        assert u.total_tokens == 150

    def test_cost_calculation(self):
        u = TokenUsage(model="glm-5:cloud", input_tokens=1_000_000, output_tokens=0)
        rates = TOKEN_COSTS["glm-5:cloud"]
        assert abs(u.cost_usd - rates["input"]) < 0.0001

    def test_unknown_model_uses_default_rate(self):
        u = TokenUsage(model="unknown-model", input_tokens=1_000_000, output_tokens=0)
        default_rate = TOKEN_COSTS["default"]["input"]
        assert abs(u.cost_usd - default_rate) < 0.0001


class TestCostReport:
    def test_aggregates_totals(self):
        report = CostReport(usages=[
            TokenUsage(model="glm-5:cloud", input_tokens=100, output_tokens=50),
            TokenUsage(model="glm-5:cloud", input_tokens=200, output_tokens=100),
        ])
        assert report.total_input_tokens == 300
        assert report.total_output_tokens == 150
        assert report.total_tokens == 450

    def test_empty_report(self):
        report = CostReport()
        assert report.total_tokens == 0
        assert report.total_cost_usd == 0.0

    def test_to_dict_structure(self):
        report = CostReport(usages=[
            TokenUsage(model="glm-5:cloud", input_tokens=100, output_tokens=50, expert_name="OWASP"),
        ])
        d = report.to_dict()
        assert "total_tokens" in d
        assert "total_cost_usd" in d
        assert "per_expert" in d
        assert d["per_expert"][0]["expert"] == "OWASP"

    def test_format_summary_contains_key_info(self):
        report = CostReport(usages=[
            TokenUsage(model="glm-5:cloud", input_tokens=1000, output_tokens=500, expert_name="OWASP"),
        ])
        summary = report.format_summary()
        assert "Cost Report" in summary
        assert "1,500" in summary  # total tokens
        assert "$" in summary


class TestCostTracker:
    def test_record_and_report(self):
        tracker = CostTracker()
        tracker.record(TokenUsage(model="glm-5:cloud", input_tokens=100, output_tokens=50))
        report = tracker.report()
        assert len(report.usages) == 1
        assert report.total_tokens == 150

    def test_multiple_records_accumulate(self):
        tracker = CostTracker()
        tracker.record(TokenUsage(model="glm-5:cloud", input_tokens=100, output_tokens=50))
        tracker.record(TokenUsage(model="kimi-k2.5:cloud", input_tokens=200, output_tokens=100))
        report = tracker.report()
        assert len(report.usages) == 2
        assert report.total_tokens == 450

    def test_estimate_from_content(self):
        tracker = CostTracker()
        usage = tracker.estimate_from_content("a" * 4000, model="glm-5:cloud", expert_name="Test")
        assert usage.input_tokens == 1000  # 4000 chars / 4
        assert usage.output_tokens > 0
        assert usage.expert_name == "Test"
