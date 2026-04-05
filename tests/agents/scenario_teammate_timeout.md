# Scenario: Teammate Timeout (Silent Expert → Unresolved)

## Input Bundle

```json
{
  "disputed_findings": [
    {"severity": "medium", "issue": "Session token not invalidated on logout", "recommendation": "call session.invalidate() in logout handler"}
  ],
  "expert_results": [
    {"expert_name": "owasp", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Session token not invalidated on logout"}]},
    {"expert_name": "auth", "expert_type": "security", "findings": [{"severity": "medium", "issue": "Session token not invalidated on logout"}]},
    {"expert_name": "input", "expert_type": "security", "findings": []}
  ],
  "task_type": "audit",
  "file_context": "src/auth.py"
}
```

## Expert Responses (simulated)

- owasp: `Finding: Session token not invalidated on logout | Verdict: AGREE`
- auth: `Finding: Session token not invalidated on logout | Verdict: AGREE`
- input: *(no response — timeout)*

## Expected DebateResult

Lead receives 2 responses. Input expert silent. Safe policy: treat silent expert
as non-vote (not AGREE). 2 AGREE out of 3 = 67% < 80% → **unresolved**.

```json
{
  "resolved_findings": [],
  "unresolved_findings": [{"severity": "medium", "issue": "Session token not invalidated on logout", "recommendation": "call session.invalidate() in logout handler"}],
  "debate_summary": "2 agreed, 1 timeout (safe: treated as non-vote) — escalating to Adjudicator"
}
```

**Assertion:** Timeout is treated as non-AGREE. Finding escalates to Adjudicator.
**Design note:** This ensures timeouts never silently resolve findings.
