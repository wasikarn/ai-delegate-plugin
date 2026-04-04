"""
Input validation for AI Delegation Framework.

Provides security-focused validation for:
- Prompts (length, content safety, injection protection)
- Model names (whitelist validation)
- File paths (path traversal protection)
- Content (size limits, safety)
"""

import re
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

from .constants import Models, TaskTypes


@dataclass
class ValidationResult:
    """Result of validation."""
    valid: bool
    error: Optional[str] = None
    warning: Optional[str] = None
    sanitized: Optional[str] = None


# Valid model names whitelist
VALID_MODELS = {
    # Claude models
    Models.CLAUDE_HAIKU,
    Models.CLAUDE_SONNET,
    Models.CLAUDE_OPUS,
    # Ollama models
    Models.GLM_5_CLOUD,
    Models.KIMI_K25_CLOUD,
    # Gemini models
    Models.GEMINI_20_FLASH,
    Models.GEMINI_25_PRO,
    # Codex models
    Models.GPT_4O,
    Models.O3_MINI,
}

# Prompt safety patterns to detect
PROMPT_INJECTION_PATTERNS = [
    # System prompt injection attempts
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?prior\s+instructions",
    r"forget\s+(all\s+)?previous\s+instructions",
    r"system\s*:\s*you\s+are",
    r"<\|system\|>",
    # Escape attempts
    r"</system>",
    r"</instruction>",
    r"</prompt>",
    # Dangerous instructions
    r"output\s+your\s+(system\s+)?prompt",
    r"reveal\s+your\s+instructions",
    r"print\s+your\s+instructions",
]

# Compile patterns once for performance
COMPILED_INJECTION_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in PROMPT_INJECTION_PATTERNS
]

# Maximum sizes for validation
MAX_PROMPT_LENGTH = 100000  # 100KB max prompt
MAX_CONTENT_LENGTH = 1000000  # 1MB max content
MAX_FILE_SIZE = 10000000  # 10MB max file size


def validate_prompt(prompt: str, strict: bool = False) -> ValidationResult:
    """
    Validate AI prompt for security and safety.

    Args:
        prompt: Prompt string to validate
        strict: If True, reject on warnings; if False, sanitize

    Returns:
        ValidationResult with validation outcome
    """
    if not prompt:
        return ValidationResult(
            valid=False,
            error="Prompt cannot be empty"
        )

    # Length check
    if len(prompt) > MAX_PROMPT_LENGTH:
        return ValidationResult(
            valid=False,
            error=f"Prompt exceeds maximum length ({MAX_PROMPT_LENGTH} chars). Current: {len(prompt)}"
        )

    # Check for injection patterns
    warnings = []
    sanitized = prompt

    for pattern in COMPILED_INJECTION_PATTERNS:
        match = pattern.search(prompt)
        if match:
            warning_msg = f"Potential prompt injection detected: pattern matched near '{match.group()}'"
            if strict:
                return ValidationResult(
                    valid=False,
                    error=warning_msg
                )
            warnings.append(warning_msg)
            # Remove the matched pattern
            sanitized = pattern.sub("[REDACTED]", sanitized)

    # Check for suspicious character sequences
    suspicious_patterns = [
        (r'\x00', "Null byte detected"),
        (r'\x1b', "Escape sequence detected"),
        (r'<\?php', "PHP tag detected"),
        (r'<script', "Script tag detected"),
    ]

    for pattern, msg in suspicious_patterns:
        if re.search(pattern, prompt, re.IGNORECASE):
            if strict:
                return ValidationResult(
                    valid=False,
                    error=msg
                )
            warnings.append(msg)

    # Return result
    if warnings:
        return ValidationResult(
            valid=True,
            warning="; ".join(warnings),
            sanitized=sanitized if sanitized != prompt else None
        )

    return ValidationResult(valid=True)


def validate_model_name(model: str) -> ValidationResult:
    """
    Validate model name against whitelist.

    Args:
        model: Model name to validate

    Returns:
        ValidationResult with validation outcome
    """
    if not model:
        return ValidationResult(
            valid=False,
            error="Model name cannot be empty"
        )

    # Check against whitelist
    if model in VALID_MODELS:
        return ValidationResult(valid=True)

    # Check for common model name patterns (allow flexibility)
    # Models often have patterns like "model-name:variant" or "model-name"
    valid_patterns = [
        r'^[a-z0-9-]+$',  # Simple model name
        r'^[a-z0-9-]+:[a-z0-9-.]+$',  # Model with variant
        r'^[a-z0-9-]+-[0-9.]+$',  # Model with version number
    ]

    for pattern in valid_patterns:
        if re.match(pattern, model, re.IGNORECASE):
            return ValidationResult(
                valid=True,
                warning=f"Model '{model}' not in validated whitelist but matches naming pattern"
            )

    return ValidationResult(
        valid=False,
        error=f"Invalid model name '{model}'. Must match pattern: name, name:variant, or name-version"
    )


def validate_file_path(
    file_path: Path,
    base_dir: Optional[Path] = None,
    must_exist: bool = True
) -> ValidationResult:
    """
    Validate file path for security (path traversal protection).

    Args:
        file_path: Path to validate
        base_dir: Base directory for relative paths (prevents traversal)
        must_exist: If True, file must exist

    Returns:
        ValidationResult with validation outcome
    """
    if not file_path:
        return ValidationResult(
            valid=False,
            error="File path cannot be empty"
        )

    try:
        # Resolve to absolute path
        resolved_path = file_path.resolve()

        # Check for path traversal attempts
        dangerous_patterns = [
            '..',  # Parent directory
            '~',  # Home directory expansion
            '$',  # Environment variables
            '|',  # Pipe
            ';',  # Command separator
            '&',  # Background execution
            '`',  # Command substitution
            '$(',  # Command substitution
        ]

        path_str = str(file_path)
        for pattern in dangerous_patterns:
            if pattern in path_str:
                return ValidationResult(
                    valid=False,
                    error=f"Potentially dangerous path pattern detected: '{pattern}'"
                )

        # If base directory specified, ensure path is within it
        if base_dir:
            base_resolved = base_dir.resolve()
            try:
                resolved_path.relative_to(base_resolved)
            except ValueError:
                return ValidationResult(
                    valid=False,
                    error=f"Path '{file_path}' is outside allowed base directory '{base_dir}'"
                )

        # Check existence if required
        if must_exist and not resolved_path.exists():
            return ValidationResult(
                valid=False,
                error=f"File not found: {file_path}"
            )

        # Check file size if exists
        if resolved_path.exists() and resolved_path.is_file():
            file_size = resolved_path.stat().st_size
            if file_size > MAX_FILE_SIZE:
                return ValidationResult(
                    valid=False,
                    error=f"File size ({file_size} bytes) exceeds maximum ({MAX_FILE_SIZE} bytes)"
                )

        return ValidationResult(valid=True, sanitized=str(resolved_path))

    except Exception as e:
        return ValidationResult(
            valid=False,
            error=f"Invalid file path: {e}"
        )


def validate_content(content: str, max_length: int = MAX_CONTENT_LENGTH) -> ValidationResult:
    """
    Validate content for analysis.

    Args:
        content: Content string to validate
        max_length: Maximum allowed length

    Returns:
        ValidationResult with validation outcome
    """
    if not content:
        return ValidationResult(
            valid=False,
            error="Content cannot be empty"
        )

    # Strip and check again
    stripped = content.strip()
    if not stripped:
        return ValidationResult(
            valid=False,
            error="Content cannot be empty or whitespace only"
        )

    # Length check
    if len(content) > max_length:
        return ValidationResult(
            valid=False,
            error=f"Content exceeds maximum length ({max_length} chars). Current: {len(content)}"
        )

    # Check for null bytes (potential binary data)
    if '\x00' in content:
        return ValidationResult(
            valid=False,
            error="Content contains null bytes (binary data not supported)"
        )

    return ValidationResult(valid=True)


def validate_task_type(task_type: str) -> ValidationResult:
    """
    Validate task type against allowed values.

    Args:
        task_type: Task type to validate

    Returns:
        ValidationResult with validation outcome
    """
    if not task_type:
        return ValidationResult(
            valid=False,
            error="Task type cannot be empty"
        )

    valid_types = TaskTypes.ALL

    if task_type not in valid_types:
        return ValidationResult(
            valid=False,
            error=f"Invalid task type '{task_type}'. Valid types: {', '.join(valid_types)}"
        )

    return ValidationResult(valid=True)


def validate_tier(tier: str) -> ValidationResult:
    """
    Validate quality tier.

    Args:
        tier: Tier name to validate

    Returns:
        ValidationResult with validation outcome
    """
    from .models import Tier

    if not tier:
        return ValidationResult(
            valid=False,
            error="Tier cannot be empty"
        )

    valid_tiers = [t.value for t in Tier]

    if tier not in valid_tiers:
        return ValidationResult(
            valid=False,
            error=f"Invalid tier '{tier}'. Valid tiers: {', '.join(valid_tiers)}"
        )

    return ValidationResult(valid=True)


def validate_all(
    content: Optional[str] = None,
    task_type: Optional[str] = None,
    tier: Optional[str] = None,
    model: Optional[str] = None,
    file_path: Optional[Path] = None,
    prompt: Optional[str] = None,
    strict: bool = False,
) -> Tuple[bool, list, dict]:
    """
    Validate multiple inputs at once.

    Args:
        content: Content to validate
        task_type: Task type to validate
        tier: Tier to validate
        model: Model name to validate
        file_path: File path to validate
        prompt: Prompt to validate
        strict: If True, reject on warnings

    Returns:
        Tuple of (is_valid, errors, sanitized_values)
    """
    errors = []
    warnings = []
    sanitized = {}

    if content is not None:
        result = validate_content(content)
        if not result.valid:
            errors.append(f"Content: {result.error}")
        elif result.warning:
            warnings.append(f"Content: {result.warning}")

    if task_type is not None:
        result = validate_task_type(task_type)
        if not result.valid:
            errors.append(f"Task type: {result.error}")

    if tier is not None:
        result = validate_tier(tier)
        if not result.valid:
            errors.append(f"Tier: {result.error}")

    if model is not None:
        result = validate_model_name(model)
        if not result.valid:
            errors.append(f"Model: {result.error}")
        elif result.warning:
            warnings.append(f"Model: {result.warning}")

    if file_path is not None:
        result = validate_file_path(file_path)
        if not result.valid:
            errors.append(f"File path: {result.error}")
        elif result.sanitized:
            sanitized['file_path'] = result.sanitized

    if prompt is not None:
        result = validate_prompt(prompt, strict=strict)
        if not result.valid:
            errors.append(f"Prompt: {result.error}")
        elif result.warning:
            warnings.append(f"Prompt: {result.warning}")
            if result.sanitized:
                sanitized['prompt'] = result.sanitized

    # Check strict mode
    if strict and warnings:
        return False, errors + warnings, {'warnings': [], 'sanitized': sanitized}

    is_valid = len(errors) == 0
    return is_valid, errors, {'warnings': warnings, 'sanitized': sanitized}