"""Plugin registry for loading custom expert definitions from YAML files."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

REGISTRY_PATHS = [
    ".ai-delegate/experts.yaml",
    ".ai-delegate/experts.yml",
    "ai-delegate-experts.yaml",
    "ai-delegate-experts.yml",
]


@dataclass
class ExpertDefinition:
    """Custom expert definition loaded from YAML."""
    name: str
    task_type: str
    prompt: str
    description: str = ""
    severity_focus: List[str] = field(default_factory=list)


@dataclass
class PluginRegistry:
    """Registry of custom expert definitions."""
    experts: List[ExpertDefinition] = field(default_factory=list)

    def get_experts_for_task(self, task_type: str) -> List[ExpertDefinition]:
        """Return all custom experts registered for a given task type."""
        return [e for e in self.experts if e.task_type == task_type]

    def is_empty(self) -> bool:
        return len(self.experts) == 0


class PluginRegistryLoader:
    """Loads PluginRegistry from YAML files in the project directory."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()

    def load(self) -> PluginRegistry:
        """Load registry from first found YAML file, or return empty registry."""
        for rel_path in REGISTRY_PATHS:
            path = self.base_dir / rel_path
            if path.exists():
                return self._parse(path)
        return PluginRegistry()

    def _parse(self, path: Path) -> PluginRegistry:
        try:
            import yaml
        except ImportError:
            return PluginRegistry()

        with open(path) as f:
            data = yaml.safe_load(f)

        if not data or "experts" not in data:
            return PluginRegistry()

        experts = []
        for item in data["experts"]:
            if "name" not in item or "task_type" not in item or "prompt" not in item:
                continue
            experts.append(ExpertDefinition(
                name=item["name"],
                task_type=item["task_type"],
                prompt=item["prompt"],
                description=item.get("description", ""),
                severity_focus=item.get("severity_focus", []),
            ))

        return PluginRegistry(experts=experts)
