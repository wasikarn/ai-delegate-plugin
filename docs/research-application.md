# Research Application: Token Optimization for ai-delegate-plugin

**Date:** 2026-04-04
**Sources:** deep-research-2026-04-04.md, facebook-posts-analysis-2026-04-04.md

---

## Executive Summary

การประยุกต์ใช้ผลการวิจัยกับ ai-delegate-plugin เพื่อลด token consumption และเพิ่มประสิทธิภาพ

| Metric | Target | Method |
|--------|--------|--------|
| **SKILL.md size** | <300 tokens | Progressive disclosure |
| **Startup tokens** | -82% | Split into references |
| **Expert cost** | -50% | Model selection by complexity |
| **Cache hit rate** | >90% | Cache-friendly hooks |

---

## 1. Skills Optimization (82-98% savings)

### Current State

```
SKILL.md: 127 lines, ~800 tokens
├── Setup instructions (20 lines)
├── Smart Router explanation (30 lines)
├── Quick Start (10 lines)
├── Architecture (20 lines)
├── Domain Experts (10 lines)
├── Quality Tiers (10 lines)
├── Python API (15 lines)
├── Supported CLIs (10 lines)
└── References (5 links)
```

### Recommended: Progressive Disclosure

```
SKILL.md: <60 lines, ~300 tokens (target)
├── name + description (always loaded)
├── Quick Start (essential only)
├── Smart Router table (compact)
└── References links (on-demand)

references/ (loaded on-demand, unlimited size)
├── setup.md (moved from SKILL.md)
├── architecture.md (existing)
├── domain-experts.md (moved)
├── python-api.md (moved)
├── models.md (existing)
└── cli-reference.md (existing)
```

### Implementation

**Step 1:** Extract sections from SKILL.md to separate files

**Step 2:** Update SKILL.md to minimal version

**Step 3:** Update references links

---

## 2. Model Selection by Complexity (50-70% savings)

### Research Insight

> "Single-agent with KV cache reuse matches/beats MAS on 7 benchmarks with 53.7% token reduction"
> "Haiku for mechanical tasks = ~5x cheaper"

### Current Implementation

All experts use the same model selected by SmartRouter.

### Recommended: Complexity-Based Model Selection

```python
# ai_delegate/router.py

class ComplexityLevel(Enum):
    LOW = "low"        # Single vulnerability check
    MEDIUM = "medium"  # Multi-domain analysis
    HIGH = "high"      # Architecture + security

EXPERT_MODEL_MAP = {
    ComplexityLevel.LOW: {
        "model": "haiku",
        "cli": CLIType.CLAUDE,
        "reason": "Simple checks, fast response"
    },
    ComplexityLevel.MEDIUM: {
        "model": "glm-5:cloud",
        "cli": CLIType.OLLAMA,
        "reason": "Standard analysis, cost-effective"
    },
    ComplexityLevel.HIGH: {
        "model": "sonnet",
        "cli": CLIType.CLAUDE,
        "reason": "Complex reasoning, high accuracy"
    },
}

def detect_complexity(content: str, task_type: str) -> ComplexityLevel:
    """Detect content complexity for model selection."""
    lines = content.count('\n')

    if lines < 100 and task_type in ["audit"]:
        return ComplexityLevel.LOW
    elif lines < 500:
        return ComplexityLevel.MEDIUM
    else:
        return ComplexityLevel.HIGH
```

### Usage

```python
complexity = detect_complexity(code_content, "audit")
model_config = EXPERT_MODEL_MAP[complexity]
cli_type = model_config["cli"]
model = model_config["model"]
```

---

## 3. Expert Agent Optimization

### Research Insight

> "Optimal team size: 3-4 agents (saturation point)"
> "Multi-agent systems cost 3-15x more tokens than single-agent"

### Current State

3 experts: OWASP, Auth, Input (✅ within optimal range)

### Recommendations

1. **Keep 3 experts** (optimal)
2. **Use parallel execution** (already implemented)
3. **Add quality gates** (already have expert-gate.sh)
4. **Implement cost tiers:**

```python
# Instead of:
orchestrator = DebateOrchestrator(model="sonnet")  # Same for all

# Use:
def get_expert_config(expert_type: str, complexity: ComplexityLevel):
    if expert_type == "owasp" and complexity == ComplexityLevel.LOW:
        return {"model": "haiku", "max_tokens": 2000}
    elif expert_type == "architecture":
        return {"model": "sonnet", "max_tokens": 8000}
    else:
        return {"model": "glm-5:cloud", "max_tokens": 4000}
```

---

## 4. Context Engineering

### Research Insight

> "30%+ accuracy drop when answer is mid-context"
> "Position critical info at beginning or end, never middle"

### Application: Expert Output Format

```json
{
  "summary": "CRITICAL: 3 high-severity vulnerabilities found",
  "severity_breakdown": {"high": 3, "medium": 5, "low": 2},
  "top_findings": [
    {"severity": "high", "type": "SQL Injection", "location": "auth.py:45"}
  ],
  "domain": "security",
  "score": 75,
  "detailed_findings": [
    // Full details here (at end of JSON)
  ]
}
```

### Implementation

Update `expert_context.sh` to instruct experts:

```bash
CONTEXT="You are analyzing code for security vulnerabilities.
Focus on OWASP Top 10, input validation, authentication.

OUTPUT FORMAT (JSON):
1. summary - One-line critical finding (TOP)
2. severity_breakdown - Quick counts
3. top_findings - Top 3 most important
4. domain - Your domain
5. score - Confidence score
6. detailed_findings - Full analysis (BOTTOM)
"
```

---

## 5. Cache-Friendly Hooks

### Research Insight

> "Dynamic content breaks cache"
> "Cache hit rate: Poor 0-30% → Optimized 96%"

### Current Issues

1. **expert-context.sh** - Injects project context dynamically
2. **No static references** - Everything inline

### Recommended: Static Prompts + References

```bash
# expert-context.sh - BEFORE
CONTEXT="You are analyzing code for security vulnerabilities.
Project uses Next.js 14.2.0 with React 18. 
Focus on OWASP Top 10..."
# ❌ Dynamic framework detection breaks cache

# expert-context.sh - AFTER
CONTEXT="You are analyzing code for security vulnerabilities.
Focus on OWASP Top 10, input validation, authentication.

PROJECT CONTEXT: See ${CWD}/.claude/project-context.md
FRAMEWORK: See ${CWD}/package.json"
# ✅ Static prompt, references external file
```

### Cache Hit Optimization

```bash
# Normalize JSON output
jq -S '.' findings.json > findings-sorted.json

# Round timestamps
DATE=$(date -u +"%Y-%m-%dT%H:00:00Z")  # Round to hour
```

---

## 6. Configuration Updates

### Recommended Environment Variables

```json
{
  "env": {
    "MAX_THINKING_TOKENS": "8000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "75",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku",
    "CLAUDE_CODE_NO_FLICKER": "1"
  }
}
```

### Recommended `.claudeignore`

```gitignore
# Dependencies
node_modules/
__pycache__/
*.pyc
.venv/
venv/

# Build outputs
dist/
build/
*.egg-info/

# Generated files
*.generated.*

# Test fixtures
tests/fixtures/
**/__snapshots__/

# Lock files
package-lock.json
poetry.lock
```

---

## 7. Implementation Priority

### P0: Immediate (High Impact, Low Effort)

| Task | Impact | Effort |
|------|--------|--------|
| Add `MAX_THINKING_TOKENS=8000` | 50-70% | 1 min |
| Create `.claudeignore` | 20-40% | 5 min |
| Split SKILL.md | 82% startup | 30 min |
| Update expert output format | Quality | 15 min |

### P1: Short-term (High Impact, Medium Effort)

| Task | Impact | Effort |
|------|--------|--------|
| Implement complexity detection | 50% | 2 hours |
| Add model selection by complexity | 50% | 2 hours |
| Make hooks cache-friendly | 76-90% cache | 1 hour |

### P2: Medium-term (Optimization)

| Task | Impact | Effort |
|------|--------|--------|
| Add alternative model support (DeepSeek) | Cost | 4 hours |
| Implement supervisor+worker pattern | 98% delegated | 8 hours |
| Add parallel read optimization | 15% speed | 2 hours |

---

## 8. Expected Results

### Before Optimization

```
Startup tokens: ~800 (SKILL.md)
Expert execution: 3 × sonnet = high cost
Cache hit rate: ~50% (dynamic content)
Total session: 100% baseline
```

### After Optimization

```
Startup tokens: ~150 (SKILL.md slim) -82%
Expert execution: tiered models -50%
Cache hit rate: ~90% (cache-friendly) -40% input
Total session: ~40-50% baseline
```

### Combined Savings: **50-80%**

---

## 9. Monitoring

### Key Metrics to Track

```python
# Add to ai_delegate/metrics.py

class Metrics:
    cache_hit_rate: float      # Target: >90%
    token_count: int           # Track per task
    model_distribution: dict   # Track by complexity
    expert_cost: dict          # Track by expert type
```

### Dashboard

```
Task: audit
├── Complexity: MEDIUM
├── Model: glm-5:cloud
├── Cache hit: 94%
├── Tokens: 2,450 input, 890 output
└── Cost: $0.0032
```

---

## 10. References

- [deep-research-2026-04-04.md](../.claude/deep-research-2026-04-04.md)
- [facebook-posts-analysis-2026-04-04.md](../.claude/facebook-posts-analysis-2026-04-04.md)
- [Prompt Caching Docs](https://docs.anthropic.com/claude/docs/prompt-caching)
- [Multi-Agent Research](https://arxiv.org/abs/2401.xxxxx)
