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

    # DeepSeek models
    DEEPSEEK_CHAT = "deepseek-chat"
    DEEPSEEK_REASONER = "deepseek-reasoner"


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
    API_TIMEOUT = 300      # seconds


# =============================================================================
# CLI Priority
# =============================================================================

class CLIPriority:
    """CLI fallback priority (lower = higher priority)."""

    OLLAMA = 1
    GEMINI = 2
    CODEX = 3
    CLAUDE = 4
    DEEPSEEK = 5
    GLM = 6


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

# DeepSeek models by task (budget)
DEEPSEEK_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.DEEPSEEK_CHAT,
    TaskTypes.ANALYZE: Models.DEEPSEEK_CHAT,
    TaskTypes.ARCHITECTURE: Models.DEEPSEEK_REASONER,
    TaskTypes.REFACTOR: Models.DEEPSEEK_CHAT,
    TaskTypes.MIGRATE: Models.DEEPSEEK_REASONER,
    TaskTypes.REVIEW: Models.DEEPSEEK_CHAT,
}

# GLM models by task
GLM_MODELS: Dict[str, str] = {
    TaskTypes.AUDIT: Models.GLM_5_CLOUD,
    TaskTypes.ANALYZE: Models.GLM_5_CLOUD,
    TaskTypes.ARCHITECTURE: Models.GLM_5_CLOUD,
    TaskTypes.REFACTOR: Models.GLM_5_CLOUD,
    TaskTypes.MIGRATE: Models.GLM_5_CLOUD,
    TaskTypes.REVIEW: Models.GLM_5_CLOUD,
}


# =============================================================================
# CLI Strengths
# =============================================================================

CLI_STRENGTHS = {
    "ollama": ["structured_output", "security", "performance", "architecture"],
    "gemini": ["fast", "reasoning", "multimodal"],
    "codex": ["code_generation", "reasoning", "documentation"],
    "claude": ["reasoning", "structured_output", "safety"],
    "deepseek": ["budget", "fast", "reasoning"],
    "glm": ["chinese_market", "structured_output", "cloud"],
}