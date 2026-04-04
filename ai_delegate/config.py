"""
Configuration for AI Delegation Framework.

Contains task configurations, expert definitions, and default settings.
"""

from typing import Dict, List

from .constants import (
    Models,
    TaskTypes,
    ExpertDomains,
    DEFAULT_MODELS,
)


# =============================================================================
# Task Display Names
# =============================================================================

TASK_DISPLAY_NAMES: Dict[str, str] = {
    TaskTypes.AUDIT: "SECURITY AUDIT",
    TaskTypes.ANALYZE: "PERFORMANCE ANALYSIS",
    TaskTypes.ARCHITECTURE: "ARCHITECTURE REVIEW",
    TaskTypes.REFACTOR: "REFACTORING ANALYSIS",
    TaskTypes.MIGRATE: "MIGRATION ANALYSIS",
    TaskTypes.REVIEW: "CODE REVIEW",
}

# =============================================================================
# Task Expert Descriptions
# =============================================================================

TASK_EXPERT_DESCRIPTIONS: Dict[str, str] = {
    TaskTypes.AUDIT: "OWASP Top 10, Authentication/Crypto, Input/Secrets",
    TaskTypes.ANALYZE: "Algorithm Complexity, Database/Query, Memory/Caching",
    TaskTypes.ARCHITECTURE: "Design Patterns, SOLID Principles, Scalability/Coupling",
    TaskTypes.REFACTOR: "Simplification, Patterns, Performance",
    TaskTypes.MIGRATE: "API Compatibility, Dependencies, Testing",
    TaskTypes.REVIEW: "Multi-domain review experts",
}

# =============================================================================
# Task Adjudicator Roles
# =============================================================================

TASK_ADJUDICATOR_ROLES: Dict[str, str] = {
    TaskTypes.AUDIT: """Security Adjudicator synthesizing findings from security experts.

Your role:
1. Consolidate all vulnerabilities found
2. Remove duplicates and merge related issues
3. Prioritize by severity and exploitability
4. Provide remediation roadmap""",

    TaskTypes.ANALYZE: """Performance Adjudicator synthesizing findings from performance experts.

Your role:
1. Consolidate all performance issues
2. Identify performance trade-offs
3. Prioritize optimizations by impact
4. Provide optimization roadmap""",

    TaskTypes.ARCHITECTURE: """Architecture Adjudicator synthesizing findings from architecture experts.

Your role:
1. Consolidate all architecture issues
2. Identify patterns and anti-patterns
3. Prioritize by maintainability impact
4. Provide architecture improvement roadmap""",

    TaskTypes.REFACTOR: """Refactoring Adjudicator synthesizing findings from refactoring experts.

Your role:
1. Consolidate all refactoring opportunities
2. Identify simplification opportunities
3. Prioritize by complexity reduction
4. Provide refactoring roadmap""",

    TaskTypes.MIGRATE: """Migration Adjudicator synthesizing findings from migration experts.

Your role:
1. Consolidate all migration risks
2. Identify breaking changes
3. Prioritize by migration impact
4. Provide migration roadmap""",

    TaskTypes.REVIEW: """Review Adjudicator synthesizing findings from all expert domains.

Your role:
1. Consolidate findings from all domains
2. Identify cross-cutting concerns
3. Prioritize by overall impact
4. Provide comprehensive action plan""",
}

# =============================================================================
# Task Output Formats
# =============================================================================

TASK_OUTPUT_FORMATS: Dict[str, str] = {
    TaskTypes.AUDIT: """- critical_vulnerabilities: array of critical issues
- high_vulnerabilities: array of high severity issues
- medium_vulnerabilities: array of medium severity issues
- low_vulnerabilities: array of low severity issues
- overall_security_score: 0-100""",

    TaskTypes.ANALYZE: """- high_impact: array of high impact performance issues
- medium_impact: array of medium impact issues
- low_impact: array of low impact issues
- performance_score: 0-100""",

    TaskTypes.ARCHITECTURE: """- architecture_violations: array of SOLID/pattern violations
- coupling_issues: array of coupling problems
- scalability_concerns: array of scalability issues
- architecture_score: 0-100""",

    TaskTypes.REFACTOR: """- simplification_opportunities: array of simplification ideas
- pattern_applications: array of pattern improvements
- complexity_reduction: estimated complexity reduction
- refactoring_score: 0-100""",

    TaskTypes.MIGRATE: """- breaking_changes: array of breaking changes
- api_changes: array of API differences
- dependency_changes: array of dependency impacts
- testing_requirements: array of testing needs
- migration_roadmap: phased migration plan
- migration_risk: overall migration risk assessment""",

    TaskTypes.REVIEW: """- consensus_points: array of issues all experts agree on
- conflicts: array of disagreements between experts
- final_verdict: prioritized list of recommendations
- action_items: specific next steps ordered by priority""",
}

# =============================================================================
# Expert Configurations
# =============================================================================

EXPERT_CONFIGS: Dict[str, Dict[str, str]] = {
    ExpertDomains.SECURITY: {
        ExpertDomains.OWASP: "You are an OWASP Top 10 Expert specializing in injection, XSS, CSRF, broken authentication, security misconfiguration. Identify vulnerabilities with CVE references and severity ratings.",
        ExpertDomains.AUTH: "You are an Authentication & Crypto Expert specializing in JWT, OAuth, session management, password hashing, encryption implementation. Identify auth vulnerabilities and crypto issues.",
        ExpertDomains.INPUT: "You are an Input Validation & Secrets Expert specializing in input sanitization, hardcoded secrets detection, API key exposure, sensitive data leakage. Identify validation gaps and secret exposures.",
    },
    ExpertDomains.PERFORMANCE: {
        ExpertDomains.COMPLEXITY: "You are an Algorithm Complexity Expert specializing in Big O analysis, nested loops, recursion, time complexity. Identify performance bottlenecks with complexity analysis.",
        ExpertDomains.DATABASE: "You are a Database & Query Expert specializing in N+1 queries, missing indexes, query optimization, connection pooling. Identify database performance issues.",
        ExpertDomains.MEMORY: "You are a Memory & Caching Expert specializing in memory leaks, large allocations, caching opportunities, GC pressure. Identify memory issues and caching opportunities.",
    },
    ExpertDomains.ARCHITECTURE: {
        ExpertDomains.PATTERNS: "You are a Design Patterns Expert specializing in pattern applicability, anti-patterns, Gang of Four patterns, modern patterns. Identify pattern opportunities and anti-patterns.",
        ExpertDomains.SOLID: "You are a SOLID Principles Expert specializing in Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Identify SOLID violations.",
        ExpertDomains.SCALABILITY: "You are a Scalability & Coupling Expert specializing in coupling analysis, cohesion metrics, distributed systems, microservices. Identify scalability bottlenecks.",
    },
    ExpertDomains.REFACTOR: {
        "simplification": "You are a Code Simplification Expert specializing in reducing complexity, eliminating redundancy, improving readability. Identify simplification opportunities.",
        "patterns": "You are a Refactoring Patterns Expert specializing in Extract Method, Replace Conditional with Polymorphism, Strategy Pattern. Identify refactoring opportunities.",
    },
    ExpertDomains.MIGRATE: {
        "api": "You are an API Migration Expert specializing in API versioning, breaking changes, backward compatibility. Identify migration risks.",
        "dependencies": "You are a Dependency Migration Expert specializing in package migrations, version conflicts, deprecation handling. Identify dependency risks.",
    },
}

# =============================================================================
# Re-export DEFAULT_MODELS from constants
# =============================================================================

# Note: DEFAULT_MODELS is now defined in constants.py
# This is kept for backward compatibility