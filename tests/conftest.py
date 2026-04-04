"""
Shared fixtures for AI Delegation Framework tests.

Follows pytest best practices:
- Fixtures provide test dependencies
- Each fixture has clear scope
- Fixtures are composable
"""

import pytest
from unittest.mock import Mock

from ai_delegate.client import AIClient
from ai_delegate.models import TaskConfig, Finding, ExpertResult
from ai_delegate.config import EXPERT_CONFIGS


@pytest.fixture
def mock_client() -> Mock:
    """Mock AI client that returns predictable JSON responses."""
    client = Mock(spec=AIClient)
    client.run_json.return_value = {
        "findings": [
            {"severity": "high", "issue": "XSS vulnerability found"},
            {"severity": "medium", "issue": "CSRF token missing"},
        ]
    }
    return client


@pytest.fixture
def security_task_config() -> TaskConfig:
    """Task config for security audit."""
    return TaskConfig(
        task_type="audit",
        experts=EXPERT_CONFIGS.get("security", {}),
        display_name="SECURITY AUDIT",
        description="OWASP Top 10, Authentication/Crypto, Input/Secrets",
        adjudicator_role="Security Adjudicator",
        output_format="- critical_vulnerabilities\n- high_vulnerabilities",
        default_model="glm-5:cloud",
        always_deep=True,
    )


@pytest.fixture
def performance_task_config() -> TaskConfig:
    """Task config for performance analysis."""
    return TaskConfig(
        task_type="analyze",
        experts=EXPERT_CONFIGS.get("performance", {}),
        display_name="PERFORMANCE ANALYSIS",
        description="Algorithm Complexity, Database/Query, Memory/Caching",
        adjudicator_role="Performance Adjudicator",
        output_format="- high_impact\n- medium_impact",
        default_model="glm-5:cloud",
        always_deep=False,
    )


@pytest.fixture
def sample_findings() -> list[Finding]:
    """Sample findings for testing."""
    return [
        Finding(
            severity="critical",
            issue="SQL injection in login form",
            location="auth.py:42",
            recommendation="Use parameterized queries",
        ),
        Finding(
            severity="high",
            issue="XSS in search endpoint",
            location="search.py:15",
            recommendation="Sanitize user input",
        ),
        Finding(
            severity="medium",
            issue="Missing CSRF token",
            recommendation="Add CSRF protection",
        ),
    ]


@pytest.fixture
def sample_expert_results(sample_findings: list[Finding]) -> list[ExpertResult]:
    """Sample expert results for testing consensus."""
    return [
        ExpertResult(
            expert_name="owasp",
            expert_type="security",
            findings=sample_findings[:2],  # critical + high
            raw_output='{"findings": [{"severity": "critical", "issue": "SQL injection"}]}',
        ),
        ExpertResult(
            expert_name="auth",
            expert_type="security",
            findings=sample_findings[1:],  # high + medium
            raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
        ),
        ExpertResult(
            expert_name="input",
            expert_type="security",
            findings=[sample_findings[1]],  # just high
            raw_output='{"findings": [{"severity": "high", "issue": "XSS"}]}',
        ),
    ]


@pytest.fixture
def sample_code() -> str:
    """Sample code for analysis."""
    return '''
def get_user(user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    return db.execute(query)

def search(query):
    return f"<div>Results for: {query}</div>"
'''


@pytest.fixture
def audit_task_config() -> TaskConfig:
    """Alias for security_task_config for clarity."""
    return TaskConfig.from_task_type("audit")


@pytest.fixture
def analyze_task_config() -> TaskConfig:
    """Task config for performance analysis."""
    return TaskConfig.from_task_type("analyze")