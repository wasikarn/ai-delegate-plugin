"""Tests for ContextLoader (Project Constitution injection)."""
from pathlib import Path
from ai_delegate.context_loader import ContextLoader


class TestContextLoader:
    def test_loads_context_from_ai_delegate_dir(self, tmp_path):
        """Loads .ai-delegate/context.md from base_dir if present."""
        context_dir = tmp_path / ".ai-delegate"
        context_dir.mkdir()
        context_file = context_dir / "context.md"
        context_file.write_text("# Project: MyAPI\n- Use REST, not GraphQL\n- Python 3.11+")

        loader = ContextLoader(base_dir=tmp_path)
        context = loader.load()

        assert context is not None
        assert "Use REST, not GraphQL" in context

    def test_returns_none_when_no_context_file(self, tmp_path):
        """Returns None if no context file exists."""
        loader = ContextLoader(base_dir=tmp_path)
        assert loader.load() is None

    def test_formats_context_for_injection(self, tmp_path):
        """format_for_prompt() wraps context in a clear section."""
        context_dir = tmp_path / ".ai-delegate"
        context_dir.mkdir()
        (context_dir / "context.md").write_text("Use Python 3.11+")

        loader = ContextLoader(base_dir=tmp_path)
        formatted = loader.format_for_prompt()

        assert "PROJECT CONTEXT" in formatted
        assert "Use Python 3.11+" in formatted

    def test_format_for_prompt_empty_string_when_no_context(self, tmp_path):
        """Returns empty string (not None) when no context file."""
        loader = ContextLoader(base_dir=tmp_path)
        assert loader.format_for_prompt() == ""

    def test_loads_uppercase_context_file(self, tmp_path):
        """Also finds .ai-delegate/CONTEXT.md (uppercase)."""
        context_dir = tmp_path / ".ai-delegate"
        context_dir.mkdir()
        (context_dir / "CONTEXT.md").write_text("Use TypeScript strict mode")

        loader = ContextLoader(base_dir=tmp_path)
        context = loader.load()

        assert context is not None
        assert "TypeScript strict mode" in context

    def test_loads_root_level_context_file(self, tmp_path):
        """Also finds ai-delegate-context.md at root."""
        (tmp_path / "ai-delegate-context.md").write_text("Prefer async/await")

        loader = ContextLoader(base_dir=tmp_path)
        context = loader.load()

        assert context is not None
        assert "Prefer async/await" in context
