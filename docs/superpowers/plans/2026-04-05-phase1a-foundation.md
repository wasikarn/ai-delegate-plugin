# Phase 1A — Foundation (catalog + consensus + complexity) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three pure, independently testable modules — `catalog.py` (agent discovery with S1-S4 security), `consensus.py` (extracted ConsensusCalculator), `complexity.py` (ComplexityAssessor) — without breaking any existing functionality.

**Architecture:** Each new file is a pure Python module with no import cycles. `catalog.py` depends only on stdlib + `models.py`. `consensus.py` depends only on `models.py` + `constants.py`. `complexity.py` depends only on `constants.py`. All existing `ai-delegate audit/analyze/...` commands continue to work unchanged after each task.

**Tech Stack:** Python 3.10+, pytest, stdlib only (pathlib, json, re, hashlib, signal, dataclasses)

---

## File Map

| File | Status | Purpose |
|------|--------|---------|
| `ai_delegate/catalog.py` | **Create** | AgentCatalog — scan `~/.claude/plugins/*/agents/*.md`, enforce S1-S4 |
| `ai_delegate/consensus.py` | **Create** | ConsensusCalculator extracted from `debate/orchestrator.py` |
| `ai_delegate/complexity.py` | **Create** | ComplexityAssessor — deterministic content scoring |
| `tests/test_catalog.py` | **Create** | Full catalog test suite: discovery, S1-S4, domain matching, error handling |
| `tests/test_consensus_extracted.py` | **Create** | Consensus extraction tests |
| `tests/test_complexity.py` | **Modify** | Append ComplexityAssessor tests (keep existing `detect_complexity` tests) |

---

## Task 1: `consensus.py` — Extract ConsensusCalculator

**Files:**

- Create: `ai_delegate/consensus.py`
- Create: `tests/test_consensus_extracted.py`
- Reference: `ai_delegate/debate/orchestrator.py:80-163` (source logic to extract)
- Reference: `ai_delegate/models.py` (Finding, ExpertResult, ConsensusResult types)
- Reference: `ai_delegate/constants.py` (QualityThresholds.CONSENSUS_PERCENTAGE = 80)

**Why first:** Zero dependencies on other new files. Establishes the test pattern before the harder tasks.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_consensus_extracted.py`:

```python
"""Tests for ai_delegate/consensus.py — extracted ConsensusCalculator."""
import pytest
from ai_delegate.consensus import ConsensusCalculator, normalize_finding
from ai_delegate.models import ExpertResult, Finding, ConsensusResult


class TestConsensusCalculatorEmpty:
    def test_empty_list_returns_zero_score(self):
        result = ConsensusCalculator.calculate([])
        assert result.score == 0.0
        assert result.consensus_findings == []
        assert result.disputed_findings == []
        assert result.unique_findings == {}

    def test_all_empty_findings_returns_perfect_score(self):
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[]),
        ]
        assert ConsensusCalculator.calculate(results).score == 1.0


class TestConsensusCalculatorAgreement:
    def test_full_agreement_returns_score_one(self):
        f = Finding(severity="high", issue="XSS")
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[f]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert result.score == 1.0
        assert len(result.consensus_findings) == 1

    def test_no_agreement_returns_zero_score(self):
        results = [
            ExpertResult(expert_name="e1", expert_type="security",
                         findings=[Finding(severity="high", issue="XSS")]),
            ExpertResult(expert_name="e2", expert_type="security",
                         findings=[Finding(severity="medium", issue="CSRF")]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert result.score == 0.0
        assert len(result.disputed_findings) == 0
        assert len(result.unique_findings) == 2  # both are unique

    def test_disputed_finding_two_of_three_experts(self):
        f = Finding(severity="high", issue="SQL injection")
        results = [
            ExpertResult(expert_name="e1", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e2", expert_type="security", findings=[f]),
            ExpertResult(expert_name="e3", expert_type="security",
                         findings=[Finding(severity="low", issue="info leak")]),
        ]
        # threshold = ceil(3 * 80/100) = ceil(2.4) = 3 → SQL injection appears 2x = disputed
        result = ConsensusCalculator.calculate(results)
        assert len(result.disputed_findings) == 1
        assert result.disputed_findings[0].issue == "SQL injection"

    def test_unique_finding_keyed_by_expert_name(self):
        results = [
            ExpertResult(expert_name="owasp", expert_type="security",
                         findings=[Finding(severity="high", issue="only owasp finds this")]),
            ExpertResult(expert_name="auth", expert_type="security", findings=[]),
        ]
        result = ConsensusCalculator.calculate(results)
        assert "owasp" in result.unique_findings
        assert result.unique_findings["owasp"][0].issue == "only owasp finds this"


class TestNormalizeFinding:
    def test_canonical_format_passthrough(self):
        raw = {"severity": "high", "issue": "XSS", "recommendation": "sanitize"}
        f = normalize_finding(raw)
        assert f.severity == "high"
        assert f.issue == "XSS"
        assert f.recommendation == "sanitize"

    def test_domain_format_title_mapped_to_issue(self):
        raw = {"severity": "high", "title": "SQL injection", "category": "OWASP-A03",
               "file": "db.py", "line": 42, "recommendation": "use params"}
        f = normalize_finding(raw)
        assert f.issue == "SQL injection"
        assert f.location == "db.py:42"

    def test_missing_severity_defaults_to_medium(self):
        raw = {"issue": "unknown risk"}
        f = normalize_finding(raw)
        assert f.severity == "medium"

    def test_missing_issue_uses_empty_string(self):
        raw = {"severity": "low"}
        f = normalize_finding(raw)
        assert f.issue == ""
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
python -m pytest tests/test_consensus_extracted.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'ai_delegate.consensus'`

- [ ] **Step 3: Write `ai_delegate/consensus.py`**

```python
"""
consensus.py — Pure consensus calculation extracted from debate/orchestrator.py.

Responsibilities:
- ConsensusCalculator.calculate(): aggregate ExpertResult list → ConsensusResult
- normalize_finding(): translate domain-specific finding dicts to canonical Finding

No side effects. Thread-safe (reads only). Does not import from debate/.
"""
import math
from typing import Dict, List

from ai_delegate.constants import QualityThresholds
from ai_delegate.models import ConsensusResult, ExpertResult, Finding


class ConsensusCalculator:
    """Calculate consensus between expert findings.

    Deduplication key: (finding.severity.lower(), finding.issue.lower())
    Agreement threshold: ceil(N_experts * CONSENSUS_PERCENTAGE / 100)
    """

    @staticmethod
    def calculate(expert_results: List[ExpertResult]) -> ConsensusResult:
        """Calculate agreement score between expert findings.

        Args:
            expert_results: List of expert analysis results. Not modified.

        Returns:
            ConsensusResult — new object. findings are references, not copies.
        """
        if not expert_results:
            return ConsensusResult(score=0.0)

        all_findings: List[Finding] = []
        for result in expert_results:
            all_findings.extend(result.findings)

        if not all_findings:
            return ConsensusResult(score=1.0)

        finding_counts: Dict[tuple, int] = {}
        finding_by_key: Dict[tuple, List[Finding]] = {}
        finding_key_to_expert: Dict[tuple, str] = {}

        for result in expert_results:
            for finding in result.findings:
                key = (finding.severity.lower(), finding.issue.lower())
                finding_counts[key] = finding_counts.get(key, 0) + 1
                if key not in finding_by_key:
                    finding_by_key[key] = []
                    finding_key_to_expert[key] = result.expert_name
                finding_by_key[key].append(finding)

        threshold = math.ceil(
            len(expert_results) * QualityThresholds.CONSENSUS_PERCENTAGE / 100
        )

        consensus_findings: List[Finding] = []
        disputed_findings: List[Finding] = []
        unique_findings: Dict[str, List[Finding]] = {}

        for key, count in finding_counts.items():
            if count >= threshold:
                consensus_findings.append(finding_by_key[key][0])
            elif count > 1:
                disputed_findings.append(finding_by_key[key][0])
            else:
                expert_name = finding_key_to_expert.get(key, "unknown")
                if expert_name not in unique_findings:
                    unique_findings[expert_name] = []
                unique_findings[expert_name].append(finding_by_key[key][0])

        total_unique = len(finding_counts)
        consensus_count = sum(1 for c in finding_counts.values() if c >= threshold)
        score = consensus_count / total_unique if total_unique > 0 else 1.0

        disagreement_parts = []
        for expert_name, findings in unique_findings.items():
            issues = [f.issue for f in findings[:3]]
            if issues:
                disagreement_parts.append(
                    f"{expert_name} uniquely raised: {', '.join(issues)}"
                )
        disagreement_summary = "; ".join(disagreement_parts)

        return ConsensusResult(
            score=score,
            consensus_findings=consensus_findings,
            disputed_findings=disputed_findings,
            unique_findings=unique_findings,
            disagreement_summary=disagreement_summary,
        )


def normalize_finding(raw: dict) -> Finding:
    """Convert domain-specific finding dict to canonical Finding.

    Supports two formats:
    1. Canonical (schema_version: "1.0"): {"severity", "issue", "recommendation", "location"}
    2. Domain format: {"severity", "title", "category", "file", "line", "description", "recommendation"}
    """
    issue = raw.get("title") or raw.get("issue", "")
    location = raw.get("location")
    if not location and raw.get("file"):
        location = f"{raw['file']}:{raw.get('line', '')}"

    return Finding(
        severity=raw.get("severity", "medium"),
        issue=issue,
        location=location,
        recommendation=raw.get("recommendation"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_consensus_extracted.py -v
```

Expected: all 9 tests PASS

- [ ] **Step 5: Verify existing tests still pass**

```bash
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -10
```

Expected: same pass count as before (no regressions).

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/consensus.py tests/test_consensus_extracted.py
git commit -m "feat: add consensus.py — extracted ConsensusCalculator from debate/orchestrator"
```

---

## Task 2: `complexity.py` — ComplexityAssessor

**Files:**

- Create: `ai_delegate/complexity.py`
- Modify: `tests/test_complexity.py` (append new class, keep existing tests)
- Reference: `ai_delegate/constants.py` (ComplexityThresholds.LOW_LINES=100, MEDIUM_LINES=500)
- Reference: spec section "Intelligence Layer / complexity.py"

**Note:** Existing `tests/test_complexity.py` tests `detect_complexity()` from `router.py` — those stay. New tests go in a new class at the bottom of the file.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_complexity.py` (after the last existing class):

```python
# ─── New tests for ai_delegate/complexity.py ComplexityAssessor ─────────────

from ai_delegate.complexity import ComplexityAssessor, ComplexityScore


class TestComplexityAssessorLevel:
    def test_low_under_100_lines(self):
        content = "\n".join(["x = 1"] * 50)
        score = ComplexityAssessor.assess(content)
        assert score.level == "low"
        assert score.line_count == 50

    def test_medium_100_to_500_lines(self):
        content = "\n".join(["x = 1"] * 300)
        score = ComplexityAssessor.assess(content)
        assert score.level == "medium"

    def test_high_over_500_lines(self):
        content = "\n".join(["x = 1"] * 600)
        score = ComplexityAssessor.assess(content)
        assert score.level == "high"


class TestComplexityAssessorDomains:
    def test_security_terms_detected(self):
        content = "verify password using jwt token and ssl cert"
        score = ComplexityAssessor.assess(content)
        assert "security" in score.domains
        assert score.security_signals > 0

    def test_performance_terms_detected(self):
        content = "optimize database query with cache and async"
        score = ComplexityAssessor.assess(content)
        assert "performance" in score.domains

    def test_architecture_terms_detected(self):
        content = "interface factory singleton dependency injection"
        score = ComplexityAssessor.assess(content)
        assert "architecture" in score.domains

    def test_no_domain_terms_returns_empty_domains(self):
        content = "x = 1\ny = 2\nprint(x + y)"
        score = ComplexityAssessor.assess(content)
        assert score.domains == []

    def test_high_security_signals_bumps_low_to_medium(self):
        # 6+ security terms should bump low→medium
        terms = ["password", "token", "secret", "crypto", "hash", "jwt", "oauth"]
        content = " ".join(terms) * 3  # 21 occurrences
        score = ComplexityAssessor.assess(content)
        # line count is 1 → would be "low" without bump
        assert score.level in ("medium", "high")


class TestComplexityAssessorFiles:
    def test_assess_files_max_level(self, tmp_path):
        low_file = tmp_path / "small.py"
        high_file = tmp_path / "large.py"
        low_file.write_text("\n".join(["x = 1"] * 50))
        high_file.write_text("\n".join(["x = 1"] * 600))
        score = ComplexityAssessor.assess_files([low_file, high_file])
        assert score.level == "high"
        assert score.file_count == 2
        assert score.line_count == 650

    def test_assess_files_merges_domains(self, tmp_path):
        auth_file = tmp_path / "auth.py"
        query_file = tmp_path / "query.py"
        auth_file.write_text("jwt token password")
        query_file.write_text("database query cache")
        score = ComplexityAssessor.assess_files([auth_file, query_file])
        assert "security" in score.domains
        assert "performance" in score.domains
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_complexity.py -k "TestComplexityAssessor" -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'ai_delegate.complexity'`

- [ ] **Step 3: Write `ai_delegate/complexity.py`**

```python
"""
complexity.py — Deterministic content complexity assessment.

ComplexityAssessor uses rule-based scoring (line count + keyword signals).
No AI reasoning. Output is stable and reproducible for the same input.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ai_delegate.constants import ComplexityThresholds


@dataclass
class ComplexityScore:
    level: str                        # "low" | "medium" | "high"
    domains: list[str] = field(default_factory=list)   # detected domain keywords
    file_count: int = 1
    line_count: int = 0
    security_signals: int = 0         # count of security-relevant term occurrences


_LEVELS = ["low", "medium", "high"]


def _max_level(a: str, b: str) -> str:
    return _LEVELS[max(_LEVELS.index(a), _LEVELS.index(b))]


class ComplexityAssessor:
    """Deterministic complexity scoring using line counts and keyword detection."""

    SECURITY_TERMS = frozenset({
        "password", "token", "secret", "crypto", "hash", "jwt", "oauth",
        "auth", "session", "cookie", "cert", "ssl", "tls",
    })
    PERF_TERMS = frozenset({
        "query", "n+1", "cache", "index", "latency", "timeout", "async",
    })
    ARCH_TERMS = frozenset({
        "interface", "abstract", "factory", "singleton", "dependency",
        "coupling", "cohesion", "pattern", "service", "repository",
    })

    @staticmethod
    def assess(content: str, filename: str = "") -> ComplexityScore:
        """Score a single content string.

        Level rules (applied in order, highest wins):
        1. line_count >= MEDIUM_LINES (500) → high
        2. line_count >= LOW_LINES (100)   → medium
        3. security_signals > 5            → bump to at least medium
        4. default                         → low
        """
        lines = content.splitlines()
        line_count = len(lines)
        content_lower = content.lower()

        if line_count >= ComplexityThresholds.MEDIUM_LINES:
            level = "high"
        elif line_count >= ComplexityThresholds.LOW_LINES:
            level = "medium"
        else:
            level = "low"

        domains: list[str] = []

        sec_count = sum(content_lower.count(t) for t in ComplexityAssessor.SECURITY_TERMS)
        if sec_count > 0:
            domains.append("security")
            if sec_count > 5:
                level = _max_level(level, "medium")

        if any(t in content_lower for t in ComplexityAssessor.PERF_TERMS):
            domains.append("performance")

        if any(t in content_lower for t in ComplexityAssessor.ARCH_TERMS):
            domains.append("architecture")

        return ComplexityScore(
            level=level,
            domains=domains,
            file_count=1,
            line_count=line_count,
            security_signals=sec_count,
        )

    @staticmethod
    def assess_files(paths: list[Path]) -> ComplexityScore:
        """Aggregate complexity across multiple files.

        Level: max level across all files.
        Domains: union of all domains.
        """
        scores = [ComplexityAssessor.assess(p.read_text(), p.name) for p in paths]
        all_domains = list({d for s in scores for d in s.domains})
        max_level = max((s.level for s in scores), key=lambda lvl: _LEVELS.index(lvl))
        return ComplexityScore(
            level=max_level,
            domains=all_domains,
            file_count=len(paths),
            line_count=sum(s.line_count for s in scores),
            security_signals=sum(s.security_signals for s in scores),
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_complexity.py -v
```

Expected: all tests PASS (existing + new ComplexityAssessor tests)

- [ ] **Step 5: Verify no regressions**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: same pass count as after Task 1.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/complexity.py tests/test_complexity.py
git commit -m "feat: add complexity.py — ComplexityAssessor (deterministic content scoring)"
```

---

## Task 3: `catalog.py` — AgentCatalog with S1-S4 Security

**Files:**

- Create: `ai_delegate/catalog.py`
- Create: `tests/test_catalog.py`
- Reference: spec section "Security Requirements S1-S4" and "Agent Catalog"

This is the most complex task. Work through each security requirement in a separate test class.

- [ ] **Step 1: Write failing tests — discovery and domain matching**

Create `tests/test_catalog.py`:

```python
"""Tests for ai_delegate/catalog.py — AgentCatalog."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

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
    """Helper: write a valid agent .md file."""
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

    def test_scan_finds_agents_in_trusted_plugin(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "Security analysis OWASP")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert len(result) == 1
        assert result[0].name == "security-expert"
        assert result[0].source_plugin == "ai-delegate"

    def test_scan_result_cached_on_second_call(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "OWASP security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        first = catalog.scan()
        second = catalog.scan()
        assert first is second  # same list object

    def test_invalidate_clears_cache(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "OWASP security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        first = catalog.scan()
        catalog.invalidate()
        second = catalog.scan()
        assert first is not second

    def test_agent_metadata_fields_populated(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "arch-expert", "Architecture pattern design SOLID",
                     model="sonnet", tools=["Read", "Grep"])
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        agents = catalog.scan()
        assert agents[0].model == "sonnet"
        assert agents[0].tools == ["Read", "Grep"]
        assert "architecture" in agents[0].domains

    def test_for_domains_filters_by_domain(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        _write_agent(agents_dir, "security-expert", "OWASP security vulnerabilities")
        _write_agent(agents_dir, "perf-expert", "database query performance bottleneck")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        sec = catalog.for_domains(["security"])
        assert all("security" in a.domains for a in sec)
        assert not any(a.name == "perf-expert" for a in sec)


# ─── S1: Agent Name Validation ──────────────────────────────────────────────


class TestS1AgentNameValidation:
    def test_valid_name_passes(self):
        assert validate_agent_name("security-expert") == "security-expert"
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

    def test_agent_with_invalid_name_skipped_during_scan(
        self, plugins_root, plugin_dir, trust_file
    ):
        agents_dir = plugin_dir / "agents"
        # Write agent with unsafe name in frontmatter
        bad = agents_dir / "bad.md"
        bad.write_text("---\nname: bad name with spaces\ndescription: test\n---\n")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert result == []  # skipped


# ─── S2: Plugin Trust Boundary ──────────────────────────────────────────────


class TestS2TrustBoundary:
    def test_untrusted_plugin_agents_skipped(self, tmp_path):
        untrusted = tmp_path / "plugins" / "unknown-plugin"
        (untrusted / "agents").mkdir(parents=True)
        _write_agent(untrusted / "agents", "sneaky-expert", "OWASP security")

        trust = tmp_path / "trust.json"
        trust.write_text(json.dumps({"trusted_plugins": ["ai-delegate"]}))

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust)
        assert catalog.scan() == []

    def test_trust_all_flag_bypasses_trust_check(self, tmp_path):
        plugin = tmp_path / "plugins" / "any-plugin"
        (plugin / "agents").mkdir(parents=True)
        _write_agent(plugin / "agents", "any-expert", "security analysis")

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_all=True)
        assert len(catalog.scan()) == 1

    def test_no_trust_file_trusts_only_ai_delegate(self, tmp_path):
        ai_delegate = tmp_path / "plugins" / "ai-delegate"
        other = tmp_path / "plugins" / "other-plugin"
        (ai_delegate / "agents").mkdir(parents=True)
        (other / "agents").mkdir(parents=True)
        _write_agent(ai_delegate / "agents", "sec", "security analysis")
        _write_agent(other / "agents", "other", "performance analysis")

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins")  # no trust_file
        result = catalog.scan()
        assert len(result) == 1
        assert result[0].source_plugin == "ai-delegate"


# ─── S3: Path Traversal ──────────────────────────────────────────────────────


class TestS3PathTraversal:
    def test_symlink_outside_plugin_dir_rejected(self, tmp_path, trust_file):
        plugin = tmp_path / "plugins" / "ai-delegate"
        (plugin / "agents").mkdir(parents=True)

        # Create a file outside the plugin dir
        external = tmp_path / "external.md"
        external.write_text("---\nname: evil\ndescription: pwned\n---\n")

        # Create a symlink inside agents/ pointing outside
        link = plugin / "agents" / "evil.md"
        link.symlink_to(external)

        catalog = AgentCatalog(plugins_dir=tmp_path / "plugins", trust_file=trust_file)
        result = catalog.scan()
        # Symlink to external path must be rejected
        assert result == []


# ─── S4: DoS Protection ──────────────────────────────────────────────────────


class TestS4DoSProtection:
    def test_more_than_100_agents_truncated(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        for i in range(105):
            _write_agent(agents_dir, f"agent-{i}", "security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert len(result) == 100  # capped

    def test_large_frontmatter_file_skipped(self, plugins_root, plugin_dir, trust_file):
        agents_dir = plugin_dir / "agents"
        # Write a file with frontmatter > 4096 bytes
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
        assert catalog.scan() == []

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
        _write_agent(plugin_dir / "agents", "no-tools", "security analysis")
        catalog = AgentCatalog(plugins_dir=plugins_root, trust_file=trust_file)
        result = catalog.scan()
        assert result[0].tools == []


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


class TestExtractPluginName:
    def test_extracts_plugin_name_from_standard_path(self, tmp_path):
        path = tmp_path / "ai-delegate" / "agents" / "expert.md"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _extract_plugin_name(path) == "ai-delegate"

    def test_extracts_devflow_plugin_name(self, tmp_path):
        path = tmp_path / "devflow" / "agents" / "code-reviewer.md"
        path.parent.mkdir(parents=True)
        path.touch()
        assert _extract_plugin_name(path) == "devflow"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_catalog.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'ai_delegate.catalog'`

- [ ] **Step 3: Write `ai_delegate/catalog.py`**

```python
"""
catalog.py — Agent discovery for all installed Claude Code plugins.

Scans ~/.claude/plugins/*/agents/*.md and returns AgentMetadata list.
Enforces security requirements S1-S4:
  S1: Agent name validation (command injection prevention)
  S2: Plugin trust boundary (allowlist via trust file)
  S3: Path traversal prevention (canonical path resolution)
  S4: DoS protection (100 agent cap, 5s timeout, 4096 byte frontmatter limit)
"""
from __future__ import annotations

import json
import logging
import re
import signal
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ─── S1: Name validation ─────────────────────────────────────────────────────

AGENT_NAME_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


def validate_agent_name(name: str) -> str:
    """Validate agent name is safe for subprocess use.

    Raises ValueError if name contains characters outside [a-zA-Z0-9_-].
    """
    if not AGENT_NAME_PATTERN.match(name):
        raise ValueError(
            f"Invalid agent name {name!r}: must match [a-zA-Z0-9_-]+"
        )
    return name


# ─── S4: Limits ──────────────────────────────────────────────────────────────

MAX_AGENTS_PER_PLUGIN = 100
SCAN_TIMEOUT_SECONDS = 5
MAX_FRONTMATTER_SIZE_BYTES = 4096


# ─── Domain matching ─────────────────────────────────────────────────────────

DOMAIN_KEYWORDS: dict[str, list[str]] = {
    "security":     ["security", "owasp", "vulnerabilit", "injection", "auth", "crypto"],
    "performance":  ["performance", "complexity", "database", "memory", "bottleneck", "query"],
    "architecture": ["architecture", "design", "pattern", "solid", "coupling", "cohesion"],
    "code-quality": ["quality", "maintainab", "readab", "code smell", "refactor", "clean"],
    "testing":      ["test", "coverage", "mock", "assertion", "spec"],
    "migration":    ["migration", "migrate", "breaking change", "api contract", "deprecat"],
    "database":     ["database", "sql", "migration", "schema", "index", "query"],
}


def _detect_domains(description: str) -> list[str]:
    """Return list of domain keys whose keywords appear in description (lowercase)."""
    desc_lower = description.lower()
    return [
        domain
        for domain, keywords in DOMAIN_KEYWORDS.items()
        if any(kw in desc_lower for kw in keywords)
    ]


def _extract_plugin_name(agent_path: Path) -> str:
    """Extract plugin name from path ~/.claude/plugins/<name>/agents/<file>.md"""
    try:
        return agent_path.parents[1].name
    except IndexError:
        return "unknown"


# ─── Data model ──────────────────────────────────────────────────────────────

@dataclass
class AgentMetadata:
    name: str            # validated [a-zA-Z0-9_-]+
    description: str     # raw description from frontmatter
    source_plugin: str   # e.g. "ai-delegate", "devflow"
    model: str           # default model; "" if not specified
    tools: list[str]     # e.g. ["Read", "Grep"]
    path: Path           # resolved canonical path
    domains: list[str] = field(default_factory=list)  # from _detect_domains


# ─── Frontmatter parser ──────────────────────────────────────────────────────

def _parse_frontmatter(text: str) -> dict:
    """Extract YAML frontmatter from markdown text.

    Returns empty dict if no frontmatter block found or YAML is malformed.
    """
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    yaml_block = text[3:end].strip()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(yaml_block) or {}
    except Exception:
        # Fallback: minimal line-by-line parser for simple frontmatter
        result: dict = {}
        lines = yaml_block.splitlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            if ":" in line and not line.strip().startswith("#"):
                k, _, v = line.partition(":")
                k = k.strip()
                v = v.strip()
                if v == "|":
                    # Multiline block — collect indented lines
                    block_lines = []
                    i += 1
                    while i < len(lines) and (lines[i].startswith("  ") or lines[i] == ""):
                        block_lines.append(lines[i].strip())
                        i += 1
                    result[k] = " ".join(block_lines)
                    continue
                elif v.startswith("[") and v.endswith("]"):
                    try:
                        result[k] = json.loads(v)
                    except Exception:
                        result[k] = v
                else:
                    result[k] = v
            i += 1
        return result


# ─── Main catalog ─────────────────────────────────────────────────────────────

class AgentCatalog:
    """Discover agent definitions from all installed Claude Code plugins.

    Usage:
        catalog = AgentCatalog()
        agents = catalog.scan()                   # all trusted agents
        sec_agents = catalog.for_domains(["security"])
        catalog.invalidate()                       # clear in-memory cache
    """

    def __init__(
        self,
        plugins_dir: Path | None = None,
        trust_file: Path | None = None,
        trust_all: bool = False,
    ):
        self._plugins_dir = plugins_dir or Path.home() / ".claude" / "plugins"
        self._trust_all = trust_all
        self._trusted = self._load_trust(trust_file)
        self._cache: list[AgentMetadata] | None = None

    def _load_trust(self, trust_file: Path | None) -> set[str]:
        default = Path.home() / ".claude" / "ai-delegate-trust.json"
        path = trust_file or default
        if path.exists():
            try:
                data = json.loads(path.read_text())
                return set(data.get("trusted_plugins", []))
            except Exception:
                logger.warning("Could not parse trust file %s — trusting only ai-delegate", path)
        return {"ai-delegate"}

    def _is_trusted(self, source_plugin: str) -> bool:
        return self._trust_all or source_plugin in self._trusted

    def _safe_agent_path(self, candidate: Path, plugin_dir: Path) -> Path | None:
        """Return canonical path only if it is under plugin_dir. Rejects symlinks pointing outside."""
        try:
            resolved = candidate.resolve()
        except Exception:
            return None
        plugin_dir_resolved = plugin_dir.resolve()
        if resolved.is_relative_to(plugin_dir_resolved):
            return resolved
        logger.warning("Path traversal rejected: %s → %s", candidate, resolved)
        return None

    def _parse_agent_file(self, md_file: Path, plugin_dir: Path, source_plugin: str) -> AgentMetadata | None:
        """Parse one agent .md file. Returns None if file should be skipped."""
        # S3: path traversal check
        safe_path = self._safe_agent_path(md_file, plugin_dir)
        if safe_path is None:
            return None

        # S4: frontmatter size limit
        try:
            stat = md_file.stat(follow_symlinks=False)
            if stat.st_size > MAX_FRONTMATTER_SIZE_BYTES:
                logger.warning("Skipping oversized agent file: %s", md_file)
                return None
            text = md_file.read_text(errors="replace")
        except Exception as e:
            logger.warning("Could not read agent file %s: %s", md_file, e)
            return None

        try:
            fm = _parse_frontmatter(text)
        except Exception as e:
            logger.warning("Malformed frontmatter in %s: %s", md_file, e)
            return None

        # Required: name
        name = fm.get("name", "")
        if not name:
            logger.warning("Missing name field in %s — skipping", md_file)
            return None

        # S1: name validation
        try:
            validate_agent_name(str(name))
        except ValueError:
            logger.warning("Skipping agent with unsafe name: %r in %s", name, md_file)
            return None

        description = fm.get("description", "")
        if isinstance(description, str):
            description = description.strip()
        else:
            description = ""

        model = str(fm.get("model", "") or "")
        raw_tools = fm.get("tools", [])
        tools = raw_tools if isinstance(raw_tools, list) else []
        domains = _detect_domains(description)

        return AgentMetadata(
            name=str(name),
            description=description,
            source_plugin=source_plugin,
            model=model,
            tools=tools,
            path=safe_path,
            domains=domains,
        )

    def _scan_all(self) -> list[AgentMetadata]:
        """Scan all trusted plugin agent directories."""
        results: list[AgentMetadata] = []

        if not self._plugins_dir.exists():
            return results

        for plugin_dir in sorted(self._plugins_dir.iterdir()):
            if not plugin_dir.is_dir():
                continue

            source_plugin = plugin_dir.name

            # S2: trust boundary
            if not self._is_trusted(source_plugin):
                continue

            agents_dir = plugin_dir / "agents"
            if not agents_dir.is_dir():
                continue

            count = 0
            for md_file in sorted(agents_dir.glob("*.md")):
                if count >= MAX_AGENTS_PER_PLUGIN:
                    logger.warning(
                        "Plugin %s has >%d agents — loading first %d only",
                        source_plugin,
                        MAX_AGENTS_PER_PLUGIN,
                        MAX_AGENTS_PER_PLUGIN,
                    )
                    break

                metadata = self._parse_agent_file(md_file, agents_dir, source_plugin)
                if metadata is not None:
                    results.append(metadata)
                    count += 1

        return results

    def _scan_with_timeout(self) -> list[AgentMetadata]:
        """Run _scan_all with S4 timeout protection."""
        def _handler(signum, frame):
            raise TimeoutError(f"Catalog scan exceeded {SCAN_TIMEOUT_SECONDS} seconds")

        old_handler = signal.signal(signal.SIGALRM, _handler)
        signal.alarm(SCAN_TIMEOUT_SECONDS)
        try:
            return self._scan_all()
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def scan(self) -> list[AgentMetadata]:
        """Scan all trusted plugins for agents. Returns cached result if already scanned."""
        if self._cache is not None:
            return self._cache
        self._cache = self._scan_with_timeout()
        return self._cache

    def for_domains(self, domains: list[str]) -> list[AgentMetadata]:
        """Return agents whose detected domains overlap with the given domains list."""
        all_agents = self.scan()
        domains_set = set(domains)
        return [a for a in all_agents if domains_set & set(a.domains)]

    def invalidate(self) -> None:
        """Clear in-memory cache (call if plugins installed during session)."""
        self._cache = None
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_catalog.py -v
```

Expected: all tests PASS. If PyYAML is not installed, the fallback parser handles simple frontmatter — verify by checking if `yaml` import fails gracefully:

```bash
python -c "import yaml; print('yaml available')" 2>/dev/null || echo "yaml not available, fallback parser active"
```

- [ ] **Step 5: Verify no regressions**

```bash
python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: same pass count as after Task 2.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/catalog.py tests/test_catalog.py
git commit -m "feat: add catalog.py — AgentCatalog with S1-S4 security (agent discovery)"
```

---

## Task 4: Integration Check + CHANGELOG Update

**Files:**

- Modify: `CHANGELOG.md`
- Modify: `ai_delegate/__init__.py` (add exports)

- [ ] **Step 1: Add exports to `__init__.py`**

Read `ai_delegate/__init__.py` first, then add:

```python
# Add these imports to the existing __init__.py public API section:
from ai_delegate.consensus import ConsensusCalculator, normalize_finding
from ai_delegate.complexity import ComplexityAssessor, ComplexityScore
from ai_delegate.catalog import AgentCatalog, AgentMetadata, DOMAIN_KEYWORDS
```

- [ ] **Step 2: Verify imports work**

```bash
python -c "from ai_delegate import ConsensusCalculator, ComplexityAssessor, AgentCatalog; print('imports ok')"
```

Expected: `imports ok`

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -15
```

Expected: all existing tests PASS plus new tests from Tasks 1-3.

- [ ] **Step 4: Update CHANGELOG.md**

Read `CHANGELOG.md` and prepend to the top (after the title) under a new `[Unreleased]` section:

```markdown
## [Unreleased]

### Added
- `consensus.py` — `ConsensusCalculator` extracted from `debate/orchestrator.py` (pure, no side effects)
- `complexity.py` — `ComplexityAssessor` for deterministic content complexity scoring
- `catalog.py` — `AgentCatalog` for discovering agents from installed plugins with S1-S4 security:
  - S1: Agent name validation (command injection prevention)
  - S2: Plugin trust boundary (`~/.claude/ai-delegate-trust.json`)
  - S3: Path traversal prevention (canonical path resolution)
  - S4: DoS protection (100 agent cap, 5s timeout, 4096 byte frontmatter limit)
```

- [ ] **Step 5: Final commit**

```bash
git add ai_delegate/__init__.py CHANGELOG.md
git commit -m "chore: export new Phase 1A modules from __init__.py, update CHANGELOG"
```

---

## Self-Review

Spec coverage check:

- S1 agent name validation → `validate_agent_name()` + tests ✓
- S2 plugin trust boundary → `_load_trust()`, `_is_trusted()` + tests ✓
- S3 path traversal → `_safe_agent_path()` + symlink test ✓
- S4 DoS protection → 100 agent cap + frontmatter size limit + 5s timeout + tests ✓
- `ConsensusCalculator.calculate()` extracted from debate/orchestrator.py ✓
- `normalize_finding()` handles both canonical and domain-specific formats ✓
- `ComplexityAssessor.assess()` and `assess_files()` ✓
- Domain detection (SECURITY_TERMS, PERF_TERMS, ARCH_TERMS) ✓
- No existing tests broken — new files are additions, not replacements ✓

Phase 1B plan (selector.py, path_selector.py, cache.py, CLI commands) builds on these foundations and should be written after this plan completes.
