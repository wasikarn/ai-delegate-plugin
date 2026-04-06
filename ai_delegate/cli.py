"""
CLI interface for AI Delegation Framework.

Supports multiple backends: ollama (default), claude (fallback).
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from .client import BackendClient
from .debate.orchestrator import DebateOrchestrator
from .memory import AnalysisMemory
from .models import TaskConfig, Tier
from .config import (
    TASK_DISPLAY_NAMES,
    TASK_EXPERT_DESCRIPTIONS,
    DEFAULT_MODELS,
)
from .validation import validate_file_path
from .constants import (
    OLLAMA_MODELS,
    CLAUDE_MODELS,
)

# Reverse-lookup: model name → CLI prefix (built once at import time)
_MODEL_CLI_MAP = {
    **{m: "ollama" for m in OLLAMA_MODELS.values()},
    **{m: "claude" for m in CLAUDE_MODELS.values()},
}


def _format_model_display(model: str) -> str:
    cli = _MODEL_CLI_MAP.get(model)
    return f"{cli} {model}" if cli else model


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
    no_adaptive: bool = False,
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

    # Initialize memory for regression detection and adaptive routing
    memory = None
    try:
        memory = AnalysisMemory()
    except Exception:
        pass  # Memory is non-critical

    # Select model directly from constants (ModelAssigner handles per-expert routing)
    from .constants import FALLBACK_MODEL, DEFAULT_MODELS as _DEFAULT_MODELS, _cli_for_model
    effective_model = model or _DEFAULT_MODELS.get(task_type, FALLBACK_MODEL)
    cli_name = _cli_for_model(effective_model)
    if verbose:
        print(f"CLI: {cli_name} | Model: {effective_model}")

    # Create client
    client = BackendClient(
        model=effective_model,
        verbose=verbose,
        cli_type=cli_name,
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
        from .memory import MemoryRecord
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
        if memory is None:
            memory = AnalysisMemory()
        regression = memory.detect_regression(record)
        run_id = memory.store(record)
        memory.record_cli_run(run_id, cli_name)
        memory.store_findings(
            analysis_run_id=run_id,
            task_type=task_type,
            findings=findings,
        )
        result["regression"] = regression
        result["_run_id"] = run_id
        result["_cli_name"] = cli_name
    except Exception:
        pass  # Memory is non-critical

    return result


def _handle_rate_subcommand(args: list) -> None:
    """Handle 'ai-delegate rate --last y|n' subcommand."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate rate")
    parser.add_argument("--last", choices=["y", "n"], required=True,
                        help="Rate the most recent run (y=useful, n=not useful)")
    parsed = parser.parse_args(args)

    memory = AnalysisMemory()
    with memory._connect() as conn:
        row = conn.execute(
            "SELECT id, cli_name, task_type FROM analysis_runs ORDER BY id DESC LIMIT 1"
        ).fetchone()

    if not row:
        print("No runs to rate.", file=sys.stderr)
        sys.exit(1)

    run_id, cli_name, task_type = row
    rating = 1 if parsed.last == "y" else 0
    memory.store_rating(run_id, rating)

    perf = memory.get_cli_performance(task_type or "")
    cli_perf = next((p for p in perf if p["cli_name"] == cli_name), None)
    if cli_perf:
        print(
            f"Rating saved ({cli_name} / {task_type}: "
            f"{cli_perf['win_count']} wins, {cli_perf['loss_count']} losses)"
        )
    else:
        print("Rating saved")
    sys.exit(0)


def _handle_search_subcommand(args: list) -> None:
    """Handle 'ai-delegate search <query>' subcommand."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate search", description="Search past findings in memory")
    parser.add_argument("query", help="Text to search for in past findings")
    parser.add_argument(
        "--task-type",
        choices=["audit", "analyze", "architecture", "refactor", "migrate", "review"],
        help="Filter by task type",
    )
    parser.add_argument(
        "--severity",
        choices=["critical", "high", "medium", "low", "info"],
        help="Filter by severity",
    )
    parser.add_argument("--limit", type=int, default=20, help="Max results (default: 20)")
    parsed = parser.parse_args(args)

    results = AnalysisMemory().search_findings(
        query=parsed.query,
        task_type=parsed.task_type,
        severity=parsed.severity,
        limit=parsed.limit,
    )
    if not results:
        print("No findings matched.")
    else:
        for r in results:
            print(f"[{r['severity'].upper()}] ({r['task_type']}) {r['issue_text']}")
    sys.exit(0)


def _handle_catalog_subcommand(args: list) -> None:
    """Handle 'ai-delegate catalog [--json] [--domain X] [--trust-all]'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate catalog")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--domain", help="Filter by domain")
    parser.add_argument("--trust-all", action="store_true")
    parsed = parser.parse_args(args)

    from .catalog import AgentCatalog
    catalog = AgentCatalog(trust_all=parsed.trust_all)
    agents = catalog.for_domains([parsed.domain]) if parsed.domain else catalog.scan()

    output = [
        {
            "name": a.name,
            "description": a.description,
            "source_plugin": a.source_plugin,
            "model": a.model,
            "tools": a.tools,
            "domains": a.domains,
        }
        for a in agents
    ]
    print(json.dumps(output, indent=2))
    sys.exit(0)


def _handle_assess_subcommand(args: list) -> None:
    """Handle 'ai-delegate assess --file path'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate assess")
    parser.add_argument("--file", required=True)
    parsed = parser.parse_args(args)

    file_path = Path(parsed.file)
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    from .complexity import ComplexityAssessor
    score = ComplexityAssessor.assess(file_path.read_text(), file_path.name)
    print(json.dumps({
        "level": score.level,
        "domains": score.domains,
        "file_count": score.file_count,
        "line_count": score.line_count,
        "security_signals": score.security_signals,
    }))
    sys.exit(0)


def _handle_consensus_subcommand(args: list) -> None:
    """Handle 'ai-delegate consensus --findings [...]'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate consensus")
    parser.add_argument("--findings", required=True)
    parsed = parser.parse_args(args)

    try:
        raw_findings = json.loads(parsed.findings)
    except json.JSONDecodeError as e:
        print(f"Error: invalid JSON in --findings: {e}", file=sys.stderr)
        sys.exit(1)

    from .models import ExpertResult, Finding
    from .consensus import ConsensusCalculator

    expert_map: dict = {}
    for raw in raw_findings:
        expert = raw.get("expert", "unknown")
        if expert not in expert_map:
            expert_map[expert] = []
        expert_map[expert].append(Finding(
            severity=raw.get("severity", "medium"),
            issue=raw.get("issue", ""),
            recommendation=raw.get("recommendation"),
            location=raw.get("location"),
        ))

    results = [
        ExpertResult(expert_name=name, expert_type="unknown", findings=findings)
        for name, findings in expert_map.items()
    ]

    if not results:
        print(json.dumps({"score": 0.0, "tier": "deep", "consensus_findings": [], "disputed_findings": []}))
        sys.exit(0)

    result = ConsensusCalculator.calculate(results)
    if result.score >= 0.90:
        tier = "fast"
    elif result.score >= 0.70:
        tier = "standard"
    else:
        tier = "deep"

    print(json.dumps({
        "score": result.score,
        "tier": tier,
        "consensus_findings": [f.to_dict() for f in result.consensus_findings],
        "disputed_findings": [f.to_dict() for f in result.disputed_findings],
    }))
    sys.exit(0)


def _handle_assign_subcommand(args: list) -> None:
    """Handle 'ai-delegate assign --agents X,Y --complexity low|medium|high'."""
    import argparse as _ap
    parser = _ap.ArgumentParser(prog="ai-delegate assign")
    parser.add_argument("--agents", required=True)
    parser.add_argument("--complexity", choices=["low", "medium", "high"], default="medium")
    parser.add_argument("--trust-all", action="store_true")
    parsed = parser.parse_args(args)

    agent_names = [n.strip() for n in parsed.agents.split(",") if n.strip()]

    from .catalog import AgentCatalog
    from .model_assigner import ModelAssigner
    from .complexity import ComplexityScore

    catalog = AgentCatalog(trust_all=parsed.trust_all)
    all_agents = {a.name: a for a in catalog.scan()}
    selected = [all_agents[n] for n in agent_names if n in all_agents]
    complexity = ComplexityScore(level=parsed.complexity)
    assignments = ModelAssigner.assign_all(selected, complexity)

    print(json.dumps([
        {
            "agent": a.agent.name,
            "path": a.path.value,
            "model": a.model,
            "source_plugin": a.agent.source_plugin,
            "tools": a.agent.tools,
        }
        for a in assignments
    ]))
    sys.exit(0)


def _handle_memory_check_subcommand(args: list) -> None:
    """Handle 'ai-delegate memory check --content-hash H --experts X,Y --task T'."""
    import argparse as _ap
    import time
    parser = _ap.ArgumentParser(prog="ai-delegate memory check")
    parser.add_argument("--content-hash", required=True)
    parser.add_argument("--experts", default="")
    parser.add_argument("--task", default="")
    parsed = parser.parse_args(args)

    expert_names = [n.strip() for n in parsed.experts.split(",") if n.strip()]

    try:
        from .memory import AnalysisMemory
        memory = AnalysisMemory()
        entry = memory.check_cache(
            content_hash=parsed.content_hash,
            task_description=parsed.task,
            expert_names=expert_names,
        )
        if entry is None:
            print(json.dumps({"hit": False}))
        else:
            age_hours = (time.time() - entry.cached_at) / 3600
            print(json.dumps({
                "hit": True,
                "score": entry.consensus.score,
                "age_hours": round(age_hours, 2),
            }))
    except Exception:
        print(json.dumps({"hit": False}))
    sys.exit(0)


def main():
    """Main CLI entry point."""
    # Handle pre-parser subcommands (avoids positional arg conflict with task_type)
    if sys.argv[1:2] == ["rate"]:
        _handle_rate_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["search"]:
        _handle_search_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["catalog"]:
        _handle_catalog_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["assess"]:
        _handle_assess_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["consensus"]:
        _handle_consensus_subcommand(sys.argv[2:])
        return
    if sys.argv[1:2] == ["assign"]:
        _handle_assign_subcommand(sys.argv[2:])
        return
    if sys.argv[1:3] == ["memory", "check"]:
        _handle_memory_check_subcommand(sys.argv[3:])
        return

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
    parser.add_argument(
        "--no-adaptive",
        action="store_true",
        help="Disable adaptive CLI routing (use static priority map)",
    )
    parser.add_argument(
        "--no-rating",
        action="store_true",
        help="Disable inline rating prompt after analysis",
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
            no_adaptive=args.no_adaptive,
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

        # Inline rating prompt (skipped in --no-rating mode and CI/pipe)
        run_id = result.get("_run_id")
        if run_id and not args.no_rating:
            try:
                rating_input = input(
                    "Was this result useful? (y/n, Enter to skip): "
                ).strip().lower()
                if rating_input in ("y", "n"):
                    AnalysisMemory().store_rating(run_id, 1 if rating_input == "y" else 0)
            except EOFError:
                pass  # CI/pipe safe — silent skip

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