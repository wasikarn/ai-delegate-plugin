# Scenario: One Challenged, Two Agree (Unresolved — 67% below 80% threshold)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "medium", "issue": "Missing input sanitization on username field", "recommendation": "add regex validation"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Missing input sanitization on username field"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Missing input sanitization on username field"}]},
    {"expert_name": "input", "expert_type": "security", "findings": []}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Missing input sanitization on username field | Verdict: AGREE`
- auth: `Finding: Missing input sanitization on username field | Verdict: AGREE`
- input: `Finding: Missing input sanitization on username field | Verdict: CHALLENGE: username field already sanitized by ORM layer before reaching auth module`

## Expected DebateResult

2 AGREE out of 3 = 67% — below 80% threshold → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "medium", "issue": "Missing input sanitization on username field", "recommendation": "add regex validation"}],
  "debate_summary": "2 agreed, 1 challenged (ORM sanitization argument) — escalating to Adjudicator"
}
```

**Assertion:** finding is in `unresolved_findings` because 67% < 80%.
