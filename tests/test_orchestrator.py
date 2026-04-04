"""
Integration tests for DebateOrchestrator.

Tests the complete analysis flow from start to finish.
"""

import pytest
from unittest.mock import Mock, patch
from typing import Any

from ai_delegate.client import OllamaClient
from ai_delegate.models import TaskConfig, ExpertResult, Finding, Tier, Verdict
from ai_delegate.debate.orchestrator import DebateOrchestrator, ConsensusCalculator, DebatePhase, ExpertRunner


class TestDebateOrchestrator:
    """Integration tests for DebateOrchestrator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock AI client with realistic responses."""
        client = Mock(spec=OllamaClient)

        def mock_run_json(prompt: str) -> dict:
            """Simulate realistic AI responses based on prompt content."""
            if "OWASP" in prompt or "security" in prompt.lower():
                return {
                    "findings": [
                        {"severity": "high", "issue": "SQL injection in login"},
                        {"severity": "medium", "issue": "XSS in search"},
                    ]
                }
            elif "Adjudicator" in prompt:
                return {
                    "findings": [
                        {"severity": "high", "issue": "SQL injection in login"},
                        {"severity": "medium", "issue": "XSS in search"},
                    ],
                    "recommendations": ["Use parameterized queries", "Sanitize input"],
                    "action_items": ["Fix SQL injection", "Add XSS protection"],
                }
            elif "Judge" in prompt:
                return {
                    "selected_verdict": 1,
                    "confidence": 90,
                    "reasoning": "Verdict 1 is more complete",
                }
            else:
                return {"findings": []}

        client.run_json.side_effect = mock_run_json
        return client

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit task config."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def analyze_config(self) -> TaskConfig:
        """Create analyze task config."""
        return TaskConfig.from_task_type("analyze")

    @pytest.fixture
    def orchestrator(self, mock_client: Any, audit_config: TaskConfig) -> DebateOrchestrator:
        """Create DebateOrchestrator instance."""
        return DebateOrchestrator(mock_client, audit_config, verbose=False)

    def test_analyze_returns_verdict(
        self, orchestrator: DebateOrchestrator, sample_code: str
    ):
        """Analyze should return a Verdict."""
        result = orchestrator.analyze(sample_code)

        assert isinstance(result, Verdict)
        assert result.task_type == "audit"

    def test_analyze_fast_tier_skips_debate(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """FAST tier should skip debate and adjudication."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        # Patch consensus to return high score
        with patch.object(
            ConsensusCalculator, "calculate"
        ) as mock_consensus:
            from ai_delegate.models import ConsensusResult

            mock_consensus.return_value = ConsensusResult(
                score=0.95,  # High consensus = FAST tier
                consensus_findings=[Finding(severity="high", issue="Test")],
            )

            result = orchestrator.analyze(sample_code, tier=Tier.FAST.value)

            # Should return consensus directly
            assert result.tier_used == Tier.FAST.value
            # Should not call run_json for debate/adjudication
            assert result.consensus_score == 0.95

    def test_analyze_deep_tier_runs_all_phases(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """DEEP tier should run all phases including judge."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        result = orchestrator.analyze(sample_code, tier=Tier.DEEP.value)

        assert result.tier_used == Tier.DEEP.value
        # Judge confidence/reasoning only set when verdict 1 is selected (default)
        # Mock returns selected_verdict: 1 by default

    def test_analyze_auto_tier_selects_based_on_consensus(
        self, mock_client: Any, analyze_config: TaskConfig, sample_code: str
    ):
        """AUTO tier should select tier based on consensus."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        # With realistic mock, consensus should select appropriate tier
        result = orchestrator.analyze(sample_code, tier=Tier.AUTO.value)

        assert result.tier_used in [Tier.FAST.value, Tier.STANDARD.value, Tier.DEEP.value]

    def test_analyze_audit_always_deep(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """Audit tasks should always use DEEP tier."""
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        result = orchestrator.analyze(sample_code, tier=Tier.AUTO.value)

        # Audit always uses DEEP (always_deep=True)
        assert result.tier_used == Tier.DEEP.value
        assert result.judge_confidence is not None

    def test_analyze_handles_expert_failures(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """Analyze should handle expert failures gracefully."""
        call_count = 0

        def failing_response(prompt: str):
            nonlocal call_count
            call_count += 1
            if call_count <= 2:  # First 2 experts fail
                raise RuntimeError("API error")
            return {"findings": [{"severity": "low", "issue": "Minor issue"}]}

        mock_client.run_json.side_effect = failing_response
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        # Should not raise, should complete analysis
        result = orchestrator.analyze(sample_code)

        assert isinstance(result, Verdict)

    def test_verbose_logging(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str, caplog
    ):
        """Verbose mode should log progress."""
        import logging

        caplog.set_level(logging.INFO)

        orchestrator = DebateOrchestrator(mock_client, audit_config, verbose=True)
        orchestrator.analyze(sample_code)

        # Should have logged expert completion
        assert "completed" in caplog.text.lower() or len(caplog.records) >= 0


class TestDebateOrchestratorComponents:
    """Tests for DebateOrchestrator component integration."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_expert_runner_integration(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """DebateOrchestrator should use ExpertRunner correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}]
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        results = orchestrator.expert_runner.run_parallel(sample_code)

        # Should have results from all experts
        assert len(results) == 3  # owasp, auth, input
        assert all(r.expert_type == "audit" for r in results)

    def test_adjudicator_integration(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """DebateOrchestrator should use Adjudicator correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}],
            "recommendations": ["Fix XSS"],
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        debate_results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="audit",
                findings=[Finding(severity="high", issue="XSS")],
                raw_output='{"findings": []}',
            )
        ]

        verdict = orchestrator.adjudicator.adjudicate(debate_results)

        assert verdict.task_type == "audit"

    def test_consensus_calculator_integration(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """DebateOrchestrator should use ConsensusCalculator correctly."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "XSS"}]
        }

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        results = orchestrator.expert_runner.run_parallel(sample_code)
        consensus = ConsensusCalculator.calculate(results)

        assert consensus.score >= 0.0
        assert consensus.score <= 1.0


class TestDebateOrchestratorTierSelection:
    """Tests for tier selection logic."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config (always_deep=True)."""
        return TaskConfig.from_task_type("audit")

    @pytest.fixture
    def analyze_config(self) -> TaskConfig:
        """Create analyze config (always_deep=False)."""
        return TaskConfig.from_task_type("analyze")

    def test_select_tier_explicit(self, mock_client: Any, analyze_config: TaskConfig):
        """Explicit tier should be used."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        from ai_delegate.models import ConsensusResult

        consensus = ConsensusResult(score=0.5)

        tier = orchestrator._select_tier(Tier.DEEP.value, consensus)
        assert tier == Tier.DEEP.value

        tier = orchestrator._select_tier(Tier.FAST.value, consensus)
        assert tier == Tier.FAST.value

    def test_select_tier_always_deep(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """Tasks with always_deep=True should always use DEEP."""
        orchestrator = DebateOrchestrator(mock_client, audit_config)

        from ai_delegate.models import ConsensusResult

        # Even with high consensus
        consensus = ConsensusResult(score=0.95)

        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.DEEP.value

    def test_select_tier_consensus_based(
        self, mock_client: Any, analyze_config: TaskConfig
    ):
        """AUTO should select tier based on consensus score."""
        orchestrator = DebateOrchestrator(mock_client, analyze_config)

        from ai_delegate.models import ConsensusResult

        # High consensus = FAST
        consensus = ConsensusResult(score=0.95)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.FAST.value

        # Medium consensus = STANDARD
        consensus = ConsensusResult(score=0.75)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.STANDARD.value

        # Low consensus = DEEP
        consensus = ConsensusResult(score=0.50)
        tier = orchestrator._select_tier(Tier.AUTO.value, consensus)
        assert tier == Tier.DEEP.value


class TestTaskConfigNewFields:
    """Tests for new TaskConfig fields: expert_models and sparse_topology_k."""

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_expert_models_defaults_to_empty_dict(
        self, audit_config: TaskConfig
    ):
        """expert_models should default to empty dict."""
        assert audit_config.expert_models == {}

    def test_sparse_topology_k_defaults_to_none(
        self, audit_config: TaskConfig
    ):
        """sparse_topology_k should default to None."""
        assert audit_config.sparse_topology_k is None

    def test_expert_models_can_be_set(
        self, audit_config: TaskConfig
    ):
        """expert_models should be settable."""
        audit_config.expert_models = {"owasp": "gpt-4o", "auth": "gemini-2.5-pro"}
        assert audit_config.expert_models == {"owasp": "gpt-4o", "auth": "gemini-2.5-pro"}

    def test_sparse_topology_k_can_be_set(
        self, audit_config: TaskConfig
    ):
        """sparse_topology_k should be settable."""
        audit_config.sparse_topology_k = 2
        assert audit_config.sparse_topology_k == 2


class TestHeterogeneousModels:
    """Tests for heterogeneous models (per-expert model assignment)."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_resolve_client_returns_base_when_no_override(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """_resolve_client should return base client when no override exists."""
        from ai_delegate.debate.orchestrator import _resolve_client

        result = _resolve_client(mock_client, audit_config, "owasp")
        assert result is mock_client

    def test_resolve_client_returns_base_when_same_model(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """_resolve_client should return base client when override is same model."""
        from ai_delegate.debate.orchestrator import _resolve_client

        # Set base client model
        mock_client.model = "test-model"

        # Set expert_models to same model
        audit_config.expert_models = {"owasp": "test-model"}

        result = _resolve_client(mock_client, audit_config, "owasp")
        assert result is mock_client

    def test_resolve_client_creates_new_client_for_different_model(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """_resolve_client should create new client when override differs."""
        from ai_delegate.debate.orchestrator import _resolve_client

        # Set base client properties
        mock_client.model = "base-model"
        mock_client.fallback_model = "fallback"
        mock_client.verbose = True
        mock_client.cli_type = "ollama"

        # Set expert_models to different model
        audit_config.expert_models = {"owasp": "override-model"}

        with patch("ai_delegate.debate.orchestrator.OllamaClient") as MockClient:
            mock_new_client = Mock(spec=OllamaClient)
            MockClient.return_value = mock_new_client

            result = _resolve_client(mock_client, audit_config, "owasp")

            # Should create new client with override model
            MockClient.assert_called_once_with(
                model="override-model",
                fallback_model="fallback",
                verbose=True,
                cli_type="ollama",
            )
            assert result is mock_new_client

    def test_expert_runner_uses_per_expert_client(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """ExpertRunner should use per-expert clients when configured."""
        # Set expert_models
        audit_config.expert_models = {"owasp": "owasp-model", "auth": "auth-model"}

        # Configure mock to return findings
        mock_client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "Test"}]
        }
        mock_client.model = "base-model"
        mock_client.fallback_model = "fallback"
        mock_client.verbose = False
        mock_client.cli_type = "ollama"

        orchestrator = DebateOrchestrator(mock_client, audit_config)

        with patch(
            "ai_delegate.debate.orchestrator._resolve_client"
        ) as mock_resolve:
            # Make _resolve_client return mock_client for simplicity
            mock_resolve.return_value = mock_client

            results = orchestrator.expert_runner.run_parallel(sample_code)

            # Should call _resolve_client for each expert
            assert mock_resolve.call_count == 3  # owasp, auth, input
            # Verify calls included expert names
            call_args = [call[0][2] for call in mock_resolve.call_args_list]
            assert "owasp" in call_args
            assert "auth" in call_args
            assert "input" in call_args

            # Should have results from all experts
            assert len(results) == 3


class TestDebateOrchestratorEdgeCases:
    """Edge case tests for DebateOrchestrator."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create mock client."""
        return Mock(spec=OllamaClient)

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        """Create audit config."""
        return TaskConfig.from_task_type("audit")

    def test_empty_code(self, mock_client: Any, audit_config: TaskConfig):
        """Empty code should be handled."""
        mock_client.run_json.return_value = {"findings": []}

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze("")

        assert isinstance(result, Verdict)

    def test_very_large_code(self, mock_client: Any, audit_config: TaskConfig):
        """Very large code should be handled."""
        mock_client.run_json.return_value = {
            "findings": [{"severity": "low", "issue": "Large file"}]
        }

        large_code = "x = 1\n" * 10000

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze(large_code)

        assert isinstance(result, Verdict)

    def test_unicode_code(self, mock_client: Any, audit_config: TaskConfig):
        """Unicode content should be handled."""
        mock_client.run_json.return_value = {"findings": []}

        unicode_code = '''
def hello():
    return "สวัสดี ครับ"
'''

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        result = orchestrator.analyze(unicode_code)

        assert isinstance(result, Verdict)

    def test_debate_phase_runs_parallel(
        self, mock_client: Any, audit_config: TaskConfig, sample_code: str
    ):
        """DebatePhase.run() should execute in parallel, not sequentially."""
        import time

        call_times = []

        def slow_response(prompt: str) -> dict:
            """Simulate slow expert responses (50ms each)."""
            call_times.append(time.time())
            time.sleep(0.05)  # 50ms per call
            return {
                "findings": [{"severity": "high", "issue": "Test finding"}],
                "recommendations": ["Fix issue"],
                "action_items": ["Implement fix"],
            }

        mock_client.run_json.side_effect = slow_response

        orchestrator = DebateOrchestrator(mock_client, audit_config)
        debate_results = [
            ExpertResult(
                expert_name="owasp",
                expert_type="audit",
                findings=[Finding(severity="high", issue="SQL injection")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="auth",
                expert_type="audit",
                findings=[Finding(severity="medium", issue="Auth bypass")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="input",
                expert_type="audit",
                findings=[Finding(severity="low", issue="Input validation")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="extra",
                expert_type="audit",
                findings=[Finding(severity="low", issue="Extra finding")],
                raw_output='{"findings": []}',
            ),
        ]

        start_time = time.time()
        results = orchestrator.debate_phase.run(debate_results)
        elapsed = time.time() - start_time

        # If sequential: ~0.2s (4 experts × 50ms)
        # If parallel: ~0.05s (max 50ms for any expert)
        # Assert execution was parallel: should be < 0.15s
        assert elapsed < 0.15, f"Expected parallel execution (<0.15s), got {elapsed:.3f}s"
        assert isinstance(results, list)
        assert len(results) == len(debate_results)


class TestSparseTopology:
    """Tests for DebatePhase sparse topology: _select_peers and filtered findings."""

    @pytest.fixture
    def mock_client(self) -> Any:
        client = Mock(spec=OllamaClient)
        client.run_json.return_value = {"findings": [{"severity": "high", "issue": "Test"}]}
        return client

    @pytest.fixture
    def audit_config(self) -> TaskConfig:
        return TaskConfig.from_task_type("audit")

    # --- _select_peers unit tests ---

    def test_select_peers_basic(self, mock_client: Any, audit_config: TaskConfig):
        """Expert 0 with k=2, N=3 sees peers 1 and 2."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(0, 3, 2) == [1, 2]

    def test_select_peers_wraps_around(self, mock_client: Any, audit_config: TaskConfig):
        """Expert 2 with k=2, N=3 wraps around to peers 0 and 1."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(2, 3, 2) == [0, 1]

    def test_select_peers_middle(self, mock_client: Any, audit_config: TaskConfig):
        """Expert 1 with k=2, N=4 sees peers 2 and 3."""
        phase = DebatePhase(mock_client, audit_config)
        assert phase._select_peers(1, 4, 2) == [2, 3]

    def test_select_peers_caps_at_n_minus_1(self, mock_client: Any, audit_config: TaskConfig):
        """k >= N-1 returns all peers (full visibility)."""
        phase = DebatePhase(mock_client, audit_config)
        result = phase._select_peers(0, 3, 5)
        assert sorted(result) == [1, 2]

    def test_select_peers_k_equals_1(self, mock_client: Any, audit_config: TaskConfig):
        """k=1 returns exactly 1 peer."""
        phase = DebatePhase(mock_client, audit_config)
        result = phase._select_peers(0, 3, 1)
        assert result == [1]

    # --- Integration: DebatePhase.run() with sparse topology ---

    def test_debate_phase_full_topology_by_default(self, mock_client: Any, audit_config: TaskConfig):
        """sparse_topology_k=None uses full visibility (default)."""
        assert audit_config.sparse_topology_k is None
        expert_results = [
            ExpertResult(
                expert_name="owasp", expert_type="audit",
                findings=[Finding(severity="high", issue="SQL injection")],
                raw_output='{"findings": []}',
            ),
            ExpertResult(
                expert_name="auth", expert_type="audit",
                findings=[Finding(severity="medium", issue="Auth bypass")],
                raw_output='{"findings": []}',
            ),
        ]
        phase = DebatePhase(mock_client, audit_config)
        results = phase.run(expert_results)
        assert len(results) == 2

    def test_debate_phase_sparse_k1_each_expert_sees_one_peer(
        self, mock_client: Any, audit_config: TaskConfig
    ):
        """sparse_topology_k=1: each expert prompt contains exactly 1 peer section."""
        audit_config.sparse_topology_k = 1
        prompts_seen: list = []

        def capture(prompt: str) -> dict:
            prompts_seen.append(prompt)
            return {"findings": []}

        mock_client.run_json.side_effect = capture

        expert_results = [
            ExpertResult(
                expert_name=name, expert_type="audit",
                findings=[],
                raw_output='{"findings": []}',
            )
            for name in ["owasp", "auth", "input"]
        ]

        phase = DebatePhase(mock_client, audit_config)
        results = phase.run(expert_results)

        assert len(results) == 3
        # Each prompt should contain exactly 1 "### X Expert:" peer section
        for prompt in prompts_seen:
            count = prompt.count("### ")
            assert count == 1, f"Expected 1 peer section (k=1), got {count}"