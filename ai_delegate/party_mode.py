"""Party Mode: multi-turn adversarial debate where experts challenge each other."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import List

from .models import ExpertResult, Finding, Verdict, TaskConfig, Tier

logger = logging.getLogger(__name__)


class PartyDebate:
    """
    BMAD-inspired Party Mode: all experts respond, see each other's findings,
    then respond again in a structured multi-turn debate.
    """

    def __init__(self, client, task_config: TaskConfig, rounds: int = 2, verbose: bool = False):
        self.client = client
        self.task_config = task_config
        self.rounds = rounds
        self.verbose = verbose

    def run(self, content: str) -> Verdict:
        """Run party mode debate and return final verdict."""
        round1_results = self._run_round1(content)
        if self.verbose:
            logger.info(f"[Party] Round 1 complete: {len(round1_results)} experts responded")

        round2_results = self._run_round2(round1_results)
        if self.verbose:
            logger.info("[Party] Round 2 complete: debate finished")

        verdict = self._adjudicate(round1_results + round2_results)
        return verdict

    def _run_round1(self, content: str) -> List[ExpertResult]:
        """Run round 1: independent expert analysis."""
        results = []

        with ThreadPoolExecutor(max_workers=len(self.task_config.experts)) as executor:
            import concurrent.futures
            futures = {
                executor.submit(self._expert_round1, name, prompt, content): name
                for name, prompt in self.task_config.experts.items()
            }
            for future in concurrent.futures.as_completed(futures):
                name = futures[future]
                try:
                    results.append(future.result())
                except Exception as e:
                    logger.error(f"[Party] Round 1 failed for {name}: {e}")

        return results

    def _expert_round1(self, expert_name: str, expert_prompt: str, content: str) -> ExpertResult:
        prompt = f"""{expert_prompt}

Content to analyze:
```
{content}
```

ROUND 1: Provide your initial analysis.
Output JSON with findings array."""

        output = self.client.run_json(prompt)
        findings = [
            Finding.from_dict(f)
            for f in output.get("findings", [])
            if isinstance(f, dict)
        ]
        return ExpertResult(
            expert_name=expert_name,
            expert_type=self.task_config.task_type,
            findings=findings,
            raw_output=json.dumps(output),
        )

    def _run_round2(self, round1_results: List[ExpertResult]) -> List[ExpertResult]:
        """Round 2: each expert sees all others' round 1 findings and responds."""
        results = []

        for result in round1_results:
            other_findings = "\n".join(
                f"**{r.expert_name}**: {r.raw_output}"
                for r in round1_results
                if r.expert_name != result.expert_name and not r.error
            )

            prompt = f"""You are {result.expert_name} Expert in a debate.

YOUR ROUND 1 FINDINGS:
{result.raw_output}

OTHER EXPERTS' FINDINGS:
{other_findings}

ROUND 2: Respond to the other experts.
- Where do you agree? (note it)
- Where do you disagree? (explain why)
- What new risks does reading their findings reveal?

Output JSON with:
{{
  "agreements": ["what you agree with"],
  "disagreements": [{{"expert": "name", "point": "their claim", "rebuttal": "your counter"}}],
  "findings": [updated findings array after considering all perspectives]
}}"""

            try:
                output = self.client.run_json(prompt)
                findings = [
                    Finding.from_dict(f)
                    for f in output.get("findings", [])
                    if isinstance(f, dict)
                ] or result.findings

                results.append(ExpertResult(
                    expert_name=f"{result.expert_name}:Round2",
                    expert_type=self.task_config.task_type,
                    findings=findings,
                    raw_output=json.dumps(output),
                ))
            except Exception as e:
                logger.error(f"[Party] Round 2 failed for {result.expert_name}: {e}")
                results.append(result)

        return results

    def _adjudicate(self, all_results: List[ExpertResult]) -> Verdict:
        """Synthesize all rounds into final verdict."""
        all_findings_text = "\n\n".join(
            f"### {r.expert_name}:\n{r.raw_output}"
            for r in all_results
            if not r.error
        )

        prompt = f"""You are the {self.task_config.task_type} Adjudicator.

{self.task_config.adjudicator_role}

PARTY DEBATE TRANSCRIPT:
{all_findings_text}

Synthesize all rounds of debate into a final verdict.
{self.task_config.output_format}"""

        output = self.client.run_json(prompt)
        return Verdict(
            task_type=self.task_config.task_type,
            consensus_score=0.8,
            tier_used=Tier.STANDARD.value,
            raw_output=json.dumps(output),
        )
