"""
Tests for CLI interface.

Tests command-line argument parsing and execution.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
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
        assert "0.3.0" in captured.out

    def test_version_short_flag(self, capsys):
        """-V prints version and exits 0."""
        with patch("sys.argv", ["ai-delegate", "-V"]):
            with pytest.raises(SystemExit) as exc_info:
                main()

        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        assert "0.3.0" in captured.out


class TestMainModule:
    """Tests for __main__.py entry point."""

    def test_main_module_imports(self):
        """__main__.py imports and calls main correctly."""
        from ai_delegate.__main__ import main as module_main

        # Should be callable
        assert callable(module_main)


class TestRateSubcommand:
    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "y"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_last_y_stores_win(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            42, "ollama", "audit"
        )
        mock_memory.get_cli_performance.return_value = [
            {"cli_name": "ollama", "win_count": 8, "loss_count": 2}
        ]
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_memory.store_rating.assert_called_once_with(42, 1)

    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "n"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_last_n_stores_loss(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = (
            42, "ollama", "audit"
        )
        mock_memory.get_cli_performance.return_value = []
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0
        mock_memory.store_rating.assert_called_once_with(42, 0)

    @patch("ai_delegate.cli.sys.argv", ["ai-delegate", "rate", "--last", "y"])
    @patch("ai_delegate.cli.AnalysisMemory")
    def test_rate_no_runs_exits_with_error(self, mock_memory_cls):
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_memory._connect.return_value.__enter__.return_value.execute.return_value.fetchone.return_value = None
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1


class TestNoAdaptiveFlag:
    @patch("ai_delegate.cli.run_analysis")
    @patch("sys.stdin")
    def test_no_adaptive_passed_to_run_analysis(self, mock_stdin, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
        }
        with patch("sys.argv", ["ai-delegate", "audit", "--no-adaptive", "--no-rating"]):
            main()
        call_kwargs = mock_run.call_args[1]
        assert call_kwargs.get("no_adaptive") is True


class TestInlineRatingPrompt:
    @patch("ai_delegate.cli.run_analysis")
    @patch("ai_delegate.cli.AnalysisMemory")
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin")
    def test_rating_prompt_shown_after_analysis(
        self, mock_stdin, mock_input, mock_memory_cls, mock_run
    ):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_memory = MagicMock()
        mock_memory_cls.return_value = mock_memory
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit"]):
            main()
        mock_memory.store_rating.assert_called_once_with(42, 1)

    @patch("ai_delegate.cli.run_analysis")
    @patch("builtins.input", side_effect=EOFError)
    @patch("sys.stdin")
    def test_eof_in_rating_prompt_is_silent(self, mock_stdin, mock_input, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit"]):
            main()  # Should not raise

    @patch("ai_delegate.cli.run_analysis")
    @patch("builtins.input", return_value="y")
    @patch("sys.stdin")
    def test_no_rating_flag_skips_prompt(self, mock_stdin, mock_input, mock_run):
        mock_stdin.isatty.return_value = False
        mock_stdin.read.return_value = "some code"
        mock_run.return_value = {
            "task_type": "audit", "consensus_score": 0.75,
            "tier_used": "standard", "findings": [],
            "recommendations": [], "action_items": [],
            "_run_id": 42,
        }
        with patch("sys.argv", ["ai-delegate", "audit", "--no-rating"]):
            main()
        mock_input.assert_not_called()