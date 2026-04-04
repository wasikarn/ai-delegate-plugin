"""Advanced elicitation methods for deeper analysis (BMAD-inspired)."""

import json
import logging
from typing import List

from .models import ExpertResult, Finding

logger = logging.getLogger(__name__)


class ElicitationMethod:
    PRE_MORTEM = "pre-mortem"
    FIRST_PRINCIPLES = "first-principles"
    INVERSION = "inversion"
    RED_TEAM = "red-team"
    CONSTRAINT_REMOVAL = "constraint-removal"
    ALL = [PRE_MORTEM, FIRST_PRINCIPLES, INVERSION, RED_TEAM, CONSTRAINT_REMOVAL]


_ELICITATION_PROMPTS = {
    ElicitationMethod.PRE_MORTEM: """## PRE-MORTEM ANALYSIS
Assume this code has already caused a serious production incident.
Ask: "What went wrong? Why did it fail?"
Find failure modes that were invisible in the initial analysis.""",

    ElicitationMethod.FIRST_PRINCIPLES: """## FIRST-PRINCIPLES ANALYSIS
Strip away all assumptions. What are the fundamental properties of this code?
What invariants must always hold? What would you build from scratch?
Find issues that violate fundamental constraints.""",

    ElicitationMethod.INVERSION: """## INVERSION ANALYSIS
Instead of asking "how do we make this work well?", ask "how do we make this fail badly?"
List the most effective ways an attacker or bug could exploit this code.
Then flip each point to find defensive improvements.""",

    ElicitationMethod.RED_TEAM: """## RED TEAM ANALYSIS
You are an adversary. Your goal is to find the most dangerous vulnerabilities.
Challenge every assumption in the initial findings.
Look for issues the initial analysis may have missed or downplayed.""",

    ElicitationMethod.CONSTRAINT_REMOVAL: """## CONSTRAINT REMOVAL ANALYSIS
Assume there are no constraints: infinite time, infinite resources, no backward compatibility.
What would the ideal solution look like?
Use the gap between ideal and current to identify the most impactful improvements.""",
}


class ElicitationEngine:
    """Apply a BMAD elicitation lens to deepen expert analysis."""

    def __init__(self, client):
        self.client = client

    def apply(
        self,
        method: str,
        expert_results: List[ExpertResult],
        content: str,
    ) -> List[ExpertResult]:
        """Apply elicitation method to existing findings, returning refined results."""
        if method not in _ELICITATION_PROMPTS:
            raise ValueError(f"Unknown elicitation method: {method}. Valid: {ElicitationMethod.ALL}")

        method_prompt = _ELICITATION_PROMPTS[method]

        findings_context = "\n".join(
            f"- [{r.expert_name}] {f.severity}: {f.issue}"
            for r in expert_results
            for f in r.findings
        )

        prompt = f"""{method_prompt}

ORIGINAL FINDINGS FROM EXPERTS:
{findings_context}

CODE BEING ANALYZED:
```
{content}
```

Apply the {method} lens to re-examine this code and the existing findings.
Look for anything missed, underestimated, or worth re-framing.

Output JSON with:
{{
  "elicitation_method": "{method}",
  "new_risks": ["list of newly discovered risks"],
  "refined_findings": [
    {{"severity": "critical|high|medium|low", "issue": "description", "recommendation": "fix"}}
  ]
}}"""

        try:
            output = self.client.run_json(prompt)
            refined_findings_raw = output.get("refined_findings", [])

            if not isinstance(refined_findings_raw, list):
                refined_findings_raw = []

            refined_findings = [
                Finding.from_dict(f) for f in refined_findings_raw if isinstance(f, dict)
            ]

            if not refined_findings:
                logger.warning(f"Elicitation ({method}) produced no refined findings — keeping originals")
                return expert_results

            elicitation_result = ExpertResult(
                expert_name=f"Elicitation:{method}",
                expert_type="elicitation",
                findings=refined_findings,
                raw_output=json.dumps(output),
                persona_name=f"Elicitation ({method})",
            )

            return list(expert_results) + [elicitation_result]

        except Exception as e:
            logger.error(f"Elicitation ({method}) failed: {e}")
            return expert_results
