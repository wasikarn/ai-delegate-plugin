"""Tests for ai_delegate/catalog.py — AgentCatalog."""
import json
import pytest
from pathlib import Path

from ai_delegate.catalog import (
    AgentCatalog,
    AgentMetadata,
    DOMAIN_KEYWORDS,
    _detect_domains,
    _extract_plugin_name,
    validate_agent_name,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


def _write_agent(agents_dir: Path, name: str, description: str, **extras) -> Path:
    """Helper: write a valid agent .md file with YAML frontmatter."""
    model = extras.get("model", "")
    tools = extras.get("tools", [])
    frontmatter = f"---\nname: {name}\ndescription: |\n  {description}\n"
    if model:
        frontmatter += f"model: {model}\n"
    if tools:
        frontmatter += f"tools: {json.dumps(tools)}\n"
    frontmatter += "---\n\n# Agent body"
    path = agents_dir / f"{name}.md"
    path.write_text(frontmatter)
    return path


@pytest.fixture
def plugin_dir(tmp_path) -> Path:
    """A fake plugin directory with agents/ subdir."""
    plugin = tmp_path / "plugins" / "ai-delegate"
    (plugin / "agents").mkdir(parents=True)
    return plugin


@pytest.fixture
def plugins_root(plugin_dir) -> Path:
    """The plugins root containing ai-delegate."""
    return plugin_dir.parent


@pytest.fixture
def trust_file(tmp_path) -> Path:
    """A trust file that trusts ai-delegate."""
    tf = tmp_path / "trust.json"
    tf.write_text(json.dumps({"trusted_plugins": ["ai-delegate"]}))
    return tf


# ─── Discovery ───────────────────────────────────────────────────────────────


class TestAgentCatalogDiscovery:
    def test_scan_empty_plugins_returns_empty(self, tmp_path, trust_file):
        (tmp_path / "plugins").mkdir()
        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust_file)
        assert catalog.scan() == []

    def test_scan_nonexistent_plugins_dir_returns_empty(self, tmp_path, trust_file):
        catalog = AgentCatalog(plugins_dir=tmp_path / "nonexistent", trust_file=trust_file)
        assert catalog.scan() == []

    def test_scan_finds_agents_in_trusted_plugin(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "Security analysis OWASP vulnerabilities")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert len(result) == 1
        assert result[0].name == "security-expert"
        assert result[0].source_plugin == "ai-delegate"

    def test_scan_result_cached_on_second_call(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "security-expert", "OWASP security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        first = catalog.scan()
        second = catalog.scan()
        assert first is second  # same list object — cached

    def test_invalidate_clears_cache(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "security-expert", "OWASP security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        first = catalog.scan()
        catalog.invalidate()
        second = catalog.scan()
        assert first is not second  # new list after invalidate

    def test_agent_metadata_fields_populated(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "arch-expert",
                     "Architecture pattern design SOLID coupling cohesion",
                     model="sonnet", tools=["Read", "Grep"])
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        agents = catalog.scan()
        assert len(agents) == 1
        a = agents[0]
        assert a.model == "sonnet"
        assert a.tools == ["Read", "Grep"]
        assert "architecture" in a.domains
        assert a.path.exists()

    def test_for_domains_filters_by_domain(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "OWASP security vulnerabilities injection")
        _write_agent(agents_dir, "perf-expert", "database query performance bottleneck")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        sec = catalog.for_domains(["security"])
        assert len(sec) == 1
        assert sec[0].name == "security-expert"

    def test_for_domains_returns_empty_when_no_match(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "perf-expert", "database query performance")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.for_domains(["testing"])
        assert result == []


# ─── S1: Agent Name Validation ───────────────────────────────────────────────


class TestS1AgentNameValidation:
    def test_valid_name_alphanumeric_passes(self):
        assert validate_agent_name("security-expert") == "security-expert"

    def test_valid_name_with_underscore_passes(self):
        assert validate_agent_name("arch_expert_v2") == "arch_expert_v2"

    def test_name_with_space_raises(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("bad name")

    def test_name_with_semicolon_raises(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("bad;name")

    def test_name_with_slash_raises(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("../../../etc/passwd")

    def test_name_with_dollar_raises(self):
        with pytest.raises(ValueError, match="Invalid agent name"):
            validate_agent_name("$PATH")

    def test_agent_with_invalid_name_skipped_during_scan(
        self, plugins_root, plugin_dir, trust_file
    ):
        bad = plugin_dir / "agents" / "bad.md"
        bad.write_text("---\nname: bad name with spaces\ndescription: test\n---\n")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        assert catalog.scan() == []

    def test_agent_with_injection_name_skipped(self, plugins_root, plugin_dir, trust_file):
        bad = plugin_dir / "agents" / "inject.md"
        bad.write_text("---\nname: $(rm -rf /)\ndescription: evil\n---\n")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        assert catalog.scan() == []


# ─── S2: Plugin Trust Boundary ───────────────────────────────────────────────


class TestS2TrustBoundary:
    def test_untrusted_plugin_agents_skipped(self, tmp_path):
        untrusted = tmp_path / "plugins" / "unknown-plugin"
        (untrusted / "agents").mkdir(parents=True)
        _write_agent(untrusted / "agents", "sneaky-expert", "OWASP security analysis")

        trust = tmp_path / "trust.json"
        trust.write_text(json.dumps({"trusted_plugins": ["ai-delegate"]}))

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust)
        assert catalog.scan() == []

    def test_trust_all_flag_bypasses_trust_check(self, tmp_path):
        plugin = tmp_path / "plugins" / "any-plugin"
        (plugin / "agents").mkdir(parents=True)
        _write_agent(plugin / "agents", "any-expert", "security analysis OWASP")

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_all=True)
        assert len(catalog.scan()) == 1

    def test_no_trust_file_trusts_only_ai_delegate(self, tmp_path):
        ai_delegate = tmp_path / "plugins" / "ai-delegate"
        other = tmp_path / "plugins" / "other-plugin"
        (ai_delegate / "agents").mkdir(parents=True)
        (other / "agents").mkdir(parents=True)
        _write_agent(ai_delegate / "agents", "sec", "security analysis OWASP")
        _write_agent(other / "agents", "other", "performance analysis database")

        # No trust_file parameter — default should trust only "ai-delegate"
        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins")
        result = catalog.scan()
        assert len(result) == 1
        assert result[0].source_plugin == "ai-delegate"

    def test_multiple_trusted_plugins_both_scanned(self, tmp_path):
        for plugin_name in ["ai-delegate", "devflow"]:
            p = tmp_path / "plugins" / plugin_name
            (p / "agents").mkdir(parents=True)
            _write_agent(p / "agents", f"{plugin_name}-expert", "security OWASP analysis")

        trust = tmp_path / "trust.json"
        trust.write_text(json.dumps({"trusted_plugins": ["ai-delegate", "devflow"]}))

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust)
        result = catalog.scan()
        assert len(result) == 2
        plugin_names = {a.source_plugin for a in result}
        assert plugin_names == {"ai-delegate", "devflow"}


# ─── S3: Path Traversal ──────────────────────────────────────────────────────


class TestS3PathTraversal:
    def test_symlink_outside_plugin_dir_rejected(self, tmp_path, trust_file):
        plugin = tmp_path / "plugins" / "ai-delegate"
        (plugin / "agents").mkdir(parents=True)

        # File outside the plugin dir
        external = tmp_path / "external.md"
        external.write_text("---\nname: evil\ndescription: pwned\n---\n")

        # Symlink inside agents/ pointing outside
        link = plugin / "agents" / "evil.md"
        link.symlink_to(external)

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust_file)
        result = catalog.scan()
        # Symlink resolves outside agents_dir — must be rejected
        assert result == []


# ─── S4: DoS Protection ──────────────────────────────────────────────────────


class TestS4DoSProtection:
    def test_more_than_100_agents_capped_at_100(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        for i in range(105):
            _write_agent(agents_dir, f"agent-{i:03d}", "security OWASP analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert len(result) == 100

    def test_large_frontmatter_file_skipped(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        # File larger than MAX_FRONTMATTER_SIZE_BYTES (4096)
        large = agents_dir / "huge.md"
        large.write_text("---\nname: huge\ndescription: " + "x" * 5000 + "\n---\n")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert result == []


# ─── Error Handling ──────────────────────────────────────────────────────────


class TestCatalogErrorHandling:
    def test_missing_name_field_skips_file(self, plugins_root, plugin_dir, trust_file):
        (plugin_dir / "agents" / "noname.md").write_text(
            "---\ndescription: no name here\n---\n"
        )
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        assert catalog.scan() == []

    def test_malformed_yaml_skips_file(self, plugins_root, plugin_dir, trust_file):
        (plugin_dir / "agents" / "broken.md").write_text(
            "---\nname: [broken yaml\n---\n"
        )
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        # Malformed YAML produces invalid name → agent is skipped entirely
        result = catalog.scan()
        assert result == []

    def test_missing_description_uses_empty_string(self, plugins_root, plugin_dir, trust_file):
        (plugin_dir / "agents" / "nodesc.md").write_text(
            "---\nname: nodesc-expert\n---\n"
        )
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert len(result) == 1
        assert result[0].description == ""
        assert result[0].domains == []

    def test_missing_tools_defaults_to_empty_list(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "no-tools", "security OWASP analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert result[0].tools == []

    def test_missing_model_defaults_to_empty_string(self, plugins_root, plugin_dir, trust_file):
        _write_agent(plugin_dir / "agents", "no-model", "security OWASP analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert result[0].model == ""

    def test_malformed_trust_file_falls_back_to_ai_delegate_only(self, tmp_path):
        plugin = tmp_path / "plugins" / "ai-delegate"
        (plugin / "agents").mkdir(parents=True)
        _write_agent(plugin / "agents", "sec", "security OWASP analysis")

        bad_trust = tmp_path / "trust.json"
        bad_trust.write_text("NOT VALID JSON{{{{")

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=bad_trust)
        # Should fall back to trusting only ai-delegate
        result = catalog.scan()
        assert len(result) == 1


# ─── Helper Functions ─────────────────────────────────────────────────────────


class TestDetectDomains:
    def test_security_keywords_detected(self):
        assert "security" in _detect_domains("OWASP security vulnerabilities injection")

    def test_performance_keywords_detected(self):
        assert "performance" in _detect_domains("database query performance bottleneck")

    def test_architecture_keywords_detected(self):
        assert "architecture" in _detect_domains("architecture design pattern SOLID coupling")

    def test_multiple_domains_detected(self):
        domains = _detect_domains("security vulnerabilities and architecture patterns")
        assert "security" in domains
        assert "architecture" in domains

    def test_no_matching_keywords_returns_empty(self):
        assert _detect_domains("general purpose text without domain terms") == []

    def test_case_insensitive_matching(self):
        assert "security" in _detect_domains("OWASP SECURITY ANALYSIS")

    def test_domain_keywords_dict_has_expected_domains(self):
        expected = {"security", "performance", "architecture", "code-quality",
                    "testing", "migration", "database"}
        assert expected.issubset(set(DOMAIN_KEYWORDS.keys()))


class TestExtractPluginName:
    def test_extracts_ai_delegate_plugin_name(self, tmp_path):
        path = tmp_path / "ai-delegate" / "agents" / "expert.md"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _extract_plugin_name(path) == "ai-delegate"

    def test_extracts_devflow_plugin_name(self, tmp_path):
        path = tmp_path / "devflow" / "agents" / "code-reviewer.md"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _extract_plugin_name(path) == "devflow"
