"""
CLI interface for AI Delegation Framework.

Supports multiple backends: ollama, gemini, codex.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .client import OllamaClient
from .debate.orchestrator import DebateOrchestrator
from .models import TaskConfig, Tier
from .config import (
    TASK_DISPLAY_NAMES,
    TASK_EXPERT_DESCRIPTIONS,
    DEFAULT_MODELS,
)
from .validation import validate_file_path
from .constants import (
    OLLAMA_MODELS,
    GEMINI_MODELS,
    CODEX_MODELS,
    CLAUDE_MODELS,
)


def _format_model_display(model: str) -> str:
    """Format model name with its CLI backend for display."""
    ollama_models = set(OLLAMA_MODELS.values())
    gemini_models = set(GEMINI_MODELS.values())
    codex_models = set(CODEX_MODELS.values())
    claude_models = set(CLAUDE_MODELS.values())

    if model in ollama_models:
        return f"ollama {model}"
    if model in gemini_models:
        return f"gemini {model}"
    if model in codex_models:
        return f"codex {model}"
    if model in claude_models:
        return f"claude {model}"
    return model


def create_task_config(task_type: str) -> TaskConfig:
    """Create task configuration from task type."""
    return TaskConfig.from_task_type(task_type)


def run_analysis(
    content: str,
    task_type: str,
    tier: str = Tier.AUTO.value,
    model: Optional[str] = None,
    verbose: bool = False,
    elicit: Optional[str] = None,
    mode: str = "solo",
) -> dict:
    """
    Run multi-expert analysis.

    Args:
        content: Content to analyze
        task_type: Type of analysis (audit, analyze, architecture, etc.)
        tier: Quality tier (auto, fast, standard, deep)
        model: Model to use (defaults to task-specific model)
        verbose: Enable verbose logging

    Returns:
        Verdict as dictionary
    """
    # Create task config
    config = create_task_config(task_type)

    # Load custom expert plugins
    from .plugin_registry import PluginRegistry
    registry = PluginRegistry()
    custom_experts = registry.for_task(task_type)
    for plugin in custom_experts:
        config.experts.update(plugin.to_expert_dict())
    if custom_experts and verbose:
        print(f"Loaded {len(custom_experts)} custom expert(s): {[p.name for p in custom_experts]}")

    # Override model if specified
    if model:
        config.default_model = model

    # Create client
    client = OllamaClient(
        model=config.default_model,
        verbose=verbose,
    )

    if mode == "party":
        from .party_mode import PartyDebate
        party = PartyDebate(client=client, task_config=config, verbose=verbose)
        verdict = party.run(content=content)
    else:
        # Create orchestrator
        orchestrator = DebateOrchestrator(
            client=client,
            task_config=config,
            verbose=verbose,
        )
        verdict = orchestrator.analyze(content, tier=tier, elicit=elicit)

    result = verdict.to_dict()

    # Store result in memory and check for regressions (non-critical, best effort)
    try:
        from .memory import AnalysisMemory, MemoryRecord
        findings = result.get("findings", [])
        record = MemoryRecord(
            file_path=f"<content:{task_type}>",
            task_type=task_type,
            consensus_score=result["consensus_score"],
            finding_count=len(findings),
            critical_count=sum(1 for f in findings if f.get("severity", "").lower() == "critical"),
            high_count=sum(1 for f in findings if f.get("severity", "").lower() == "high"),
            findings_summary="; ".join(f.get("issue", "")[:80] for f in findings[:10]),
        )
        memory = AnalysisMemory()
        regression = memory.detect_regression(record)
        memory.store(record)
        result["regression"] = regression
    except Exception:
        pass  # Memory is non-critical

    return result


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="AI Delegation Framework - Multi-expert analysis with debate",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Task Types:
  audit        Security audit (OWASP, auth, input validation)
  analyze      Performance analysis (complexity, database, memory)
  architecture Architecture review (patterns, SOLID, scalability)
  refactor    Refactoring analysis (simplification, patterns)
  migrate      Migration analysis (API, dependencies, testing)

Quality Tiers:
  auto        Auto-select based on consensus (default)
  fast        Quick analysis, consensus only
  standard    Debate + adjudication
  deep        Full analysis with judge evaluation

Examples:
  # Security audit
  echo "user_input = request.GET['id']" | ai-delegate audit

  # Performance analysis with deep tier
  cat my_code.py | ai-delegate analyze --tier deep

  # Architecture review from file
  ai-delegate architecture --file ./src/architecture.md

  # Use specific model
  ai-delegate audit --model glm-5:cloud
        """,
    )

    parser.add_argument(
        "--version", "-V",
        action="version",
        version="%(prog)s 0.3.0",
    )
    parser.add_argument(
        "task_type",
        choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"],
        help="Type of analysis to perform",
    )
    parser.add_argument(
        "--tier",
        choices=[Tier.AUTO.value, Tier.FAST.value, Tier.STANDARD.value, Tier.DEEP.value],
        default=Tier.AUTO.value,
        help="Quality tier (default: auto)",
    )
    parser.add_argument(
        "--model",
        help="Model to use (default: task-specific)",
    )
    parser.add_argument(
        "--file", "-f",
        type=Path,
        help="Read content from file instead of stdin",
    )
    parser.add_argument(
        "--output", "-o",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "adr", "risk-matrix", "playbook", "perf-profile"],
        default=None,
        help="Structured output format (overrides --output)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--elicit",
        choices=["pre-mortem", "first-principles", "inversion", "red-team", "constraint-removal", "all"],
        help="Apply BMAD elicitation lens after initial analysis for deeper findings",
    )
    parser.add_argument(
        "--mode",
        choices=["solo", "party"],
        default="solo",
        help="Debate mode: solo (parallel+consensus) or party (multi-turn adversarial)",
    )
    parser.add_argument(
        "--checkpoint",
        action="store_true",
        help="Output findings organized by severity (human-readable checkpoint review)",
    )
    parser.add_argument(
        "--flow",
        choices=["quick", "standard", "bmad", "enterprise"],
        default=None,
        help="Workflow mode preset (overrides --tier and --elicit)",
    )
    parser.add_argument(
        "--show-cost",
        action="store_true",
        help="Show estimated token usage and cost after analysis",
    )

    args = parser.parse_args()

    # Get content
    if args.file:
        # Validate file path for security
        validation_result = validate_file_path(args.file)
        if not validation_result.valid:
            print(f"Error: {validation_result.error}", file=sys.stderr)
            sys.exit(1)
        content = args.file.read_text()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Error: No input provided. Use --file or pipe content.", file=sys.stderr)
            sys.exit(1)
        content = sys.stdin.read()

    if not content.strip():
        print("Error: Empty content provided.", file=sys.stderr)
        sys.exit(1)

    # Display task info
    if args.verbose:
        task_name = TASK_DISPLAY_NAMES.get(args.task_type, args.task_type.upper())
        task_desc = TASK_EXPERT_DESCRIPTIONS.get(args.task_type, "")
        print(f"Task: {task_name}")
        print(f"Description: {task_desc}")
        print(f"Tier: {args.tier}")
        print(f"Model: {args.model or DEFAULT_MODELS.get(args.task_type, 'default')}")
        print("---")

    # Apply flow preset (overrides --tier and --elicit)
    tier = args.tier
    elicit = args.elicit
    if args.flow:
        from .flow_config import FlowConfig
        flow = FlowConfig.from_mode(args.flow)
        tier = flow.tier
        elicit = flow.elicit

    # Always show which model/CLI will be used
    from .constants import FALLBACK_MODEL
    effective_model = args.model or DEFAULT_MODELS.get(args.task_type, FALLBACK_MODEL)
    print(f"Using: {_format_model_display(effective_model)}")

    # Run analysis
    try:
        result = run_analysis(
            content=content,
            task_type=args.task_type,
            tier=tier,
            model=args.model,
            verbose=args.verbose,
            elicit=elicit,
            mode=args.mode,
        )

        if args.format:
            from .output_formatter import OutputFormatter
            from .models import Verdict, Finding as FindingModel
            findings = [FindingModel.from_dict(f) for f in result.get("findings", [])]
            verdict_obj = Verdict(
                task_type=result["task_type"],
                consensus_score=result["consensus_score"],
                tier_used=result["tier_used"],
                findings=findings,
                recommendations=result.get("recommendations", []),
                action_items=result.get("action_items", []),
            )
            print(OutputFormatter().format(verdict_obj, fmt=args.format))
        elif args.checkpoint:
            from .checkpoint import CheckpointPresenter
            from .models import Verdict, Finding as FindingModel
            findings = [FindingModel.from_dict(f) for f in result.get("findings", [])]
            verdict_obj = Verdict(
                task_type=result["task_type"],
                consensus_score=result["consensus_score"],
                tier_used=result["tier_used"],
                findings=findings,
                recommendations=result.get("recommendations", []),
                action_items=result.get("action_items", []),
            )
            print(CheckpointPresenter().format(verdict_obj))
        elif args.output == "json":
            print(json.dumps(result, indent=2))
        else:
            # Text output
            print(f"Task: {result['task_type']}")
            print(f"Tier: {result['tier_used']}")
            print(f"Consensus: {result['consensus_score']:.0%}")
            if result.get('findings'):
                print("\nFindings:")
                for finding in result['findings']:
                    print(f"  [{finding['severity']}] {finding['issue']}")
            if result.get('recommendations'):
                print("\nRecommendations:")
                for rec in result['recommendations']:
                    print(f"  - {rec}")

        regression = result.get("regression")
        if regression and regression.get("new_findings", 0) > 0:
            print(
                f"\nREGRESSION: +{regression['new_findings']} new findings "
                f"(+{regression['new_critical']} critical) vs last run",
                file=sys.stderr,
            )

        if args.show_cost:
            from .cost_tracker import CostTracker
            tracker = CostTracker()
            # Use content length to estimate costs per expert in result
            model = args.model or "glm-5:cloud"
            for finding in result.get("findings", []):
                expert = finding.get("metadata", {}).get("expert", "expert") if isinstance(finding, dict) else "expert"
                usage = tracker.estimate_from_content(content, model=model, expert_name=expert)
                tracker.record(usage)
            if not result.get("findings"):
                usage = tracker.estimate_from_content(content, model=model)
                tracker.record(usage)
            print("\n" + tracker.report().format_summary())

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()