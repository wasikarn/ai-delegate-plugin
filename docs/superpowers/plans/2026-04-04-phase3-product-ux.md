# Phase 3: Product UX & Outputs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add structured output formats, workflow modes, and consensus disagreement detail to make ai-delegate outputs actionable.

**Architecture:** New `OutputFormatter` and `FlowConfig` modules that wrap the existing `DebateOrchestrator`. No changes to orchestrator internals — all new behavior is post-processing. Consensus disagreement is surfaced by extending `ConsensusResult.unique_findings`.

**Tech Stack:** Python 3.10+, dataclasses, json, existing models.py, existing cli.py

---

### Task 1: Structured Output Formats

**Files:**

- Create: `ai_delegate/output_formatter.py`
- Modify: `ai_delegate/cli.py` (add `--format` flag)
- Create: `tests/test_output_formatter.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_output_formatter.py
import pytest
from ai_delegate.output_formatter import OutputFormatter
from ai_delegate.models import Verdict, Finding


def make_verdict(findings=None, recommendations=None):
    return Verdict(
        task_type="audit",
        consensus_score=0.75,
        tier_used="standard",
        findings=findings or [
            Finding(severity="high", issue="SQL injection in login", location="auth.py:42",
                    recommendation="Use parameterized queries"),
            Finding(severity="medium", issue="Missing rate limiting", location="api.py:15",
                    recommendation="Add rate limiting middleware"),
        ],
        recommendations=recommendations or ["Apply parameterized queries", "Add rate limiting"],
        action_items=["Fix SQL injection immediately"],
    )


class TestOutputFormatter:
    def test_adr_format_contains_context(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="adr")
        assert "# Architecture Decision Record" in output
        assert "## Context" in output
        assert "## Decision" in output
        assert "## Consequences" in output

    def test_adr_format_includes_findings(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="adr")
        assert "SQL injection" in output

    def test_risk_matrix_format(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="risk-matrix")
        assert "| Severity |" in output
        assert "high" in output.lower()
        assert "medium" in output.lower()

    def test_risk_matrix_sorts_by_severity(self):
        formatter = OutputFormatter()
        verdict = make_verdict(findings=[
            Finding(severity="low", issue="Minor issue", recommendation="Fix later"),
            Finding(severity="critical", issue="Critical bug", recommendation="Fix now"),
            Finding(severity="medium", issue="Medium issue", recommendation="Fix soon"),
        ])
        output = formatter.format(verdict, fmt="risk-matrix")
        critical_pos = output.index("critical")
        low_pos = output.index("low")
        assert critical_pos < low_pos

    def test_playbook_format(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="playbook")
        assert "## Playbook" in output
        assert "### Step" in output
        assert "Action:" in output

    def test_playbook_contains_action_items(self):
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="playbook")
        assert "Fix SQL injection immediately" in output

    def test_perf_profile_format(self):
        formatter = OutputFormatter()
        verdict = Verdict(
            task_type="analyze",
            consensus_score=0.85,
            tier_used="standard",
            findings=[
                Finding(severity="high", issue="N+1 query in user list", location="users.py:30",
                        impact="10x slower under load"),
            ],
            recommendations=["Add eager loading"],
            action_items=["Fix N+1 query"],
        )
        output = formatter.format(verdict, fmt="perf-profile")
        assert "## Performance Profile" in output
        assert "N+1" in output

    def test_unknown_format_raises(self):
        formatter = OutputFormatter()
        with pytest.raises(ValueError, match="Unknown format"):
            formatter.format(make_verdict(), fmt="unknown-format")

    def test_default_json_format(self):
        import json
        formatter = OutputFormatter()
        output = formatter.format(make_verdict(), fmt="json")
        data = json.loads(output)
        assert data["task_type"] == "audit"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd /Users/kobig/Codes/Personals/ai-delegate-plugin
pytest tests/test_output_formatter.py -v 2>&1 | head -30
```

Expected: ImportError or ModuleNotFoundError for `ai_delegate.output_formatter`

- [ ] **Step 3: Create OutputFormatter**

```python
# ai_delegate/output_formatter.py
"""
Structured output formatters for ai-delegate verdicts.
"""
import json
from typing import Optional
from .models import Verdict, Finding

_SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def _severity_rank(f: Finding) -> int:
    return _SEVERITY_ORDER.get(f.severity.lower(), 5)


class OutputFormatter:
    """Formats Verdict into various structured output formats."""

    def format(self, verdict: Verdict, fmt: str = "json") -> str:
        if fmt == "json":
            return json.dumps(verdict.to_dict(), indent=2)
        elif fmt == "adr":
            return self._format_adr(verdict)
        elif fmt == "risk-matrix":
            return self._format_risk_matrix(verdict)
        elif fmt == "playbook":
            return self._format_playbook(verdict)
        elif fmt == "perf-profile":
            return self._format_perf_profile(verdict)
        else:
            raise ValueError(f"Unknown format: {fmt}. Valid: json, adr, risk-matrix, playbook, perf-profile")

    def _format_adr(self, verdict: Verdict) -> str:
        lines = [
            "# Architecture Decision Record",
            f"\n**Task:** {verdict.task_type.upper()}",
            f"**Consensus:** {verdict.consensus_score:.0%}",
            f"**Tier:** {verdict.tier_used}",
            "\n## Context",
            f"Analysis identified {len(verdict.findings)} findings across {verdict.task_type} review.",
            "\n## Decision",
        ]
        for r in verdict.recommendations:
            lines.append(f"- {r}")
        lines.append("\n## Consequences")
        sorted_findings = sorted(verdict.findings, key=_severity_rank)
        for f in sorted_findings:
            loc = f" ({f.location})" if f.location else ""
            lines.append(f"- **[{f.severity.upper()}]** {f.issue}{loc}")
        lines.append("\n## Action Items")
        for item in verdict.action_items:
            lines.append(f"- [ ] {item}")
        return "\n".join(lines)

    def _format_risk_matrix(self, verdict: Verdict) -> str:
        sorted_findings = sorted(verdict.findings, key=_severity_rank)
        lines = [
            "# Risk Matrix",
            f"\n**Task:** {verdict.task_type.upper()} | **Consensus:** {verdict.consensus_score:.0%}",
            "\n| Severity | Issue | Location | Recommendation |",
            "|----------|-------|----------|----------------|",
        ]
        for f in sorted_findings:
            loc = f.location or "—"
            rec = f.recommendation or "—"
            lines.append(f"| {f.severity} | {f.issue} | {loc} | {rec} |")
        return "\n".join(lines)

    def _format_playbook(self, verdict: Verdict) -> str:
        lines = [
            "## Playbook",
            f"\n**Task:** {verdict.task_type.upper()} | **Tier:** {verdict.tier_used}",
            "\n### Immediate Actions",
        ]
        for i, item in enumerate(verdict.action_items, 1):
            lines.append(f"\n### Step {i}")
            lines.append(f"**Action:** {item}")
        critical = [f for f in verdict.findings if f.severity.lower() in ("critical", "high")]
        if critical:
            lines.append("\n### Critical Findings to Address")
            for f in critical:
                loc = f" at `{f.location}`" if f.location else ""
                lines.append(f"\n**{f.issue}**{loc}")
                if f.recommendation:
                    lines.append(f"- Recommendation: {f.recommendation}")
        return "\n".join(lines)

    def _format_perf_profile(self, verdict: Verdict) -> str:
        lines = [
            "## Performance Profile",
            f"\n**Task:** {verdict.task_type.upper()} | **Consensus:** {verdict.consensus_score:.0%}",
            "\n### Findings",
        ]
        sorted_findings = sorted(verdict.findings, key=_severity_rank)
        for f in sorted_findings:
            loc = f" (`{f.location}`)" if f.location else ""
            impact = f"\n  - Impact: {f.impact}" if f.impact else ""
            rec = f"\n  - Fix: {f.recommendation}" if f.recommendation else ""
            lines.append(f"\n**[{f.severity.upper()}]** {f.issue}{loc}{impact}{rec}")
        lines.append("\n### Recommendations")
        for r in verdict.recommendations:
            lines.append(f"- {r}")
        return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_output_formatter.py -v
```

Expected: All 9 tests PASS

- [ ] **Step 5: Add `--format` flag to CLI**

In `ai_delegate/cli.py`, find:

```python
    parser.add_argument(
        "--output", "-o",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
```

Replace with:

```python
    parser.add_argument(
        "--output", "-o",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "adr", "risk-matrix", "playbook", "perf-profile"],
        default=None,
        help="Structured output format (overrides --output json)",
    )
```

In `main()`, after `result = run_analysis(...)`:

Find:

```python
        if args.output == "json":
            print(json.dumps(result, indent=2))
```

Replace with:

```python
        if args.format:
            from .output_formatter import OutputFormatter
            from .models import Verdict, Finding
            # Reconstruct Verdict from dict for formatter
            verdict_obj = Verdict(
                task_type=result["task_type"],
                consensus_score=result["consensus_score"],
                tier_used=result["tier_used"],
                findings=[Finding.from_dict(f) for f in result.get("findings", [])],
                recommendations=result.get("recommendations", []),
                action_items=result.get("action_items", []),
            )
            print(OutputFormatter().format(verdict_obj, fmt=args.format))
        elif args.output == "json":
            print(json.dumps(result, indent=2))
```

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/output_formatter.py tests/test_output_formatter.py ai_delegate/cli.py
git commit -m "feat: add structured output formats (adr, risk-matrix, playbook, perf-profile)"
```

---

### Task 2: Workflow Modes

**Files:**

- Create: `ai_delegate/flow_config.py`
- Modify: `ai_delegate/cli.py` (add `--flow` flag)
- Modify: `ai_delegate/debate/orchestrator.py` (accept `FlowConfig`)
- Create: `tests/test_flow_config.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_flow_config.py
import pytest
from ai_delegate.flow_config import FlowConfig, FlowMode


class TestFlowConfig:
    def test_quick_mode(self):
        config = FlowConfig.from_mode("quick")
        assert config.mode == FlowMode.QUICK
        assert config.max_experts == 2
        assert config.force_tier == "fast"
        assert config.elicitation_enabled is False
        assert config.party_mode_enabled is False

    def test_bmad_mode(self):
        config = FlowConfig.from_mode("bmad")
        assert config.mode == FlowMode.BMAD
        assert config.max_experts is None  # use all
        assert config.force_tier is None   # auto-select
        assert config.elicitation_enabled is True
        assert config.party_mode_enabled is True

    def test_enterprise_mode(self):
        config = FlowConfig.from_mode("enterprise")
        assert config.mode == FlowMode.ENTERPRISE
        assert config.elicitation_enabled is True
        assert config.party_mode_enabled is True
        assert config.force_tier == "deep"

    def test_default_mode(self):
        config = FlowConfig.default()
        assert config.mode == FlowMode.STANDARD
        assert config.elicitation_enabled is False
        assert config.party_mode_enabled is False
        assert config.force_tier is None

    def test_unknown_mode_raises(self):
        with pytest.raises(ValueError, match="Unknown flow mode"):
            FlowConfig.from_mode("turbo")

    def test_quick_mode_limits_experts(self):
        config = FlowConfig.from_mode("quick")
        experts = {"owasp": "p1", "auth": "p2", "input": "p3"}
        limited = config.limit_experts(experts)
        assert len(limited) == 2

    def test_non_quick_mode_keeps_all_experts(self):
        config = FlowConfig.from_mode("bmad")
        experts = {"owasp": "p1", "auth": "p2", "input": "p3"}
        limited = config.limit_experts(experts)
        assert len(limited) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_flow_config.py -v 2>&1 | head -20
```

Expected: ImportError for `ai_delegate.flow_config`

- [ ] **Step 3: Create FlowConfig**

```python
# ai_delegate/flow_config.py
"""
Workflow mode configuration for ai-delegate.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional


class FlowMode(str, Enum):
    QUICK = "quick"
    STANDARD = "standard"
    BMAD = "bmad"
    ENTERPRISE = "enterprise"


@dataclass
class FlowConfig:
    mode: FlowMode
    max_experts: Optional[int] = None
    force_tier: Optional[str] = None
    elicitation_enabled: bool = False
    party_mode_enabled: bool = False
    checkpoint_enabled: bool = False

    @classmethod
    def default(cls) -> "FlowConfig":
        return cls(mode=FlowMode.STANDARD)

    @classmethod
    def from_mode(cls, mode: str) -> "FlowConfig":
        if mode == "quick":
            return cls(
                mode=FlowMode.QUICK,
                max_experts=2,
                force_tier="fast",
                elicitation_enabled=False,
                party_mode_enabled=False,
                checkpoint_enabled=False,
            )
        elif mode == "standard":
            return cls.default()
        elif mode == "bmad":
            return cls(
                mode=FlowMode.BMAD,
                max_experts=None,
                force_tier=None,
                elicitation_enabled=True,
                party_mode_enabled=True,
                checkpoint_enabled=True,
            )
        elif mode == "enterprise":
            return cls(
                mode=FlowMode.ENTERPRISE,
                max_experts=None,
                force_tier="deep",
                elicitation_enabled=True,
                party_mode_enabled=True,
                checkpoint_enabled=True,
            )
        else:
            raise ValueError(f"Unknown flow mode: {mode}. Valid: quick, standard, bmad, enterprise")

    def limit_experts(self, experts: Dict[str, str]) -> Dict[str, str]:
        """Limit expert count based on flow config."""
        if self.max_experts is None:
            return experts
        items = list(experts.items())[: self.max_experts]
        return dict(items)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_flow_config.py -v
```

Expected: All 7 tests PASS

- [ ] **Step 5: Add `--flow` flag to CLI**

In `ai_delegate/cli.py`, after the `--format` argument block, add:

```python
    parser.add_argument(
        "--flow",
        choices=["quick", "standard", "bmad", "enterprise"],
        default="standard",
        help="Workflow mode: quick (2 experts, fast tier), standard (default), bmad (elicitation+party), enterprise (deep+bmad)",
    )
```

In `run_analysis()`, add `flow` parameter and pass to orchestrator:

```python
def run_analysis(
    content: str,
    task_type: str,
    tier: str = Tier.AUTO.value,
    model: Optional[str] = None,
    verbose: bool = False,
    flow: str = "standard",
) -> dict:
    from .flow_config import FlowConfig
    flow_config = FlowConfig.from_mode(flow)

    config = create_task_config(task_type)
    if model:
        config.default_model = model

    # Apply flow expert limits
    if flow_config.max_experts is not None:
        config.experts = flow_config.limit_experts(config.experts)

    # Force tier from flow config
    effective_tier = flow_config.force_tier or tier

    client = OllamaClient(model=config.default_model, verbose=verbose)
    orchestrator = DebateOrchestrator(client=client, task_config=config, verbose=verbose)
    verdict = orchestrator.analyze(content, tier=effective_tier)
    return verdict.to_dict()
```

In `main()`, pass `flow=args.flow` to `run_analysis()`.

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/flow_config.py tests/test_flow_config.py ai_delegate/cli.py
git commit -m "feat: add workflow modes (quick, standard, bmad, enterprise)"
```

---

### Task 3: Consensus Disagreement Detail

**Files:**

- Modify: `ai_delegate/debate/orchestrator.py` (`ConsensusResult`, `ConsensusCalculator`)
- Modify: `ai_delegate/models.py` (`ConsensusResult`, `Verdict`)
- Create: `tests/test_consensus_detail.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_consensus_detail.py
import pytest
from ai_delegate.models import Finding, ExpertResult, ConsensusResult
from ai_delegate.debate.orchestrator import ConsensusCalculator


def make_expert_result(name: str, findings: list) -> ExpertResult:
    return ExpertResult(expert_name=name, expert_type="security", findings=findings)


class TestConsensusDetail:
    def test_disagreement_detail_populated(self):
        """Unique findings include which expert raised them."""
        f1 = Finding(severity="high", issue="SQL injection in login")
        f2 = Finding(severity="medium", issue="Missing CSRF protection")
        f3 = Finding(severity="low", issue="Verbose error messages")

        results = [
            make_expert_result("OWASP Expert", [f1, f2]),
            make_expert_result("Auth Expert", [f1, f3]),
            make_expert_result("Input Expert", [f1]),
        ]

        calc = ConsensusCalculator()
        consensus = calc.calculate(results)

        # f1 raised by all 3 = consensus
        assert len(consensus.consensus_findings) == 1
        # f2 raised by 1 only = unique
        assert "OWASP Expert" in consensus.unique_findings
        assert any(f.issue == "Missing CSRF protection" for f in consensus.unique_findings["OWASP Expert"])

    def test_disagreement_reason_in_verdict(self):
        """ConsensusResult.disagreement_summary describes what was disputed."""
        f1 = Finding(severity="high", issue="SQL injection in login")
        f2 = Finding(severity="medium", issue="Missing CSRF protection")

        results = [
            make_expert_result("Expert A", [f1, f2]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]

        calc = ConsensusCalculator()
        consensus = calc.calculate(results)
        summary = consensus.disagreement_summary

        assert "Expert A" in summary
        assert "Missing CSRF protection" in summary

    def test_full_consensus_has_empty_disagreement(self):
        f1 = Finding(severity="high", issue="SQL injection")
        results = [
            make_expert_result("Expert A", [f1]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]
        calc = ConsensusCalculator()
        consensus = calc.calculate(results)
        assert consensus.disagreement_summary == ""

    def test_consensus_result_to_dict_includes_disagreement(self):
        f1 = Finding(severity="high", issue="SQL injection")
        f2 = Finding(severity="low", issue="Minor issue")
        results = [
            make_expert_result("Expert A", [f1, f2]),
            make_expert_result("Expert B", [f1]),
            make_expert_result("Expert C", [f1]),
        ]
        calc = ConsensusCalculator()
        consensus = calc.calculate(results)
        d = consensus.to_dict()
        assert "disagreement_summary" in d
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_consensus_detail.py -v 2>&1 | head -30
```

Expected: AttributeError on `consensus.disagreement_summary`

- [ ] **Step 3: Add `disagreement_summary` to ConsensusResult**

In `ai_delegate/models.py`, find the `ConsensusResult` dataclass:

```python
@dataclass
class ConsensusResult:
    """Result of consensus calculation between experts."""
    score: float  # 0.0 to 1.0
    consensus_findings: List[Finding] = field(default_factory=list)
    disputed_findings: List[Finding] = field(default_factory=list)
    unique_findings: Dict[str, List[Finding]] = field(default_factory=dict)
```

Replace with:

```python
@dataclass
class ConsensusResult:
    """Result of consensus calculation between experts."""
    score: float  # 0.0 to 1.0
    consensus_findings: List[Finding] = field(default_factory=list)
    disputed_findings: List[Finding] = field(default_factory=list)
    unique_findings: Dict[str, List[Finding]] = field(default_factory=dict)
    disagreement_summary: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "percentage": self.percentage,
            "tier": self.tier,
            "consensus_findings": [f.to_dict() for f in self.consensus_findings],
            "disputed_findings": [f.to_dict() for f in self.disputed_findings],
            "unique_findings": {
                k: [f.to_dict() for f in v]
                for k, v in self.unique_findings.items()
            },
            "disagreement_summary": self.disagreement_summary,
        }
```

- [ ] **Step 4: Build disagreement_summary in ConsensusCalculator**

In `ai_delegate/debate/orchestrator.py`, find the `ConsensusCalculator.calculate()` method. After building `unique_findings`, add:

```python
        # Build disagreement summary
        disagreement_parts = []
        for expert_name, findings in unique_findings.items():
            issues = [f.issue for f in findings[:3]]  # max 3 per expert
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
```

Remove the existing `return ConsensusResult(...)` that doesn't include `disagreement_summary`.

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_consensus_detail.py -v
```

Expected: All 4 tests PASS

- [ ] **Step 6: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/models.py ai_delegate/debate/orchestrator.py tests/test_consensus_detail.py
git commit -m "feat: add consensus disagreement detail (which experts raised unique findings)"
```

---

### Task 4: Bump to v0.2.0

**Files:**

- Modify: `ai_delegate/__init__.py`
- Modify: `ai_delegate/cli.py`
- Modify: `README.md`

- [ ] **Step 1: Update version strings**

In `ai_delegate/__init__.py`:

```python
__version__ = "0.2.0"
```

In `ai_delegate/cli.py`, find `version="%(prog)s 0.0.2"` → `version="%(prog)s 0.2.0"`

In `README.md`, find `version-0.0.2-blue` → `version-0.2.0-blue`

In README CLI examples section, update to reflect new flags:

```bash
# Quick security audit (fast mode)
ai-delegate audit --file src/auth.py --flow quick

# Full BMAD analysis with structured output
ai-delegate audit --file src/auth.py --flow bmad --format risk-matrix

# Architecture review as ADR
ai-delegate architecture --file ./src/ --format adr

# Enterprise deep review
ai-delegate review --file src/ --flow enterprise --format playbook
```

- [ ] **Step 2: Update test for version**

In `tests/test_cli.py`, find `assert "0.0.2" in captured.out` (both occurrences) → `assert "0.2.0" in captured.out`

- [ ] **Step 3: Run version tests**

```bash
pytest tests/test_cli.py::TestCLIVersion -v
```

Expected: Both tests PASS

- [ ] **Step 4: Run full test suite**

```bash
pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add ai_delegate/__init__.py ai_delegate/cli.py README.md tests/test_cli.py
git commit -m "feat: bump version to 0.2.0 with structured outputs and workflow modes"
```
