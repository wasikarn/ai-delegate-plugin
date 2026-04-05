# Scenario: All Experts Agree

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "high", "issue": "SQL injection in login query", "recommendation": "use parameterized queries"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]},
    {"expert_name": "input", "expert_type": "security", "findings": [{"severity": "high", "issue": "SQL injection in login query"}]}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: SQL injection in login query | Verdict: AGREE`
- auth: `Finding: SQL injection in login query | Verdict: AGREE`
- input: `Finding: SQL injection in login query | Verdict: AGREE`

## Expected DebateResult

```json
{
  "resolved_findings": [{"severity": "high", "issue": "SQL injection in login query", "recommendation": "use parameterized queries"}],
  "unresolved_findings": [],
  "debate_summary": "All 3 experts agreed on SQL injection finding (100% consensus)"
}
```

**Assertion:** `unresolved_findings` must be empty — Adjudicator should NOT be called.
