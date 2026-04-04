"""Tests for PluginRegistry custom expert definitions (plan spec)."""
import pytest
from pathlib import Path
from ai_delegate.plugin_registry import PluginRegistry, ExpertPlugin


class TestPluginRegistry:
    def test_load_valid_plugin(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        plugin_file = plugin_dir / "gdpr-expert.yaml"
        plugin_file.write_text("""
name: gdpr-expert
display_name: GDPR Compliance Expert
task_types:
  - audit
  - review
prompt: |
  You are a GDPR compliance expert. Analyze the code for GDPR violations.
  Focus on: data minimization, consent, right to erasure, data portability.
  Return JSON with findings list.
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 1
        assert plugins[0].name == "gdpr-expert"
        assert plugins[0].display_name == "GDPR Compliance Expert"
        assert "audit" in plugins[0].task_types

    def test_load_multiple_plugins(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        for name in ["expert-a", "expert-b", "expert-c"]:
            (plugin_dir / f"{name}.yaml").write_text(f"""
name: {name}
display_name: {name.upper()}
task_types: [audit]
prompt: "You are {name}."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 3

    def test_missing_required_field_skipped(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "bad-plugin.yaml").write_text("""
name: bad-plugin
# Missing: task_types, prompt
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert len(plugins) == 0

    def test_empty_directory_returns_empty_list(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert plugins == []

    def test_nonexistent_directory_returns_empty(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        # Directory does NOT exist
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        assert plugins == []

    def test_plugin_for_task_type(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "audit-only.yaml").write_text("""
name: audit-only
display_name: Audit Only Expert
task_types: [audit]
prompt: "Audit prompt."
""")
        (plugin_dir / "review-only.yaml").write_text("""
name: review-only
display_name: Review Only Expert
task_types: [review]
prompt: "Review prompt."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        audit_plugins = registry.for_task("audit")
        assert len(audit_plugins) == 1
        assert audit_plugins[0].name == "audit-only"

    def test_to_expert_dict(self, tmp_path):
        plugin_dir = tmp_path / ".ai-delegate" / "plugins"
        plugin_dir.mkdir(parents=True)
        (plugin_dir / "custom.yaml").write_text("""
name: custom-expert
display_name: Custom Expert
task_types: [audit]
prompt: "Custom analysis prompt."
""")
        registry = PluginRegistry(plugin_dir=plugin_dir)
        plugins = registry.load()
        expert_dict = plugins[0].to_expert_dict()
        assert "custom-expert" in expert_dict
        assert expert_dict["custom-expert"] == "Custom analysis prompt."
