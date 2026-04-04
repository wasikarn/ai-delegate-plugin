# CLI Reference

## Task Types

| Task | Description | Default Model |
|------|-------------|---------------|
| `audit` | Security audit (OWASP, auth, input) | glm-5:cloud |
| `analyze` | Performance analysis | glm-5:cloud |
| `architecture` | Architecture review | kimi-k2.5:cloud |
| `refactor` | Refactoring analysis | kimi-k2.5:cloud |
| `migrate` | Migration analysis | kimi-k2.5:cloud |
| `review` | Multi-domain code review | kimi-k2.5:cloud |

## Options

| Option | Description |
|--------|-------------|
| `--tier <tier>` | Quality tier: auto, fast, standard, deep |
| `--model <model>` | Override default model |
| `--file <path>` | Read content from file |
| `--output <format>` | Output format: json (default), text |
| `--verbose, -v` | Enable verbose logging |
| `-d, --domains` | Comma-separated domains (for review) |

## Input Methods

```bash
# Pipe via stdin (quick snippets)
echo "user_input = request.GET['id']" | ai-delegate audit

# Read from file
ai-delegate audit --file src/auth.py

# Directory analysis (architecture)
ai-delegate architecture --file ./src/
```

## Examples

### Security Audit

```bash
# Quick security audit
echo "password = request.POST['pwd']" | ai-delegate audit

# Full file audit with deep tier
ai-delegate audit --tier deep --file src/auth.py

# Custom model for security
ai-delegate audit --model glm-5:cloud --file src/auth.py
```

### Performance Analysis

```bash
# Performance analysis
ai-delegate analyze --file src/api.py

# Deep performance analysis
ai-delegate analyze --tier deep --file src/api.py
```

### Architecture Review

```bash
# Review architecture documentation
ai-delegate architecture --file ./docs/architecture.md

# Review source directory
ai-delegate architecture --file ./src/
```

### Multi-Domain Code Review

```bash
# Security + Performance domains
ai-delegate review src/main.py -d security,performance

# All domains (comprehensive)
ai-delegate review src/ -d all

# Specific domains
ai-delegate review src/api.py -d security,architecture,refactor
```

### Output Formats

```bash
# JSON (default, machine-readable)
ai-delegate audit --file src/auth.py

# Text (human-readable)
ai-delegate audit --output text --file src/auth.py

# Verbose logging
ai-delegate analyze -v --file src/api.py
```

## Output Format

**JSON (default):**

```json
{
  "task_type": "audit",
  "consensus_score": 0.85,
  "tier_used": "deep",
  "findings": [
    {
      "severity": "high",
      "title": "XSS vulnerability in search",
      "description": "User input not sanitized"
    }
  ],
  "recommendations": [
    "Sanitize user input",
    "Add CSRF protection"
  ],
  "action_items": [
    "Add input validation",
    "Implement content security policy"
  ]
}
```

**Text:**

```
Task: SECURITY AUDIT
Tier: deep
Consensus: 85%

Findings:
  [high] XSS vulnerability in search
    User input not sanitized
  [medium] CSRF token missing
    Form submissions lack CSRF token

Recommendations:
  - Sanitize user input
  - Add CSRF protection

Action Items:
  - Add input validation
  - Implement content security policy
```
