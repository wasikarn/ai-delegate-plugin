"""Tests for PluginRegistry custom expert definitions."""
import pytest
from pathlib import Path
import tempfile
import os
from ai_delegate.plugin_registry import (
    ExpertDefinition,
    PluginRegistry,
    PluginRegistryLoader,
)


class TestPluginRegistry:
    def test_empty_registry(self):
        registry = PluginRegistry()
        assert registry.is_empty()
        assert registry.get_experts_for_task("audit") == []

    def test_get_experts_for_task_filters_by_type(self):
        registry = PluginRegistry(experts=[
            ExpertDefinition(name="MyAudit", task_type="audit", prompt="Check for issues"),
            ExpertDefinition(name="MyArch", task_type="architecture", prompt="Check design"),
        ])
        assert len(registry.get_experts_for_task("audit")) == 1
        assert registry.get_experts_for_task("audit")[0].name == "MyAudit"
        assert len(registry.get_experts_for_task("architecture")) == 1

    def test_get_experts_empty_when_no_match(self):
        registry = PluginRegistry(experts=[
            ExpertDefinition(name="MyAudit", task_type="audit", prompt="Check"),
        ])
        assert registry.get_experts_for_task("analyze") == []


class TestPluginRegistryLoader:
    def test_load_returns_empty_when_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            loader = PluginRegistryLoader(base_dir=Path(tmpdir))
            registry = loader.load()
        assert registry.is_empty()

    def test_load_parses_yaml_file(self):
        yaml_content = """
experts:
  - name: CustomSQLExpert
    task_type: audit
    prompt: "Check for SQL injection vulnerabilities"
    description: "Custom SQL audit expert"
    severity_focus:
      - critical
      - high
  - name: APIDesign
    task_type: architecture
    prompt: "Review REST API design"
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ai_delegate_dir = Path(tmpdir) / ".ai-delegate"
            ai_delegate_dir.mkdir()
            (ai_delegate_dir / "experts.yaml").write_text(yaml_content)
            loader = PluginRegistryLoader(base_dir=Path(tmpdir))
            registry = loader.load()

        assert not registry.is_empty()
        assert len(registry.experts) == 2

        audit_experts = registry.get_experts_for_task("audit")
        assert len(audit_experts) == 1
        assert audit_experts[0].name == "CustomSQLExpert"
        assert "SQL injection" in audit_experts[0].prompt
        assert audit_experts[0].severity_focus == ["critical", "high"]

    def test_load_skips_experts_missing_required_fields(self):
        yaml_content = """
experts:
  - name: ValidExpert
    task_type: audit
    prompt: "Valid prompt"
  - task_type: audit
    prompt: "Missing name — invalid"
  - name: MissingPrompt
    task_type: audit
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            ai_delegate_dir = Path(tmpdir) / ".ai-delegate"
            ai_delegate_dir.mkdir()
            (ai_delegate_dir / "experts.yaml").write_text(yaml_content)
            loader = PluginRegistryLoader(base_dir=Path(tmpdir))
            registry = loader.load()

        assert len(registry.experts) == 1
        assert registry.experts[0].name == "ValidExpert"

    def test_load_empty_yaml_returns_empty_registry(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            ai_delegate_dir = Path(tmpdir) / ".ai-delegate"
            ai_delegate_dir.mkdir()
            (ai_delegate_dir / "experts.yaml").write_text("# empty file\n")
            loader = PluginRegistryLoader(base_dir=Path(tmpdir))
            registry = loader.load()

        assert registry.is_empty()
