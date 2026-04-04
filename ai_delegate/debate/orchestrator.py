"""
Debate Orchestrator for Multi-Expert Analysis.

Coordinates parallel expert analysis, debate rounds, and adjudication.
"""

import json
import math
import hashlib
import time
import logging
import atexit
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, ClassVar

from ..client import OllamaClient
from ..models import (
    Finding,
    ExpertResult,
    ConsensusResult,
    Verdict,
    TaskConfig,
    Tier,
)
from ..config import (
    CONSENSUS_THRESHOLD_FAST,
    CONSENSUS_THRESHOLD_STANDARD,
)
from ..constants import WorkerConstants, QualityThresholds

logger = logging.getLogger(__name__)


def build_findings(
    results: List[ExpertResult],
    exclude: Optional[str] = None,
) -> str:
    """
    Build findings string from expert results.

    Args:
        results: List of expert results
        exclude: Optional expert name to exclude

    Returns:
        Formatted findings string
    """
    parts = []
    for result in results:
        if result.error:
            continue
        if exclude and result.expert_name == exclude:
            continue
        parts.append(f"### {result.expert_name} Expert:\n{result.raw_output}\n")
    return "\n".join(parts)


class ConsensusCalculator:
    """Calculate consensus between expert findings."""

    @staticmethod
    def calculate(expert_results: List[ExpertResult]) -> ConsensusResult:
        """
        Calculate consensus between expert findings.

        Args:
            expert_results: List of expert analysis results

        Returns:
            ConsensusResult with score and categorized findings
        """
        if not expert_results:
            return ConsensusResult(score=0.0)

        # Extract all findings
        all_findings: List[Finding] = []
        for result in expert_results:
            all_findings.extend(result.findings)

        if not all_findings:
            return ConsensusResult(score=1.0)

        # Count findings by normalized key
        finding_counts: Dict[str, int] = {}
        finding_by_key: Dict[str, List[Finding]] = {}

        for finding in all_findings:
            # Normalize finding key
            _raw = f"{finding.severity}|{finding.issue}"
            key = hashlib.md5(_raw.encode()).hexdigest()
            finding_counts[key] = finding_counts.get(key, 0) + 1
            if key not in finding_by_key:
                finding_by_key[key] = []
            finding_by_key[key].append(finding)

        # Calculate consensus threshold (80% of experts, ceiling to avoid false consensus)
        threshold = math.ceil(len(expert_results) * QualityThresholds.CONSENSUS_PERCENTAGE / 100)

        # Categorize findings
        consensus_findings: List[Finding] = []
        disputed_findings: List[Finding] = []
        unique_findings: Dict[str, List[Finding]] = {}

        for key, count in finding_counts.items():
            if count >= threshold:
                # Consensus finding
                consensus_findings.append(finding_by_key[key][0])
            elif count > 1:
                # Disputed finding
                disputed_findings.append(finding_by_key[key][0])
            else:
                # Unique finding
                expert_name = finding_by_key[key][0].metadata.get("expert", "unknown")
                if expert_name not in unique_findings:
                    unique_findings[expert_name] = []
                unique_findings[expert_name].append(finding_by_key[key][0])

        # Calculate consensus score
        total_unique = len(finding_counts)
        consensus_count = sum(1 for c in finding_counts.values() if c >= threshold)

        score = consensus_count / total_unique if total_unique > 0 else 1.0

        return ConsensusResult(
            score=score,
            consensus_findings=consensus_findings,
            disputed_findings=disputed_findings,
            unique_findings=unique_findings,
        )


class ForcedFindingValidator:
    """Ensure that zero expert findings triggers deeper analysis."""

    @staticmethod
    def should_force_deep(expert_results: List[ExpertResult]) -> bool:
        """
        Return True if all non-errored experts returned zero findings.

        When all experts return nothing, we assume shallow analysis rather than
        a perfectly clean codebase. Force DEEP tier to re-examine.
        """
        successful = [r for r in expert_results if not r.error]
        if not successful:
            return False  # All errored — can't judge
        total_findings = sum(len(r.findings) for r in successful)
        return total_findings == 0


class ExpertRunner:
    """Runs expert analysis in parallel using pooled threads."""

    # Shared thread pool for all instances
    _executor: ClassVar[ThreadPoolExecutor] = ThreadPoolExecutor(max_workers=WorkerConstants.ORCHESTRATOR_MAX_WORKERS)

    def __init__(self, client: OllamaClient, task_config: TaskConfig, verbose: bool = False):
        self.client = client
        self.task_config = task_config
        self.verbose = verbose

    def run_parallel(self, content: str) -> List[ExpertResult]:
        """
        Run all experts in parallel using pooled threads.

        Args:
            content: Content to analyze

        Returns:
            List of expert results
        """
        import concurrent.futures

        results: List[ExpertResult] = []

        futures = {
            self._executor.submit(
                self._run_single_expert,
                expert_name,
                expert_prompt,
                content,
            ): expert_name
            for expert_name, expert_prompt in self.task_config.experts.items()
        }

        for future in concurrent.futures.as_completed(futures):
            expert_name = futures[future]
            try:
                result = future.result()
                results.append(result)
                if self.verbose:
                    logger.info(f"[{expert_name} Expert] completed")
            except Exception as e:
                logger.error(f"[{expert_name} Expert] failed: {e}")
                results.append(ExpertResult(
                    expert_name=expert_name,
                    expert_type=self.task_config.task_type,
                    error=str(e),
                ))

        return results

    def _run_single_expert(
        self,
        expert_name: str,
        expert_prompt: str,
        content: str,
    ) -> ExpertResult:
        """Run a single expert analysis."""
        prompt = f"""{expert_prompt}

Content to analyze:
```
{content}
```

Output your findings as structured JSON with:
- findings: array of issues found
- severity: severity rating
- recommendation: specific remediation step"""

        start_time = time.time()

        try:
            output = self.client.run_json(prompt)
            duration_ms = (time.time() - start_time) * 1000

            # Parse findings from JSON
            findings = []
            raw_findings = output.get("findings", [])
            if isinstance(raw_findings, list):
                for f in raw_findings:
                    if isinstance(f, dict):
                        findings.append(Finding.from_dict(f))

            return ExpertResult(
                expert_name=expert_name,
                expert_type=self.task_config.task_type,
                findings=findings,
                raw_output=json.dumps(output),
                duration_ms=duration_ms,
            )

        except Exception as e:
            return ExpertResult(
                expert_name=expert_name,
                expert_type=self.task_config.task_type,
                error=str(e),
            )

    @classmethod
    def shutdown(cls) -> None:
        """
        Shutdown the shared thread pool.

        Call this when done with all ExpertRunner instances to free resources.
        """
        cls._executor.shutdown(wait=True)

    @classmethod
    def _register_cleanup(cls) -> None:
        """Register atexit handler for automatic cleanup."""
        atexit.register(cls.shutdown)


# Register cleanup on module import
ExpertRunner._register_cleanup()


class Adjudicator:
    """Synthesizes final verdict from expert debates."""

    def __init__(self, client: OllamaClient, task_config: TaskConfig, verbose: bool = False):
        self.client = client
        self.task_config = task_config
        self.verbose = verbose

    def adjudicate(self, debate_results: List[ExpertResult]) -> Verdict:
        """
        Run adjudication phase.

        Args:
            debate_results: Results from debate phase

        Returns:
            Final verdict
        """
        all_findings = build_findings(debate_results)

        prompt = f"""You are a {self.task_config.task_type} Adjudicator.

{self.task_config.adjudicator_role}

Expert Debates:
{all_findings}

Output your ADJUDICATION as structured JSON with:
{self.task_config.output_format}"""

        output = self.client.run_json(prompt)

        return Verdict(
            task_type=self.task_config.task_type,
            consensus_score=0.0,  # Will be set by caller
            tier_used=Tier.STANDARD.value,
            raw_output=json.dumps(output),
        )

    def run_judge_evaluation(
        self,
        verdict1: Verdict,
        debate_results: List[ExpertResult],
    ) -> Verdict:
        """
        Run judge evaluation for DEEP tier.

        Args:
            verdict1: First verdict
            debate_results: Results from debate phase

        Returns:
            Final verdict with judge confidence
        """
        # Generate second adjudication with different focus
        all_findings = build_findings(debate_results)

        prompt2 = f"""You are a {self.task_config.task_type} Adjudicator with a focus on practical impact.

Expert Debates:
{all_findings}

Focus on real-world impact and provide actionable recommendations.

Output your ADJUDICATION as structured JSON with:
{self.task_config.output_format}"""

        output2 = self.client.run_json(prompt2)

        # Run judge to select best
        judge_prompt = f"""You are a neutral Judge evaluating multiple verdicts.

Evaluate each verdict on these criteria (score 0-100 each):

1. COMPLETENESS: All expert findings addressed (0-25)
2. CONSENSUS_ACCURACY: Consensus points correctly identified (0-25)
3. CONFLICT_RESOLUTION: Conflicts resolved with reasoning (0-25)
4. ACTIONABILITY: Clear, prioritized action items (0-25)

### Verdict 1:
{verdict1.raw_output}

### Verdict 2:
{json.dumps(output2)}

Output your evaluation as JSON:
{{
  "verdict_scores": [{{"verdict": 1, "total": 85, "dimensions": {{"completeness": 22, "consensus_accuracy": 21, "conflict_resolution": 20, "actionability": 22}}}}, ...],
  "selected_verdict": 1,
  "confidence": 90,
  "reasoning": "Brief explanation of selection"
}}"""

        judgment = self.client.run_json(judge_prompt)

        selected = judgment.get("selected_verdict", 1)
        confidence = judgment.get("confidence", 50)
        reasoning = judgment.get("reasoning", "")

        final_verdict = verdict1 if selected == 1 else Verdict(
            task_type=self.task_config.task_type,
            consensus_score=0.0,
            tier_used=Tier.DEEP.value,
            raw_output=json.dumps(output2),
        )

        final_verdict.judge_confidence = confidence
        final_verdict.judge_reasoning = reasoning

        return final_verdict


class DebatePhase:
    """Runs debate rounds between experts."""

    def __init__(self, client: OllamaClient, task_config: TaskConfig, verbose: bool = False):
        self.client = client
        self.task_config = task_config
        self.verbose = verbose

    def run(self, expert_results: List[ExpertResult]) -> List[ExpertResult]:
        """
        Run debate phase between experts.

        Args:
            expert_results: Results from initial expert analysis

        Returns:
            Updated results after debate
        """
        debate_results: List[ExpertResult] = []

        for result in expert_results:
            if result.error:
                continue

            # Build other findings string
            other_findings = build_findings(
                expert_results,
                exclude=result.expert_name,
            )

            prompt = f"""You are the {result.expert_name} Expert.

Your initial findings:
{result.raw_output}

Other experts' findings:
{other_findings}

Instructions:
1. Compare your findings with other experts
2. Identify duplicate or related issues
3. Validate ratings
4. Propose consolidated findings

Output your revised analysis as JSON."""

            try:
                output = self.client.run_json(prompt)

                # Parse new findings from debate output (not reusing old ones)
                new_findings = []
                raw_findings = output.get("findings", [])
                if isinstance(raw_findings, list):
                    for f in raw_findings:
                        if isinstance(f, dict):
                            new_findings.append(Finding.from_dict(f))

                # Fall back to original findings if debate produced none
                final_findings = new_findings if new_findings else result.findings

                debate_results.append(ExpertResult(
                    expert_name=result.expert_name,
                    expert_type=result.expert_type,
                    findings=final_findings,
                    raw_output=json.dumps(output),
                ))
            except Exception as e:
                logger.error(f"Debate failed for {result.expert_name}: {e}")
                debate_results.append(result)

        return debate_results


class DebateOrchestrator:
    """
    Coordinates multi-expert debate with adjudication.

    This is a thin orchestrator that delegates to specialized components:
    - ExpertRunner: Parallel expert execution
    - ConsensusCalculator: Consensus calculation
    - DebatePhase: Expert debate rounds
    - Adjudicator: Final verdict synthesis

    Flow:
    1. Run experts in parallel (ExpertRunner)
    2. Calculate consensus (ConsensusCalculator)
    3. Select tier based on consensus
    4. Run debate if needed (DebatePhase)
    5. Run adjudication (Adjudicator)
    6. Run judge if DEEP tier (Adjudicator)
    """

    def __init__(
        self,
        client: OllamaClient,
        task_config: TaskConfig,
        verbose: bool = False,
    ):
        """
        Initialize orchestrator.

        Args:
            client: OllamaClient instance
            task_config: Task configuration
            verbose: Enable verbose logging
        """
        self.client = client
        self.task_config = task_config
        self.verbose = verbose

        # Initialize components
        self.expert_runner = ExpertRunner(client, task_config, verbose)
        self.adjudicator = Adjudicator(client, task_config, verbose)
        self.debate_phase = DebatePhase(client, task_config, verbose)

    def analyze(self, content: str, tier: str = Tier.AUTO.value) -> Verdict:
        """
        Run complete multi-expert analysis.

        Args:
            content: Content to analyze
            tier: Quality tier (auto, fast, standard, deep)

        Returns:
            Final adjudicated verdict
        """
        try:
            # Phase 1: Run experts in parallel
            expert_results = self.expert_runner.run_parallel(content)

            # Phase 2: Calculate consensus
            consensus = ConsensusCalculator.calculate(expert_results)

            # Determine tier — force DEEP if all experts returned zero findings (AUTO mode only)
            if tier == Tier.AUTO.value and ForcedFindingValidator.should_force_deep(expert_results):
                logger.warning("All experts returned 0 findings — forcing DEEP tier for deeper analysis")
                selected_tier = Tier.DEEP.value
            else:
                selected_tier = self._select_tier(tier, consensus)

            if self.verbose:
                logger.info(f"Consensus: {consensus.percentage:.0f}% → Tier: {selected_tier}")

            # FAST tier: Return consensus directly
            if selected_tier == Tier.FAST.value:
                return self._create_verdict_from_consensus(
                    consensus, selected_tier
                )

            # Phase 3: Run debate
            debate_results = self.debate_phase.run(expert_results)

            # Phase 4: Run adjudication
            verdict = self.adjudicator.adjudicate(debate_results)

            # Update tier_used to reflect selected tier
            verdict.tier_used = selected_tier

            # DEEP tier: Run judge evaluation
            if selected_tier == Tier.DEEP.value:
                verdict = self.adjudicator.run_judge_evaluation(verdict, debate_results)

            return verdict

        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise

    def _select_tier(
        self,
        requested_tier: str,
        consensus: ConsensusResult,
    ) -> str:
        """Select tier based on consensus and task type."""
        # If tier is explicitly set, use it
        if requested_tier != Tier.AUTO.value:
            return requested_tier

        # Critical tasks always use DEEP
        if self.task_config.always_deep:
            return Tier.DEEP.value

        # Use consensus-based selection (score is 0-1, percentage is 0-100)
        consensus_pct = consensus.percentage
        if consensus_pct >= CONSENSUS_THRESHOLD_FAST:
            return Tier.FAST.value
        elif consensus_pct >= CONSENSUS_THRESHOLD_STANDARD:
            return Tier.STANDARD.value
        else:
            return Tier.DEEP.value

    def _create_verdict_from_consensus(
        self,
        consensus: ConsensusResult,
        tier: str,
    ) -> Verdict:
        """Create verdict directly from consensus for FAST tier."""
        return Verdict(
            task_type=self.task_config.task_type,
            consensus_score=consensus.score,
            tier_used=tier,
            findings=consensus.consensus_findings,
        )