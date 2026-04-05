# Scenario: Split Verdict (1 AGREE, 1 CHALLENGE, 1 WITHDRAW — Unresolved)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "high", "issue": "Insecure direct object reference in user profile endpoint", "recommendation": "add authorization check"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]},
    {"expert_name": "input", "expert_type": "security", "findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint"}]}
  ],
  "task_type": "audit",
  "file_context": "src/user_profile.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Insecure direct object reference in user profile endpoint | Verdict: AGREE`
- auth: `Finding: Insecure direct object reference in user profile endpoint | Verdict: CHALLENGE: auth middleware already enforces ownership check at route level`
- input: `Finding: Insecure direct object reference in user profile endpoint | Verdict: WITHDRAW`

## Expected DebateResult

1 AGREE out of 3 = 33% — below 80% → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "high", "issue": "Insecure direct object reference in user profile endpoint", "recommendation": "add authorization check"}],
  "debate_summary": "Split verdict: 1 agree, 1 challenge, 1 withdraw — escalating to Adjudicator"
}
```

**Assertion:** finding is in `unresolved_findings`. Adjudicator receives this for final judgment.
