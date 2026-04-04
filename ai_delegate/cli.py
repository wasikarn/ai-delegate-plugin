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

    return verdict.to_dict()


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
        version="%(prog)s 0.0.2",
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

    # Run analysis
    try:
        result = run_analysis(
            content=content,
            task_type=args.task_type,
            tier=args.tier,
            model=args.model,
            verbose=args.verbose,
            elicit=args.elicit,
            mode=args.mode,
        )

        if args.output == "json":
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

    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()