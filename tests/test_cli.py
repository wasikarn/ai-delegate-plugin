"""
Tests for CLI interface.

Tests command-line argument parsing and execution.
"""

import pytest
from unittest.mock import Mock, patch
from io import StringIO

from ai_delegate.cli import main, run_analysis, create_task_config
from ai_delegate.models import Tier


class TestCreateTaskConfig:
    """Tests for create_task_config function."""

    def test_create_audit_config(self):
        """Creating audit task config."""
        config = create_task_config("audit")

        assert config.task_type == "audit"
        assert config.display_name == "SECURITY AUDIT"
        assert config.always_deep is True

    def test_create_analyze_config(self):
        """Creating analyze task config."""
        config = create_task_config("analyze")

        assert config.task_type == "analyze"
        assert config.always_deep is False

    def test_create_architecture_config(self):
        """Creating architecture task config."""
        config = create_task_config("architecture")

        assert config.task_type == "architecture"
        assert config.always_deep is True

    def test_create_refactor_config(self):
        """Creating refactor task config."""
        config = create_task_config("refactor")

        assert config.task_type == "refactor"

    def test_create_migrate_config(self):
        """Creating migrate task config."""
        config = create_task_config("migrate")

        assert config.task_type == "migrate"

    def test_create_review_config(self):
        """Creating review task config."""
        config = create_task_config("review")

        assert config.task_type == "review"


class TestRunAnalysis:
    """Tests for run_analysis function."""

    @patch("ai_delegate.cli.OllamaClient")
    @patch("ai_delegate.cli.DebateOrchestrator")
    def test_run_analysis_basic(self, mock_orchestrator_class, mock_client_class):
        """run_analysis creates client and orchestrator correctly."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_verdict = Mock()
        mock_verdict.to_dict.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
            "recommendations": ["Fix XSS"],
            "action_items": ["Review code"],
        }
        mock_orchestrator = Mock()
        mock_orchestrator.analyze.return_value = mock_verdict
        mock_orchestrator_class.return_value = mock_orchestrator

        result = run_analysis(
            content="def hello(): pass",
            task_type="audit",
            tier=Tier.STANDARD.value,
        )

        assert result["task_type"] == "audit"
        mock_client_class.assert_called_once()
        mock_orchestrator_class.assert_called_once()

    @patch("ai_delegate.cli.OllamaClient")
    @patch("ai_delegate.cli.DebateOrchestrator")
    def test_run_analysis_with_model_override(self, mock_orchestrator_class, mock_client_class):
        """run_analysis uses custom model when specified."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_verdict = Mock()
        mock_verdict.to_dict.return_value = {"task_type": "audit"}
        mock_orchestrator = Mock()
        mock_orchestrator.analyze.return_value = mock_verdict
        mock_orchestrator_class.return_value = mock_orchestrator

        run_analysis(
            content="code",
            task_type="audit",
            model="custom-model",
        )

        # Verify model was set on config
        call_args = mock_client_class.call_args
        assert call_args.kwargs["model"] == "custom-model"

    @patch("ai_delegate.cli.OllamaClient")
    @patch("ai_delegate.cli.DebateOrchestrator")
    def test_run_analysis_verbose(self, mock_orchestrator_class, mock_client_class):
        """run_analysis passes verbose flag."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        mock_verdict = Mock()
        mock_verdict.to_dict.return_value = {"task_type": "audit"}
        mock_orchestrator = Mock()
        mock_orchestrator.analyze.return_value = mock_verdict
        mock_orchestrator_class.return_value = mock_orchestrator

        run_analysis(
            content="code",
            task_type="audit",
            verbose=True,
        )

        call_args = mock_client_class.call_args
        assert call_args.kwargs["verbose"] is True


class TestCLIMain:
    """Tests for main CLI function."""

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_basic(self, mock_run_analysis, mock_create_config):
        """main handles basic CLI invocation."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
            "recommendations": [],
            "action_items": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    # Should not raise
                    main()

        mock_run_analysis.assert_called_once()

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_with_file(self, mock_run_analysis, mock_create_config, tmp_path):
        """main handles --file argument."""
        # Create temp file
        test_file = tmp_path / "test.py"
        test_file.write_text("def hello(): pass")

        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit", "--file", str(test_file)]):
            main()

        mock_run_analysis.assert_called_once()
        call_kwargs = mock_run_analysis.call_args.kwargs
        assert "def hello" in call_kwargs["content"]

    def test_main_file_not_found(self, tmp_path):
        """main exits when file not found."""
        nonexistent = tmp_path / "nonexistent.py"

        with patch("sys.argv", ["ai-delegate", "audit", "--file", str(nonexistent)]):
            with pytest.raises(SystemExit) as exc_info:
                main()

            assert exc_info.value.code == 1

    def test_main_no_input(self):
        """main exits when no input provided (tty stdin)."""
        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin.isatty", return_value=True):
                with pytest.raises(SystemExit) as exc_info:
                    main()

                assert exc_info.value.code == 1

    def test_main_empty_input(self):
        """main exits when input is empty."""
        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin", StringIO("")):
                with patch("sys.stdin.isatty", return_value=False):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_with_tier(self, mock_run_analysis, mock_create_config):
        """main handles --tier argument."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit", "--tier", "deep"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    main()

        call_kwargs = mock_run_analysis.call_args.kwargs
        assert call_kwargs["tier"] == "deep"

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_with_model(self, mock_run_analysis, mock_create_config):
        """main handles --model argument."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit", "--model", "custom-model"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    main()

        call_kwargs = mock_run_analysis.call_args.kwargs
        assert call_kwargs["model"] == "custom-model"

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_text_output(self, mock_run_analysis, mock_create_config, capsys):
        """main handles --output text argument."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [{"severity": "high", "issue": "XSS"}],
            "recommendations": ["Fix XSS"],
        }

        with patch("sys.argv", ["ai-delegate", "audit", "--output", "text"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    main()

        captured = capsys.readouterr()
        assert "Task:" in captured.out

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_json_output(self, mock_run_analysis, mock_create_config, capsys):
        """main outputs JSON by default."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    main()

        captured = capsys.readouterr()
        assert '"task_type"' in captured.out

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_verbose(self, mock_run_analysis, mock_create_config, capsys):
        """main handles --verbose argument."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            display_name="SECURITY AUDIT",
            description="Test description",
            default_model="test-model",
        )
        mock_run_analysis.return_value = {
            "task_type": "audit",
            "consensus_score": 0.85,
            "tier_used": "deep",
            "findings": [],
        }

        with patch("sys.argv", ["ai-delegate", "audit", "--verbose"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    main()

        captured = capsys.readouterr()
        assert "Task:" in captured.out
        assert "SECURITY AUDIT" in captured.out

    @patch("ai_delegate.cli.create_task_config")
    @patch("ai_delegate.cli.run_analysis")
    def test_main_handles_exception(self, mock_run_analysis, mock_create_config):
        """main handles exceptions gracefully."""
        mock_create_config.return_value = Mock(
            task_type="audit",
            default_model="test-model",
        )
        mock_run_analysis.side_effect = RuntimeError("Test error")

        with patch("sys.argv", ["ai-delegate", "audit"]):
            with patch("sys.stdin", StringIO("test code")):
                with patch("sys.stdin.isatty", return_value=False):
                    with pytest.raises(SystemExit) as exc_info:
                        main()

                    assert exc_info.value.code == 1


class TestCLIVersion:
    """Tests for --version flag."""

    def test_version_flag(self, capsys):
        """--version prints version and exits 0."""
        with patch("sys.argv", ["ai-delegate", "--version"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.0.2" in captured.out

    def test_version_short_flag(self, capsys):
        """-V prints version and exits 0."""
        with patch("sys.argv", ["ai-delegate", "-V"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.0.2" in captured.out


class TestMainModule:
    """Tests for __main__.py entry point."""

    def test_main_module_imports(self):
        """__main__.py imports and calls main correctly."""
        from ai_delegate.__main__ import main as module_main

        # Should be callable
        assert callable(module_main)