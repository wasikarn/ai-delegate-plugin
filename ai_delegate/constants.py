"""
Centralized configuration for AI Delegation Framework.

All hardcoded values are centralized here for easy configuration.
"""

from typing import Dict, List, TypedDict
from enum import Enum


# =============================================================================
# Model Names
# =============================================================================

class Models:
    """Model name constants."""

    # Claude models
    CLAUDE_HAIKU = "haiku"
    CLAUDE_SONNET = "sonnet"
    CLAUDE_OPUS = "opus"

    # Ollama models (cloud)
    GLM_5_CLOUD = "glm-5:cloud"
    KIMI_K25_CLOUD = "kimi-k2.5:cloud"
    GEMMA4_31B_CLOUD = "gemma4:31b-cloud"


# =============================================================================
# Model Specifications
# =============================================================================

class ModelSpec(TypedDict):
    """Model specification with context window, modalities, and benchmarks."""
    parameters: str           # e.g., "30.7B dense", "744B (40B active MoE)"
    context_window: int       # Maximum context length in tokens
    modalities: List[str]     # ["text"], ["text", "image"], etc.
    benchmarks: Dict[str, float]  # Key benchmark scores
    features: List[str]       # e.g., ["tools", "thinking", "vision"]
    provider: str             # "ollama" or "anthropic"


# Model specifications from official Ollama library and Anthropic docs (April 2026)
# Sources: ollama.com/library/glm-5:cloud, ollama.com/library/kimi-k2.5:cloud,
#          ollama.com/library/gemma4:31b-cloud, platform.claude.com/docs/pricing
MODEL_INFO: Dict[str, ModelSpec] = {
    # Ollama Cloud models
    Models.GLM_5_CLOUD: {
        "parameters": "744B (40B active MoE)",
        "context_window": 198_000,
        "modalities": ["text"],
        "benchmarks": {
            "aime_2026": 92.7,
            "gpqa_diamond": 86.0,
            "swe_bench": 77.8,
        },
        "features": ["tools", "thinking"],
        "provider": "ollama",
    },
    Models.KIMI_K25_CLOUD: {
        "parameters": "15T visual+text tokens",
        "context_window": 256_000,
        "modalities": ["text", "image"],
        "benchmarks": {},  # Not published
        "features": ["vision", "tools", "thinking", "agent_swarm"],
        "provider": "ollama",
    },
    Models.GEMMA4_31B_CLOUD: {
        "parameters": "30.7B dense",
        "context_window": 256_000,
        "modalities": ["text", "image"],
        "benchmarks": {
            "aime_2026": 89.2,
            "livecodebench": 80.0,
            "mmlu_pro": 85.2,
            "gpqa_diamond": 84.3,
        },
        "features": ["vision", "tools", "thinking"],
        "provider": "ollama",
    },
    # Claude models (Anthropic)
    Models.CLAUDE_HAIKU: {
        "parameters": "~3B",
        "context_window": 200_000,
        "modalities": ["text", "image"],
        "benchmarks": {
            # Haiku focuses on speed, not published benchmarks
        },
        "features": ["vision", "tools", "fast"],
        "provider": "anthropic",
    },
    Models.CLAUDE_SONNET: {
        "parameters": "~70B",
        "context_window": 200_000,  # 1M available
        "modalities": ["text", "image"],
        "benchmarks": {
            "swe_bench": 79.6,
            "terminal_bench": 59.1,
        },
        "features": ["vision", "tools", "extended_thinking", "adaptive"],
        "provider": "anthropic",
    },
    Models.CLAUDE_OPUS: {
        "parameters": "~400B",
        "context_window": 200_000,  # 1M available
        "modalities": ["text", "image"],
        "benchmarks": {
            "swe_bench": 80.8,
            "terminal_bench": 65.4,
        },
        "features": ["vision", "tools", "extended_thinking", "adaptive"],
        "provider": "anthropic",
    },
}


# =============================================================================
# Token Limits
# =============================================================================

class TokenLimits:
    """Token limit constants."""

    # By complexity level
    LOW_MAX_TOKENS = 2000
    MEDIUM_MAX_TOKENS = 4000
    HIGH_MAX_TOKENS = 8000

    # By worker type
    CODE_MAX_TOKENS = 4000
    SEARCH_MAX_TOKENS = 2000
    REVIEW_MAX_TOKENS = 3000
    DOCS_MAX_TOKENS = 4000
    TEST_MAX_TOKENS = 3000

    # Output processing limits
    THINKING_LINE_LIMIT = 150  # Max lines to process for thinking prefix removal
    OUTPUT_LINE_LIMIT = 100    # Max lines in final output after filtering


# =============================================================================
# Complexity Thresholds
# =============================================================================

class ComplexityThresholds:
    """Complexity detection thresholds."""

    LOW_LINES = 100      # < 100 lines = LOW
    MEDIUM_LINES = 500   # < 500 lines = MEDIUM
    # >= 500 lines = HIGH


# =============================================================================
# Consensus & Quality
# =============================================================================

class QualityThresholds:
    """Quality and consensus thresholds."""

    # Consensus thresholds
    FAST_THRESHOLD = 90      # >= 90% consensus = FAST tier
    STANDARD_THRESHOLD = 70  # >= 70% consensus = STANDARD tier
    # < 70% = DEEP tier

    # Score range
    MIN_SCORE = 0
    MAX_SCORE = 100

    # Consensus calculation
    CONSENSUS_PERCENTAGE = 80  # 80% of experts must agree


# =============================================================================
# Retry & Timeout
# =============================================================================

class RetryConfig:
    """Retry and timeout configuration."""

    MAX_RETRIES = 3
    INITIAL_DELAY = 2.0    # seconds
    MAX_DELAY = 8.0       # seconds
    BACKOFF_MULTIPLIER = 2

    # API timeout
    API_TIMEOUT = 60       # seconds (reduced from 300; Ollama <10s, cloud APIs <30s)


class TimeoutConfig:
    """Per-backend timeout configuration (seconds).

    Cloud models (GLM, Kimi via Ollama proxy) can take 60-180s per call.
    Local subprocess calls are fast (<10s).
    """
    SUBPROCESS = 60        # subprocess: ollama run
    SDK_LOCAL = 60         # SDK → local Ollama (fast models, no :cloud suffix)
    SDK_CLOUD = 180        # SDK → cloud proxy (GLM, Kimi: 60-180s latency)


# =============================================================================
# Worker Configuration
# =============================================================================

class WorkerConstants:
    """Worker configuration constants."""

    DEFAULT_MAX_WORKERS = 4
    ORCHESTRATOR_MAX_WORKERS = 10


# =============================================================================
# CLI Priority
# =============================================================================

class CLIPriority:
    """CLI fallback priority (lower = higher priority)."""

    OLLAMA = 1
    CLAUDE = 2
    GLM = 3


# =============================================================================
# Agent Executor Defaults
# =============================================================================

class AgentExecutorDefaults:
    """Defaults for Path B (ollama launch claude) agent execution."""

    ALLOWED_TOOLS: List[str] = ["Read", "Grep", "Glob"]
    BUDGET_USD: float = 0.20
    TIMEOUT_SEC: int = 120
    EFFORT: str = "low"


# =============================================================================
# Task Types
# =============================================================================

class TaskTypes:
    """Valid task types."""

    AUDIT = "audit"
    ANALYZE = "analyze"
    ARCHITECTURE = "architecture"
    REFACTOR = "refactor"
    MIGRATE = "migrate"
    REVIEW = "review"
    DOCS = "docs"
    TEST = "test"
    EXPLAIN = "explain"

    ALL = [AUDIT, ANALYZE, ARCHITECTURE, REFACTOR, MIGRATE, REVIEW, DOCS, TEST, EXPLAIN]

    # Tasks that always use DEEP tier
    ALWAYS_DEEP = [ARCHITECTURE, AUDIT, MIGRATE]


# =============================================================================
# Expert Domains
# =============================================================================

class ExpertDomains:
    """Expert domain constants."""

    # Security experts
    SECURITY = "security"
    OWASP = "owasp"
    AUTH = "auth"
    INPUT = "input"

    # Performance experts
    PERFORMANCE = "performance"
    COMPLEXITY = "complexity"
    DATABASE = "database"
    MEMORY = "memory"

    # Architecture experts
    ARCHITECTURE = "architecture"
    PATTERNS = "patterns"
    SOLID = "solid"
    SCALABILITY = "scalability"

    # Other domains
    REFACTOR = "refactor"
    MIGRATE = "migrate"


# =============================================================================
# Default Models by Task
# =============================================================================

DEFAULT_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GLM_5_CLOUD,
    TaskTypes.ANALYZE: Models.GLM_5_CLOUD,
    TaskTypes.ARCHITECTURE: Models.KIMI_K25_CLOUD,
    TaskTypes.REFACTOR: Models.KIMI_K25_CLOUD,
    TaskTypes.MIGRATE: Models.KIMI_K25_CLOUD,
    TaskTypes.REVIEW: Models.KIMI_K25_CLOUD,
    TaskTypes.DOCS: Models.GLM_5_CLOUD,
    TaskTypes.TEST: Models.GLM_5_CLOUD,
    TaskTypes.EXPLAIN: Models.KIMI_K25_CLOUD,
}

# Fallback model when task not found
FALLBACK_MODEL = Models.KIMI_K25_CLOUD


# =============================================================================
# CLI Configurations
# =============================================================================

# Ollama models by task
OLLAMA_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GLM_5_CLOUD,
    TaskTypes.ANALYZE: Models.GLM_5_CLOUD,
    TaskTypes.ARCHITECTURE: Models.KIMI_K25_CLOUD,
    TaskTypes.REFACTOR: Models.KIMI_K25_CLOUD,
    TaskTypes.MIGRATE: Models.KIMI_K25_CLOUD,
    TaskTypes.REVIEW: Models.KIMI_K25_CLOUD,
}

# Claude models by task (fallback)
CLAUDE_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.CLAUDE_SONNET,
    TaskTypes.ANALYZE: Models.CLAUDE_SONNET,
    TaskTypes.ARCHITECTURE: Models.CLAUDE_OPUS,
    TaskTypes.REFACTOR: Models.CLAUDE_SONNET,
    TaskTypes.MIGRATE: Models.CLAUDE_OPUS,
    TaskTypes.REVIEW: Models.CLAUDE_SONNET,
}

# GLM models by task (budget option)
GLM_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GLM_5_CLOUD,
    TaskTypes.ANALYZE: Models.GLM_5_CLOUD,
    TaskTypes.ARCHITECTURE: Models.GLM_5_CLOUD,
    TaskTypes.REFACTOR: Models.GLM_5_CLOUD,
    TaskTypes.MIGRATE: Models.GLM_5_CLOUD,
    TaskTypes.REVIEW: Models.GLM_5_CLOUD,
}


# Maps model name prefixes to CLI type (longest prefix wins)
# Used by cli.py to select cli_type without SmartRouter
_MODEL_CLI_MAP: Dict[str, str] = {
    "glm": "ollama",
    "kimi": "ollama",
    "gemma": "ollama",
    "haiku": "claude",
    "sonnet": "claude",
    "opus": "claude",
    "claude": "claude",
}


def _cli_for_model(model: str) -> str:
    """Return CLI name for a model string, defaulting to 'ollama'."""
    model_lower = model.lower()
    for prefix, cli in _MODEL_CLI_MAP.items():
        if model_lower.startswith(prefix):
            return cli
    return "ollama"


# =============================================================================
# CLI Strengths
# =============================================================================

CLI_STRENGTHS = {
    "ollama": ["structured_output", "security", "performance", "architecture"],
    "claude": ["reasoning", "structured_output", "safety"],
    "glm": ["chinese_market", "structured_output", "cloud"],
}


# =============================================================================
# Adaptive Routing Configuration
# =============================================================================

class AdaptiveConfig:
    """Constants for the adaptive CLI routing algorithm."""

    STREAK_WINDOW = 3  # consecutive runs to trigger streak lock/skip
    MIN_RUNS_BEFORE_OVERRIDE = 10  # Phase 3 gate (rated runs only)
    WIN_RATE_DELTA_THRESHOLD = 0.15  # 15 percentage points for permanent override
    ANTI_THRASH_WINDOW = 3  # look-back window for oscillation detection
    ANTI_THRASH_DISTINCT_LIMIT = 3  # ≥3 distinct CLIs in window = thrashing


class HealthConfig:
    """TTL constants (seconds) for CLI health degradation."""

    RATE_LIMIT_TTL = 300.0  # 5 min burst window
    NETWORK_TTL = 60.0  # 1 min transient blip
    AUTH_TTL = float("inf")  # indefinite — needs user intervention


# CLI_PRIORS: pre-seeded win rates stored as virtual runs at _init_db() time.
# win_rate=0.80 → 8 wins, 2 losses out of 10 virtual runs
CLI_PRIORS: Dict[str, Dict[str, float]] = {
    "claude": {"audit": 0.80, "analyze": 0.75, "review": 0.75},
    "ollama": {
        "audit": 0.70,
        "analyze": 0.70,
        "architecture": 0.65,
        "review": 0.70,
        "refactor": 0.65,
        "migrate": 0.65,
    },
}