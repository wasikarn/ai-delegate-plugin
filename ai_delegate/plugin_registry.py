"""
Plugin registry for custom expert definitions.
Loads YAML expert plugins from .ai-delegate/plugins/.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


@dataclass
class ExpertPlugin:
    """A custom expert loaded from a YAML plugin file."""
    name: str
    display_name: str
    task_types: List[str]
    prompt: str

    def to_expert_dict(self) -> Dict[str, str]:
        """Return {name: prompt} for injection into TaskConfig.experts."""
        return {self.name: self.prompt}


class PluginRegistry:
    """Loads custom expert plugins from a directory of YAML files."""

    def __init__(self, plugin_dir: Optional[Path] = None):
        if plugin_dir is None:
            plugin_dir = Path.cwd() / ".ai-delegate" / "plugins"
        self._plugin_dir = Path(plugin_dir)
        self._plugins: Optional[List[ExpertPlugin]] = None

    def load(self) -> List[ExpertPlugin]:
        """Load all plugins from directory. Returns empty list if dir missing or yaml unavailable."""
        if self._plugins is not None:
            return self._plugins

        if not HAS_YAML:
            logger.warning("PyYAML not installed — plugin registry disabled")
            self._plugins = []
            return self._plugins

        if not self._plugin_dir.exists():
            self._plugins = []
            return self._plugins

        plugins = []
        for yaml_file in sorted(self._plugin_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(yaml_file.read_text())
                if not isinstance(data, dict):
                    continue
                name = data.get("name")
                task_types = data.get("task_types")
                prompt = data.get("prompt")
                if not name or not task_types or not prompt:
                    logger.warning(
                        "Skipping %s: missing required fields (name, task_types, prompt)",
                        yaml_file.name,
                    )
                    continue
                plugins.append(ExpertPlugin(
                    name=str(name),
                    display_name=str(data.get("display_name", name)),
                    task_types=[str(t) for t in task_types],
                    prompt=str(prompt).strip(),
                ))
            except Exception as e:
                logger.warning("Failed to load plugin %s: %s", yaml_file.name, e)

        self._plugins = plugins
        return self._plugins

    def for_task(self, task_type: str) -> List[ExpertPlugin]:
        """Return plugins applicable to a given task type."""
        return [p for p in self.load() if task_type in p.task_types]
