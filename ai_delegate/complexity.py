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
    level: str                                        # "low" | "medium" | "high"
    domains: list[str] = field(default_factory=list)  # detected domain keywords
    file_count: int = 1
    line_count: int = 0
    security_signals: int = 0                         # count of security-relevant term occurrences


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
