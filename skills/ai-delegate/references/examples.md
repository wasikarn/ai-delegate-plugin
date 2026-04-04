# Examples & Use Cases

Real-world usage examples for the AI Delegation Framework.

## Security Audit Example

```bash
# Audit authentication code
ai-delegate audit --file src/auth/login.py

# Output:
# 🔴 CRITICAL: SQL Injection in password query
#    File: src/auth/login.py:42
#    Recommendation: Use parameterized queries
#
# 🟠 HIGH: Hardcoded JWT secret
#    File: src/auth/config.py:15
#    Recommendation: Use environment variable
#
# 🟡 MEDIUM: Missing rate limiting
#    File: src/auth/routes.py:78
#    Recommendation: Add rate limiter middleware
#
# Security Score: 65/100
# Consensus: 85% (3 experts agree)
```

## Performance Analysis Example

```bash
# Analyze API performance
ai-delegate analyze --file src/api/users.py

# Output:
# 🔴 HIGH: N+1 query in user list
#    File: src/api/users.py:56
#    Impact: 1000 queries for 100 users
#    Recommendation: Use JOIN or batch loading
#
# 🟡 MEDIUM: Missing cache on frequent query
#    File: src/api/users.py:23
#    Impact: Unnecessary database calls
#    Recommendation: Add Redis cache
#
# Performance Score: 70/100
# Complexity: O(n²) in user processing
```

## Architecture Review Example

```bash
# Review module architecture
ai-delegate architecture --file ./src/services/

# Output:
# 🔴 HIGH: Circular dependency between User and Auth modules
#    Files: src/services/user.py ↔ src/services/auth.py
#    Recommendation: Extract shared interface to separate module
#
# 🟠 HIGH: God Class in PaymentService (800 lines)
#    File: src/services/payment.py
#    Violations: SRP, multiple responsibilities
#    Recommendation: Extract PaymentProcessor, RefundHandler, PaymentValidator
#
# 🟡 MEDIUM: Feature envy in OrderService
#    File: src/services/order.py:120-150
#    Recommendation: Move methods to Customer class
#
# Architecture Score: 60/100
# SOLID Violations: 5 (SRP: 2, OCP: 1, DIP: 2)
```

## Refactoring Analysis Example

```bash
# Analyze refactoring opportunities
ai-delegate refactor --file src/legacy/process_order.py

# Output:
# 🔴 HIGH: 150-line method (process_order)
#    File: src/legacy/process_order.py:10-160
#    Recommendation: Extract OrderValidator, PaymentProcessor, NotificationHandler
#
# 🟠 MEDIUM: Duplicate validation logic
#    Files: src/legacy/process_order.py:45, src/legacy/process_order.py:78
#    Recommendation: Extract to validate_order() function
#
# 🟡 MEDIUM: Deep nesting (5 levels)
#    File: src/legacy/process_order.py:60-90
#    Recommendation: Use early returns or Strategy pattern
#
# Refactoring Score: 55/100
# Applicable Patterns: Extract Method, Strategy, State
```

## Migration Analysis Example

```bash
# Analyze migration from v1 to v2
ai-delegate migrate --file ./src/ --from v1 --to v2

# Output:
# 🔴 CRITICAL: Removed API: authenticate() → authenticateUser()
#    Files: 15 affected
#    Migration: Update all authenticate() calls
#
# 🟠 HIGH: Signature change: getUser(id) → getUser(id, options)
#    Files: 23 affected
#    Migration: Add empty options object {}
#
# 🟡 MEDIUM: Deprecation: oldPayment() will be removed in v3
#    Files: 5 affected
#    Migration: Migrate to newPayment() within 6 months
#
# Migration Risk: HIGH
# Breaking Changes: 5
# Deprecations: 3
```

## Testing Analysis Example

```bash
# Analyze test coverage and quality
ai-delegate test --file tests/

# Output:
# 🔴 HIGH: Missing test for payment processing
#    File: src/services/payment.py
#    Coverage: 45% (critical: payment refund not tested)
#    Recommendation: Add test cases for refund scenarios
#
# 🟠 MEDIUM: Brittle test using implementation details
#    File: tests/auth.test.js:45
#    Issue: Testing private method directly
#    Recommendation: Test public API only
#
# 🟡 MEDIUM: Missing edge case tests
#    File: tests/user.test.js:12
#    Missing: null input, empty string, unicode
#    Recommendation: Add parameterized tests
#
# Coverage Score: 72%
# Test Quality Score: 68/100
```

## Code Quality Review Example

```bash
# Analyze code maintainability
ai-delegate quality --file src/

# Output:
# 🔴 HIGH: God Class (UserController: 1200 lines)
#    File: src/controllers/user.py
#    Cyclomatic Complexity: 45
#    Recommendation: Split into UserController, UserProfile, UserAuth
#
# 🟠 HIGH: Feature envy in OrderProcessor
#    File: src/services/order.py:200-250
#    Issue: Accesses Customer data more than own data
#    Recommendation: Move methods to Customer class
#
# 🟡 MEDIUM: Primitive obsession
#    File: src/models/payment.py
#    Issue: Using strings for Money, Currency
#    Recommendation: Create Money value object
#
# Quality Score: 62/100
# Technical Debt: ~40 hours remediation
```

## Database Analysis Example

```bash
# Analyze database schema and migrations
ai-delegate database --file migrations/

# Output:
# 🔴 CRITICAL: Missing index on foreign key
#    Table: orders.user_id
#    Impact: Slow JOIN queries
#    Recommendation: CREATE INDEX idx_orders_user_id ON orders(user_id)
#
# 🟠 HIGH: N+1 query pattern detected
#    File: src/repositories/user.py:30
#    Issue: Fetching orders per user in loop
#    Recommendation: Use eager loading or batch query
#
# 🟡 MEDIUM: Missing NOT NULL constraint
#    Table: users.email
#    Recommendation: Add NOT NULL constraint
#
# Schema Score: 75/100
# Migration Safety: HIGH
```

## Multi-Domain Review Example

```bash
# Comprehensive review across multiple domains
ai-delegate review src/main.py -d security,performance,architecture

# Output:
# ═══════════════════════════════════════════
# SECURITY FINDINGS (Consensus: 90%)
# ═══════════════════════════════════════════
# 🔴 SQL Injection in user query
# 🟠 Missing CSRF token validation
#
# ═══════════════════════════════════════════
# PERFORMANCE FINDINGS (Consensus: 75%)
# ═══════════════════════════════════════════
# 🔴 N+1 query in data loading
# 🟡 Missing cache on expensive computation
#
# ═══════════════════════════════════════════
# ARCHITECTURE FINDINGS (Consensus: 85%)
# ═══════════════════════════════════════════
# 🟠 Tight coupling to external service
# 🟡 Missing abstraction for configuration
#
# ═══════════════════════════════════════════
# ADJUDICATOR FINAL VERDICT
# ═══════════════════════════════════════════
# Priority: Fix SQL injection immediately
# Then: Address N+1 queries and CSRF
# Finally: Refactor tight coupling
#
# Overall Score: 68/100
# Tier: STANDARD (debate + adjudication)
```

## Python API Example

```python
from ai_delegate import SmartRouter, DebateOrchestrator, TaskConfig

# Auto-select best CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")
print(f"Using {cli_type.value} with {model}")

# Create orchestrator
config = TaskConfig.from_task_type("audit")
orchestrator = DebateOrchestrator(model=model, task_config=config)

# Analyze content
with open("src/auth.py") as f:
    content = f.read()

verdict = orchestrator.analyze(content, tier="auto")

print(f"Score: {verdict.consensus_score}")
print(f"Tier: {verdict.tier_used}")
print(f"Findings: {len(verdict.findings)}")

# Budget mode (98% cost reduction)
from ai_delegate import create_supervisor, WorkerType

supervisor = create_supervisor(budget_mode=True)
result = supervisor.delegate(
    WorkerType.CODE,
    analyze_code,
    file_path="src/auth.py"
)
```

## Budget Mode Example

```bash
# Run with budget models (GLM/Kimi via Ollama)
ai-delegate audit --budget --file src/auth.py

# Cost comparison:
# Standard (Claude Sonnet): ~$3/1M input tokens
# Budget (GLM-5 via Ollama): ~$0.05/1M input tokens
# Savings: ~98%
```

## CI/CD Integration Example

```yaml
# .github/workflows/ai-review.yml
name: AI Code Review

on: [pull_request]

jobs:
  review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Security Audit
        run: ai-delegate audit --file src/ --output json > security-report.json

      - name: Performance Analysis
        run: ai-delegate analyze --file src/ --output json > performance-report.json

      - name: Architecture Review
        run: ai-delegate architecture --file src/ --output json > architecture-report.json

      - name: Upload Reports
        uses: actions/upload-artifact@v3
        with:
          name: ai-reports
          path: '*.json'
```
