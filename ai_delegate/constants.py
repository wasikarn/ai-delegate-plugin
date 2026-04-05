"""
Centralized configuration for AI Delegation Framework.

All hardcoded values are centralized here for easy configuration.
"""

from typing import Dict, List
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

    # Gemini models
    GEMINI_20_FLASH = "gemini-2.0-flash"
    GEMINI_25_PRO = "gemini-2.5-pro"

    # Codex models
    GPT_4O = "gpt-4o"
    O3_MINI = "o3-mini"


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
    SUBPROCESS = 60        # subprocess: ollama run, gemini, codex
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
    GEMINI = 2
    CODEX = 3
    CLAUDE = 4
    GLM = 5


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

# Gemini models by task
GEMINI_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GEMINI_20_FLASH,
    TaskTypes.ANALYZE: Models.GEMINI_20_FLASH,
    TaskTypes.ARCHITECTURE: Models.GEMINI_25_PRO,
    TaskTypes.REFACTOR: Models.GEMINI_20_FLASH,
    TaskTypes.MIGRATE: Models.GEMINI_25_PRO,
    TaskTypes.REVIEW: Models.GEMINI_25_PRO,
}

# Codex models by task
CODEX_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GPT_4O,
    TaskTypes.ANALYZE: Models.GPT_4O,
    TaskTypes.ARCHITECTURE: Models.O3_MINI,
    TaskTypes.REFACTOR: Models.GPT_4O,
    TaskTypes.MIGRATE: Models.O3_MINI,
    TaskTypes.REVIEW: Models.O3_MINI,
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
    "gemini": "gemini",
    "gpt": "codex",
    "o3": "codex",
    "o1": "codex",
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
    "gemini": ["fast", "reasoning", "multimodal"],
    "codex": ["code_generation", "reasoning", "documentation"],
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
    "codex": {"architecture": 0.80, "refactor": 0.75, "migrate": 0.75},
    "claude": {"audit": 0.80, "analyze": 0.75, "review": 0.75},
    "ollama": {
        "audit": 0.70,
        "analyze": 0.70,
        "architecture": 0.65,
        "review": 0.70,
        "refactor": 0.65,
        "migrate": 0.65,
    },
    "gemini": {
        "audit": 0.65,
        "analyze": 0.70,
        "architecture": 0.65,
        "review": 0.70,
        "refactor": 0.65,
        "migrate": 0.65,
    },
}