"""Tests for CLI utility subcommands: catalog, assess, consensus, assign, memory-check."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch


class TestCatalogSubcommand:
    def test_catalog_json_empty(self, capsys):
        """Returns empty JSON array when no agents found."""
        from ai_delegate.cli import _handle_catalog_subcommand
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[]):
            with pytest.raises(SystemExit) as exc:
                _handle_catalog_subcommand(["--json"])
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []

    def test_catalog_domain_filter(self, capsys):
        """Filters agents by domain."""
        from ai_delegate.cli import _handle_catalog_subcommand
        from ai_delegate.catalog import AgentMetadata
        agent = AgentMetadata(
            name="security-expert",
            description="OWASP",
            source_plugin="ai-delegate",
            model="",
            tools=[],
            path=Path("/fake/path.md"),
            domains=["security"],
        )
        with patch("ai_delegate.catalog.AgentCatalog.for_domains", return_value=[agent]):
            with pytest.raises(SystemExit) as exc:
                _handle_catalog_subcommand(["--domain", "security", "--json"])
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["name"] == "security-expert"
        assert data[0]["domains"] == ["security"]


class TestAssessSubcommand:
    def test_assess_returns_complexity_json(self, tmp_path, capsys):
        """Returns complexity JSON for a real file."""
        src = tmp_path / "auth.py"
        src.write_text("def login(user, pw): pass\n" * 10)
        from ai_delegate.cli import _handle_assess_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_assess_subcommand(["--file", str(src)])
        assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["level"] in ("low", "medium", "high")
        assert isinstance(data["domains"], list)
        assert "line_count" in data

    def test_assess_missing_file_exits_1(self):
        """Exits 1 on missing file."""
        from ai_delegate.cli import _handle_assess_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_assess_subcommand(["--file", "/nonexistent/path.py"])
        assert exc.value.code == 1


class TestConsensusSubcommand:
    def test_consensus_single_expert_finding(self, capsys):
        """Single expert finding returns score and tier."""
        findings = json.dumps([
            {"expert": "security", "severity": "high", "issue": "SQL injection", "recommendation": "use params"},
        ])
        from ai_delegate.cli import _handle_consensus_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_consensus_subcommand(["--findings", findings])
        assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert "score" in data
        assert data["tier"] in ("fast", "standard", "deep")
        assert isinstance(data["consensus_findings"], list)
        assert isinstance(data["disputed_findings"], list)

    def test_consensus_invalid_json_exits_1(self):
        """Exits 1 on malformed JSON."""
        from ai_delegate.cli import _handle_consensus_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_consensus_subcommand(["--findings", "not-json"])
        assert exc.value.code == 1

    def test_consensus_empty_findings(self, capsys):
        """Empty findings array returns deep tier."""
        from ai_delegate.cli import _handle_consensus_subcommand
        with pytest.raises(SystemExit) as exc:
            _handle_consensus_subcommand(["--findings", "[]"])
        assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data["tier"] == "deep"


class TestAssignSubcommand:
    def test_assign_returns_assignments(self, capsys):
        """Returns path assignments for known agents."""
        from ai_delegate.catalog import AgentMetadata
        from ai_delegate.cli import _handle_assign_subcommand
        agent = AgentMetadata(
            name="security-expert",
            description="OWASP",
            source_plugin="ai-delegate",
            model="",
            tools=[],
            path=Path("/fake/path.md"),
            domains=["security"],
        )
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[agent]):
            with pytest.raises(SystemExit) as exc:
                _handle_assign_subcommand(["--agents", "security-expert", "--complexity", "low"])
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert len(data) == 1
        assert data[0]["agent"] == "security-expert"
        assert data[0]["path"] in ("sdk", "cli", "agent")

    def test_assign_unknown_agent_skipped(self, capsys):
        """Skips unknown agent names."""
        from ai_delegate.cli import _handle_assign_subcommand
        with patch("ai_delegate.catalog.AgentCatalog.scan", return_value=[]):
            with pytest.raises(SystemExit) as exc:
                _handle_assign_subcommand(["--agents", "ghost-agent", "--complexity", "low"])
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data == []


class TestMemoryCheckSubcommand:
    def test_memory_check_miss(self, capsys):
        """Returns hit:false when check_cache returns None."""
        from ai_delegate.cli import _handle_memory_check_subcommand
        with patch("ai_delegate.memory.AnalysisMemory") as MockMem:
            MockMem.return_value.check_cache.return_value = None
            with pytest.raises(SystemExit) as exc:
                _handle_memory_check_subcommand([
                    "--content-hash", "abc123",
                    "--experts", "security-expert",
                    "--task", "audit",
                ])
            assert exc.value.code == 0
        data = json.loads(capsys.readouterr().out)
        assert data == {"hit": False}
