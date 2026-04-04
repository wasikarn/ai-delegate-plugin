"""Load project constitution from .ai-delegate/context.md."""

from pathlib import Path
from typing import Optional


CONTEXT_PATHS = [
    ".ai-delegate/context.md",
    ".ai-delegate/CONTEXT.md",
    "ai-delegate-context.md",
]


class ContextLoader:
    """Load and format project constitution for expert prompts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()
        self._cached_context: Optional[str] = None
        self._loaded: bool = False

    def load(self) -> Optional[str]:
        """Load context from first found context file, cached after first read."""
        if not self._loaded:
            for relative_path in CONTEXT_PATHS:
                full_path = self.base_dir / relative_path
                if full_path.exists():
                    self._cached_context = full_path.read_text(encoding="utf-8").strip()
                    break
            self._loaded = True
        return self._cached_context

    def format_for_prompt(self) -> str:
        """Return context formatted for injection into expert prompts.

        Returns empty string if no context file found.
        """
        context = self.load()
        if not context:
            return ""
        return f"""## PROJECT CONTEXT (Constitution)
The following constraints and decisions apply to this project.
All experts MUST respect these when making recommendations:

{context}

---
"""
