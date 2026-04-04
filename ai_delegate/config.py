"""
Configuration for Ollama Delegation Framework.

Contains task configurations, expert definitions, and default settings.
"""

from typing import Dict, List

# =============================================================================
# Task Display Names
# =============================================================================

TASK_DISPLAY_NAMES: Dict[str, str] = {
    "audit": "SECURITY AUDIT",
    "analyze": "PERFORMANCE ANALYSIS",
    "architecture": "ARCHITECTURE REVIEW",
    "refactor": "REFACTORING ANALYSIS",
    "migrate": "MIGRATION ANALYSIS",
    "review": "CODE REVIEW",
}

# =============================================================================
# Task Expert Descriptions
# =============================================================================

TASK_EXPERT_DESCRIPTIONS: Dict[str, str] = {
    "audit": "OWASP Top 10, Authentication/Crypto, Input/Secrets",
    "analyze": "Algorithm Complexity, Database/Query, Memory/Caching",
    "architecture": "Design Patterns, SOLID Principles, Scalability/Coupling",
    "refactor": "Simplification, Patterns, Performance",
    "migrate": "API Compatibility, Dependencies, Testing",
    "review": "Multi-domain review experts",
}

# =============================================================================
# Task Adjudicator Roles
# =============================================================================

TASK_ADJUDICATOR_ROLES: Dict[str, str] = {
    "audit": """Security Adjudicator synthesizing findings from security experts.

Your role:
1. Consolidate all vulnerabilities found
2. Remove duplicates and merge related issues
3. Prioritize by severity and exploitability
4. Provide remediation roadmap""",

    "analyze": """Performance Adjudicator synthesizing findings from performance experts.

Your role:
1. Consolidate all performance issues
2. Identify performance trade-offs
3. Prioritize optimizations by impact
4. Provide optimization roadmap""",

    "architecture": """Architecture Adjudicator synthesizing findings from architecture experts.

Your role:
1. Consolidate all architecture issues
2. Identify patterns and anti-patterns
3. Prioritize by impact on maintainability
4. Provide improvement roadmap""",

    "refactor": """Refactoring Adjudicator synthesizing findings from refactoring experts.

Your role:
1. Consolidate all refactoring opportunities
2. Identify quick wins vs large refactorings
3. Prioritize by impact and effort
4. Provide refactoring roadmap""",

    "migrate": """Migration Adjudicator synthesizing findings from migration experts.

Your role:
1. Consolidate all migration issues
2. Identify breaking changes and risks
3. Prioritize migration phases
4. Provide migration roadmap""",

    "review": """Code Review Adjudicator synthesizing findings from domain experts.

Your role:
1. Consolidate all findings across domains
2. Identify consensus points
3. Resolve conflicting views
4. Provide prioritized recommendations""",
}

# =============================================================================
# Task Output Formats
# =============================================================================

TASK_OUTPUT_FORMATS: Dict[str, str] = {
    "audit": """- critical_vulnerabilities: array of critical issues
- high_vulnerabilities: array of high severity issues
- medium_vulnerabilities: array of medium severity issues
- low_vulnerabilities: array of low severity issues
- remediation_roadmap: prioritized fix plan
- security_score: overall security score 0-100""",

    "analyze": """- high_impact: array of high impact optimizations
- medium_impact: array of medium impact optimizations
- low_impact: array of low impact optimizations
- trade_offs: performance trade-offs to consider
- optimization_roadmap: prioritized optimization plan""",

    "architecture": """- critical_issues: array of critical architecture issues
- high_issues: array of high severity issues
- medium_issues: array of medium severity issues
- low_issues: array of low severity issues
- improvement_roadmap: prioritized improvement plan
- architecture_score: overall architecture score 0-100""",

    "refactor": """- high_priority: array of high priority refactorings
- medium_priority: array of medium priority refactorings
- low_priority: array of low priority refactorings
- quick_wins: easy improvements with high impact
- refactoring_roadmap: prioritized refactoring plan""",

    "migrate": """- breaking_changes: array of breaking changes
- api_changes: array of API differences
- dependency_changes: array of dependency impacts
- testing_requirements: array of testing needs
- migration_roadmap: phased migration plan
- migration_risk: overall migration risk assessment""",

    "review": """- consensus_points: array of issues all experts agree on
- conflicts: array of disagreements between experts
- final_verdict: prioritized list of recommendations
- action_items: specific next steps ordered by priority""",
}

# =============================================================================
# Default Models by Task
# =============================================================================

DEFAULT_MODELS: Dict[str, str] = {
    "review": "kimi-k2.5:cloud",
    "docs": "glm-5:cloud",
    "test": "glm-5:cloud",
    "explain": "kimi-k2.5:cloud",
    "audit": "glm-5:cloud",
    "analyze": "glm-5:cloud",
    "architecture": "kimi-k2.5:cloud",
    "refactor": "kimi-k2.5:cloud",
    "migrate": "kimi-k2.5:cloud",
}

# =============================================================================
# Expert Configurations
# =============================================================================

EXPERT_CONFIGS: Dict[str, Dict[str, str]] = {
    "security": {
        "owasp": "You are an OWASP Top 10 Expert specializing in injection, XSS, CSRF, broken authentication, security misconfiguration. Identify vulnerabilities with CVE references and severity ratings.",
        "auth": "You are an Authentication & Crypto Expert specializing in JWT, OAuth, session management, password hashing, encryption implementation. Identify auth vulnerabilities and crypto issues.",
        "input": "You are an Input Validation & Secrets Expert specializing in input sanitization, hardcoded secrets detection, API key exposure, sensitive data leakage. Identify validation gaps and secret exposures.",
    },
    "performance": {
        "complexity": "You are an Algorithm Complexity Expert specializing in Big O analysis, nested loops, recursion, time complexity. Identify performance bottlenecks with complexity analysis.",
        "database": "You are a Database & Query Expert specializing in N+1 queries, missing indexes, query optimization, connection pooling. Identify database performance issues.",
        "memory": "You are a Memory & Caching Expert specializing in memory leaks, large allocations, caching opportunities, GC pressure. Identify memory issues and caching opportunities.",
    },
    "architecture": {
        "patterns": "You are a Design Patterns Expert specializing in pattern applicability, anti-patterns, Gang of Four patterns, modern patterns. Identify pattern opportunities and anti-patterns.",
        "solid": "You are a SOLID Principles Expert specializing in Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, Dependency Inversion. Identify SOLID violations.",
        "scalability": "You are a Scalability & Coupling Expert specializing in coupling analysis, cohesion metrics, distributed systems, microservices. Identify scalability bottlenecks.",
    },
    "refactor": {
        "simplification": "You are a Code Simplification Expert specializing in extract method, remove duplication, simplify conditionals, reduce complexity. Identify simplification opportunities.",
        "patterns": "You are a Pattern Introduction Expert specializing in introducing design patterns, improving maintainability, reducing coupling. Identify pattern introduction opportunities.",
        "performance": "You are a Performance Refactoring Expert specializing in performance-focused refactors, memory optimizations, algorithm improvements. Identify performance refactoring opportunities.",
    },
    "migrate": {
        "api": "You are an API Compatibility Expert specializing in breaking changes, API differences, request/response mapping. Identify API compatibility issues.",
        "dependencies": "You are a Dependency Impact Expert specializing in package changes, transitive dependencies, version conflicts. Identify dependency issues.",
        "testing": "You are a Migration Testing Expert specializing in test migration, regression risks, test coverage gaps. Identify testing requirements for migration.",
    },
}

# =============================================================================
# Tier Constants
# =============================================================================

TIER_FAST = "fast"
TIER_STANDARD = "standard"
TIER_DEEP = "deep"
TIER_AUTO = "auto"

CONSENSUS_THRESHOLD_FAST = 0.90
CONSENSUS_THRESHOLD_STANDARD = 0.70

# =============================================================================
# Rate Limiting
# =============================================================================

MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 2  # seconds, doubles each retry