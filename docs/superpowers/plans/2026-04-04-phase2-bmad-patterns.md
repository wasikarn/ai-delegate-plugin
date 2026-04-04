# Phase 2: BMAD Debate Patterns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 5 BMAD-inspired features: Party Mode (multi-turn adversarial debate), Advanced Elicitation (5 reasoning lenses), Project Constitution (shared context injection), Agent Personas (named experts), and Checkpoint Preview (concern-organized output).

**Architecture:** All features are additive. Party Mode adds `--mode party|solo` flag and a new `PartyModeOrchestrator` class. Elicitation adds `--elicit` flag and `ElicitationEngine`. Project Constitution adds `ContextLoader` that injects `.ai-delegate/context.md` into all expert prompts. Agent Personas add metadata to expert configs. Checkpoint adds `--checkpoint` flag and `CheckpointPresenter`. Existing `DebateOrchestrator` untouched.

**Tech Stack:** Python 3.9+, pytest, argparse, dataclasses, pathlib

**Prerequisite:** Phase 1 must be complete (all bugs fixed).

---

## Task 1: Agent Personas — Named Expert Identities

**Files:**

- Modify: `ai_delegate/config.py` (add EXPERT_PERSONAS dict)
- Modify: `ai_delegate/debate/orchestrator.py` (ExpertRunner._run_single_expert uses persona)
- Modify: `ai_delegate/models.py` (ExpertResult adds persona_name field)
- Create: `tests/test_personas.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_personas.py
from unittest.mock import MagicMock
from ai_delegate.debate.orchestrator import ExpertRunner
from ai_delegate.models import TaskConfig
from ai_delegate.config import EXPERT_PERSONAS

class TestAgentPersonas:
    def test_expert_personas_defined_for_all_domains(self):
        """All expert domains must have persona entries."""
        required = ["OWASP", "AUTH", "INPUT", "COMPLEXITY", "DATABASE", "MEMORY",
                    "PATTERNS", "SOLID", "SCALABILITY"]
        for key in required:
            assert key in EXPERT_PERSONAS, f"Missing persona for {key}"

    def test_persona_has_required_fields(self):
        """Each persona must have name, title, and style fields."""
        for key, persona in EXPERT_PERSONAS.items():
            assert "name" in persona, f"{key} missing 'name'"
            assert "title" in persona, f"{key} missing 'title'"
            assert "style" in persona, f"{key} missing 'style'"

    def test_expert_result_includes_persona_name(self):
        """ExpertResult should carry persona_name from the runner."""
        client = MagicMock()
        client.run_json.return_value = {"findings": []}
        
        from ai_delegate.models import TaskConfig
        config = TaskConfig(
            task_type="audit",
            experts={"OWASP": "You are OWASP expert."},
            display_name="AUDIT",
            description="",
            adjudicator_role="",
            output_format="",
            default_model="glm-5:cloud",
        )
        runner = ExpertRunner(client=client, task_config=config)
        result = runner._run_single_expert("OWASP", "You are OWASP expert.", "code")
        
        assert result.persona_name is not None
        assert "Mary" in result.persona_name or result.persona_name != ""
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/test_personas.py -v
```

Expected: FAIL — EXPERT_PERSONAS doesn't exist yet.

- [ ] **Step 3: Add personas to config.py**

Add to `ai_delegate/config.py` after the EXPERT_CONFIGS dict:

```python
# =============================================================================
# Expert Personas — Named identities for each expert domain
# =============================================================================

EXPERT_PERSONAS: dict = {
    "OWASP": {
        "name": "Mary Chen",
        "title": "OWASP Security Analyst",
        "style": "Direct and evidence-based. Always cites vulnerability class and CVE when possible.",
    },
    "AUTH": {
        "name": "Alex Rivera",
        "title": "Auth & Crypto Specialist",
        "style": "Systematic. Traces authentication flows step by step before making claims.",
    },
    "INPUT": {
        "name": "Sam Park",
        "title": "Input Validation Expert",
        "style": "Skeptical. Assumes all input is malicious until proven otherwise.",
    },
    "COMPLEXITY": {
        "name": "Dana Lee",
        "title": "Algorithm Complexity Analyst",
        "style": "Quantitative. Always provides Big-O notation and concrete benchmarks.",
    },
    "DATABASE": {
        "name": "Jordan Kim",
        "title": "Database Performance Expert",
        "style": "Practical. Focuses on query execution plans and index strategies.",
    },
    "MEMORY": {
        "name": "Casey Walsh",
        "title": "Memory & Caching Specialist",
        "style": "Profiling-first. Doesn't speculate without measuring.",
    },
    "PATTERNS": {
        "name": "Winston Okafor",
        "title": "Design Patterns Architect",
        "style": "Principled. Applies GoF and modern patterns, explains trade-offs.",
    },
    "SOLID": {
        "name": "Priya Sharma",
        "title": "SOLID Principles Expert",
        "style": "Precise. Maps each violation to a specific principle with line numbers.",
    },
    "SCALABILITY": {
        "name": "Marcus Thompson",
        "title": "Scalability & Coupling Analyst",
        "style": "Systems-thinking. Considers failure modes at 10x and 100x load.",
    },
}
```

- [ ] **Step 4: Add persona_name to ExpertResult**

In `ai_delegate/models.py`, add field to `ExpertResult`:

```python
@dataclass
class ExpertResult:
    """Result from a single expert analysis."""
    expert_name: str
    expert_type: str
    findings: List[Finding] = field(default_factory=list)
    raw_output: Optional[str] = None
    _parsed_output: Optional[Dict[str, Any]] = field(default=None, repr=False)
    error: Optional[str] = None
    duration_ms: Optional[float] = None
    persona_name: Optional[str] = None  # NEW: "Mary Chen (OWASP Security Analyst)"
```

- [ ] **Step 5: Inject persona into ExpertRunner**

In `ai_delegate/debate/orchestrator.py`, modify `_run_single_expert` to include persona in prompt and result:

```python
def _run_single_expert(self, expert_name: str, expert_prompt: str, content: str) -> ExpertResult:
    """Run a single expert analysis with persona identity."""
    from ..config import EXPERT_PERSONAS
    
    # Look up persona (expert_name is uppercase key like "OWASP")
    persona = EXPERT_PERSONAS.get(expert_name.upper(), {})
    persona_intro = ""
    persona_name = None
    if persona:
        persona_name = f"{persona['name']} ({persona['title']})"
        persona_intro = (
            f"You are {persona['name']}, {persona['title']}.\n"
            f"Your style: {persona['style']}\n\n"
        )

    prompt = f"""{persona_intro}{expert_prompt}

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
            persona_name=persona_name,
        )
    except Exception as e:
        return ExpertResult(
            expert_name=expert_name,
            expert_type=self.task_config.task_type,
            error=str(e),
            persona_name=persona_name,
        )
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_personas.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS, no regressions.

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/config.py ai_delegate/models.py ai_delegate/debate/orchestrator.py tests/test_personas.py
git commit -m "feat(personas): add named expert identities (Mary, Alex, Dana, Winston, etc.) injected into prompts"
```

---

## Task 2: Project Constitution — Shared Context Injection

**Files:**

- Create: `ai_delegate/context_loader.py`
- Modify: `ai_delegate/debate/orchestrator.py` (ExpertRunner uses context)
- Modify: `ai_delegate/cli.py` (pass context to orchestrator)
- Create: `tests/test_context_loader.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_context_loader.py
import tempfile
from pathlib import Path
from unittest.mock import patch
from ai_delegate.context_loader import ContextLoader

class TestContextLoader:
    def test_loads_context_from_ai_delegate_dir(self, tmp_path):
        """Loads .ai-delegate/context.md from cwd if present."""
        context_dir = tmp_path / ".ai-delegate"
        context_dir.mkdir()
        context_file = context_dir / "context.md"
        context_file.write_text("# Project: MyAPI\n- Use REST, not GraphQL\n- Python 3.11+")
        
        loader = ContextLoader(base_dir=tmp_path)
        context = loader.load()
        
        assert context is not None
        assert "Use REST, not GraphQL" in context

    def test_returns_none_when_no_context_file(self, tmp_path):
        """Returns None if no context file exists."""
        loader = ContextLoader(base_dir=tmp_path)
        assert loader.load() is None

    def test_formats_context_for_injection(self, tmp_path):
        """format_for_prompt() wraps context in a clear section."""
        context_dir = tmp_path / ".ai-delegate"
        context_dir.mkdir()
        (context_dir / "context.md").write_text("Use Python 3.11+")
        
        loader = ContextLoader(base_dir=tmp_path)
        formatted = loader.format_for_prompt()
        
        assert "PROJECT CONTEXT" in formatted
        assert "Use Python 3.11+" in formatted

    def test_format_for_prompt_empty_string_when_no_context(self, tmp_path):
        """Returns empty string (not None) when no context file."""
        loader = ContextLoader(base_dir=tmp_path)
        assert loader.format_for_prompt() == ""
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/test_context_loader.py -v
```

Expected: FAIL — `context_loader.py` doesn't exist.

- [ ] **Step 3: Create ContextLoader**

```python
# ai_delegate/context_loader.py
"""Load project constitution from .ai-delegate/context.md."""

from pathlib import Path
from typing import Optional


CONTEXT_PATHS = [
    ".ai-delegate/context.md",
    ".ai-delegate/CONTEXT.md",
    "ai-delegate-context.md",
]


class ContextLoader:
    """Load and format project constitution for expert prompts."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or Path.cwd()

    def load(self) -> Optional[str]:
        """Load context from first found context file, or None."""
        for relative_path in CONTEXT_PATHS:
            full_path = self.base_dir / relative_path
            if full_path.exists():
                return full_path.read_text(encoding="utf-8").strip()
        return None

    def format_for_prompt(self) -> str:
        """Return context formatted for injection into expert prompts.
        
        Returns empty string if no context file found.
        """
        context = self.load()
        if not context:
            return ""
        return f"""## PROJECT CONTEXT (Constitution)
The following constraints and decisions apply to this project.
All experts MUST respect these when making recommendations:

{context}

---
"""
```

- [ ] **Step 4: Inject context into ExpertRunner**

In `ai_delegate/debate/orchestrator.py`, modify `ExpertRunner.__init__` and `_run_single_expert`:

```python
class ExpertRunner:
    _executor: ClassVar[ThreadPoolExecutor] = ThreadPoolExecutor(
        max_workers=WorkerConstants.ORCHESTRATOR_MAX_WORKERS
    )

    def __init__(self, client: OllamaClient, task_config: TaskConfig, verbose: bool = False,
                 context_prefix: str = ""):
        self.client = client
        self.task_config = task_config
        self.verbose = verbose
        self.context_prefix = context_prefix  # NEW: project constitution

    def _run_single_expert(self, expert_name: str, expert_prompt: str, content: str) -> ExpertResult:
        from ..config import EXPERT_PERSONAS
        
        persona = EXPERT_PERSONAS.get(expert_name.upper(), {})
        persona_intro = ""
        persona_name = None
        if persona:
            persona_name = f"{persona['name']} ({persona['title']})"
            persona_intro = (
                f"You are {persona['name']}, {persona['title']}.\n"
                f"Your style: {persona['style']}\n\n"
            )

        prompt = f"""{persona_intro}{self.context_prefix}{expert_prompt}

Content to analyze:
```

{content}

```

Output your findings as structured JSON with:
- findings: array of issues found
- severity: severity rating
- recommendation: specific remediation step"""
        # ... rest of method unchanged
```

In `DebateOrchestrator.__init__`, load context:

```python
def __init__(self, client: OllamaClient, task_config: TaskConfig, verbose: bool = False):
    from ..context_loader import ContextLoader
    self.client = client
    self.task_config = task_config
    self.verbose = verbose
    
    # Load project constitution if available
    context_prefix = ContextLoader().format_for_prompt()
    
    self.expert_runner = ExpertRunner(client, task_config, verbose, context_prefix=context_prefix)
    self.adjudicator = Adjudicator(client, task_config, verbose)
    self.debate_phase = DebatePhase(client, task_config, verbose)
```

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_context_loader.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/context_loader.py ai_delegate/debate/orchestrator.py tests/test_context_loader.py
git commit -m "feat(context): add ContextLoader for project constitution injection — reads .ai-delegate/context.md into all expert prompts"
```

---

## Task 3: Advanced Elicitation — 5 Reasoning Lenses

**Files:**

- Create: `ai_delegate/elicitation.py`
- Modify: `ai_delegate/cli.py` (add `--elicit` flag)
- Modify: `ai_delegate/debate/orchestrator.py` (DebateOrchestrator.analyze accepts elicit param)
- Create: `tests/test_elicitation.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_elicitation.py
from unittest.mock import MagicMock
from ai_delegate.elicitation import ElicitationEngine, ElicitationMethod
from ai_delegate.models import Finding, ExpertResult

def make_results():
    return [
        ExpertResult(
            expert_name="OWASP",
            expert_type="audit",
            findings=[Finding(severity="high", issue="SQL injection on line 42")],
            raw_output='{"findings": [{"severity": "high", "issue": "SQL injection on line 42"}]}',
        )
    ]

class TestElicitationEngine:
    def test_all_methods_are_available(self):
        assert ElicitationMethod.PRE_MORTEM == "pre-mortem"
        assert ElicitationMethod.FIRST_PRINCIPLES == "first-principles"
        assert ElicitationMethod.INVERSION == "inversion"
        assert ElicitationMethod.RED_TEAM == "red-team"
        assert ElicitationMethod.CONSTRAINT_REMOVAL == "constraint-removal"

    def test_elicitation_calls_llm_with_method_prompt(self):
        """ElicitationEngine should call LLM with method-specific prompt."""
        client = MagicMock()
        client.run_json.return_value = {
            "elicitation_method": "pre-mortem",
            "new_risks": ["What if the parameterized query library has a bug?"],
            "refined_findings": [
                {"severity": "critical", "issue": "SQL injection — confirmed by pre-mortem analysis"}
            ]
        }
        
        engine = ElicitationEngine(client=client)
        result = engine.apply(
            method=ElicitationMethod.PRE_MORTEM,
            expert_results=make_results(),
            content="SELECT * FROM users WHERE id = " + "'" + "user_input" + "'",
        )
        
        assert client.run_json.called
        # Verify method name appears in prompt
        call_args = client.run_json.call_args[0][0]
        assert "pre-mortem" in call_args.lower() or "fail" in call_args.lower()
        assert result is not None

    def test_elicitation_returns_refined_expert_results(self):
        """ElicitationEngine returns updated ExpertResult list with new findings."""
        client = MagicMock()
        client.run_json.return_value = {
            "refined_findings": [
                {"severity": "critical", "issue": "SQL injection — critical after elicitation"},
                {"severity": "high", "issue": "New risk discovered via pre-mortem"},
            ]
        }
        
        engine = ElicitationEngine(client=client)
        refined = engine.apply(
            method=ElicitationMethod.PRE_MORTEM,
            expert_results=make_results(),
            content="some code",
        )
        
        all_findings = [f for r in refined for f in r.findings]
        assert len(all_findings) >= 1
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/test_elicitation.py -v
```

Expected: FAIL — `elicitation.py` doesn't exist.

- [ ] **Step 3: Create ElicitationEngine**

```python
# ai_delegate/elicitation.py
"""Advanced elicitation methods for deeper analysis (BMAD-inspired)."""

import json
import logging
from typing import List
from ai_delegate.models import ExpertResult, Finding

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
        
        # Collect all existing findings for context
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
            
            # Return as single synthetic expert result from elicitation
            from ai_delegate.models import ExpertResult
            elicitation_result = ExpertResult(
                expert_name=f"Elicitation:{method}",
                expert_type="elicitation",
                findings=refined_findings,
                raw_output=json.dumps(output),
                persona_name=f"Elicitation ({method})",
            )
            
            # Combine original results with elicitation result
            return list(expert_results) + [elicitation_result]
        
        except Exception as e:
            logger.error(f"Elicitation ({method}) failed: {e}")
            return expert_results
```

- [ ] **Step 4: Add --elicit flag to CLI**

In `ai_delegate/cli.py`, add after the `--tier` argument:

```python
parser.add_argument(
    "--elicit",
    choices=["pre-mortem", "first-principles", "inversion", "red-team", "constraint-removal", "all"],
    help="Apply advanced elicitation method after initial analysis (BMAD-inspired deepening)",
)
```

And update `run_analysis()` to accept and pass elicit:

```python
def run_analysis(
    content: str,
    task_type: str,
    tier: str = Tier.AUTO.value,
    model: Optional[str] = None,
    verbose: bool = False,
    elicit: Optional[str] = None,  # NEW
) -> dict:
    config = create_task_config(task_type)
    if model:
        config.default_model = model
    client = OllamaClient(model=config.default_model, verbose=verbose)
    orchestrator = DebateOrchestrator(client=client, task_config=config, verbose=verbose)
    verdict = orchestrator.analyze(content, tier=tier, elicit=elicit)  # pass elicit
    return verdict.to_dict()
```

And in `main()`:

```python
result = run_analysis(
    content=content,
    task_type=args.task_type,
    tier=args.tier,
    model=args.model,
    verbose=args.verbose,
    elicit=args.elicit,
)
```

- [ ] **Step 5: Integrate into DebateOrchestrator.analyze()**

In `ai_delegate/debate/orchestrator.py`, update `analyze()` signature and add elicitation step:

```python
def analyze(self, content: str, tier: str = Tier.AUTO.value, elicit: Optional[str] = None) -> Verdict:
    try:
        expert_results = self.expert_runner.run_parallel(content)
        
        # Apply elicitation BEFORE consensus calculation (deepens findings)
        if elicit:
            from ..elicitation import ElicitationEngine, ElicitationMethod
            engine = ElicitationEngine(client=self.client)
            methods = ElicitationMethod.ALL if elicit == "all" else [elicit]
            for method in methods:
                expert_results = engine.apply(method, expert_results, content)
        
        consensus = ConsensusCalculator.calculate(expert_results)
        
        if ForcedFindingValidator.should_force_deep(expert_results):
            selected_tier = Tier.DEEP.value
        else:
            selected_tier = self._select_tier(tier, consensus)
        
        # ... rest unchanged
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_elicitation.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add ai_delegate/elicitation.py ai_delegate/cli.py ai_delegate/debate/orchestrator.py tests/test_elicitation.py
git commit -m "feat(elicitation): add 5 BMAD reasoning lenses via --elicit flag (pre-mortem, inversion, red-team, first-principles, constraint-removal)"
```

---

## Task 4: Party Mode — Multi-Turn Adversarial Debate

**Files:**

- Create: `ai_delegate/party_mode.py`
- Modify: `ai_delegate/cli.py` (add `--mode` flag)
- Modify: `ai_delegate/debate/orchestrator.py` (DebateOrchestrator.analyze routes to party mode)
- Create: `tests/test_party_mode.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_party_mode.py
from unittest.mock import MagicMock, call
from ai_delegate.party_mode import PartyDebate
from ai_delegate.models import ExpertResult, Finding, TaskConfig

def make_config():
    return TaskConfig(
        task_type="audit",
        experts={"OWASP": "OWASP prompt", "AUTH": "AUTH prompt"},
        display_name="AUDIT",
        description="",
        adjudicator_role="Synthesize the debate into final findings.",
        output_format="findings array",
        default_model="glm-5:cloud",
    )

class TestPartyDebate:
    def test_experts_see_each_others_responses(self):
        """In party mode, each expert's round 2 prompt must include other experts' round 1 output."""
        client = MagicMock()
        round1_output = {"findings": [{"severity": "high", "issue": "SQL injection"}]}
        round2_output = {"response": "I agree with OWASP. Also noting timing attack risk."}
        client.run_json.side_effect = [
            round1_output,  # OWASP round 1
            round1_output,  # AUTH round 1
            round2_output,  # OWASP round 2 (sees AUTH's findings)
            round2_output,  # AUTH round 2 (sees OWASP's findings)
            {"findings": [{"severity": "high", "issue": "SQL injection"}]},  # adjudication
        ]
        
        party = PartyDebate(client=client, task_config=make_config())
        verdict = party.run(content="some vulnerable code")
        
        # Should have been called 5 times (2 experts × 2 rounds + 1 adjudication)
        assert client.run_json.call_count == 5

    def test_party_mode_produces_valid_verdict(self):
        """Party mode must return a Verdict object."""
        from ai_delegate.models import Verdict
        client = MagicMock()
        client.run_json.return_value = {
            "findings": [{"severity": "high", "issue": "SQL injection"}]
        }
        
        party = PartyDebate(client=client, task_config=make_config())
        verdict = party.run(content="SELECT * FROM users WHERE id = '" + "user_input'")
        
        assert isinstance(verdict, Verdict)
        assert verdict.task_type == "audit"
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/test_party_mode.py -v
```

Expected: FAIL — `party_mode.py` doesn't exist.

- [ ] **Step 3: Create PartyDebate**

```python
# ai_delegate/party_mode.py
"""Party Mode: multi-turn adversarial debate where experts challenge each other."""

import json
import logging
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor

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
        expert_names = list(self.task_config.experts.keys())
        
        # Round 1: All experts analyze independently
        round1_results = self._run_round1(content)
        if self.verbose:
            logger.info(f"[Party] Round 1 complete: {len(round1_results)} experts responded")
        
        # Round 2: Experts see each other's findings and respond
        round2_results = self._run_round2(round1_results)
        if self.verbose:
            logger.info(f"[Party] Round 2 complete: debate finished")
        
        # Adjudication: synthesize final verdict
        verdict = self._adjudicate(round1_results + round2_results)
        return verdict

    def _run_round1(self, content: str) -> List[ExpertResult]:
        """Run round 1: independent expert analysis."""
        results = []
        
        with ThreadPoolExecutor(max_workers=len(self.task_config.experts)) as executor:
            futures = {
                executor.submit(self._expert_round1, name, prompt, content): name
                for name, prompt in self.task_config.experts.items()
            }
            import concurrent.futures
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
            consensus_score=0.8,  # Party mode assumes productive debate
            tier_used=Tier.STANDARD.value,
            raw_output=json.dumps(output),
        )
```

- [ ] **Step 4: Add --mode flag to CLI**

In `ai_delegate/cli.py`, add:

```python
parser.add_argument(
    "--mode",
    choices=["solo", "party"],
    default="solo",
    help="Debate mode: solo (parallel, consensus) or party (multi-turn adversarial debate)",
)
```

Update `run_analysis()`:

```python
def run_analysis(
    content: str,
    task_type: str,
    tier: str = Tier.AUTO.value,
    model: Optional[str] = None,
    verbose: bool = False,
    elicit: Optional[str] = None,
    mode: str = "solo",  # NEW
) -> dict:
    config = create_task_config(task_type)
    if model:
        config.default_model = model
    client = OllamaClient(model=config.default_model, verbose=verbose)
    
    if mode == "party":
        from .party_mode import PartyDebate
        party = PartyDebate(client=client, task_config=config, verbose=verbose)
        verdict = party.run(content=content)
    else:
        orchestrator = DebateOrchestrator(client=client, task_config=config, verbose=verbose)
        verdict = orchestrator.analyze(content, tier=tier, elicit=elicit)
    
    return verdict.to_dict()
```

And pass `mode=args.mode` in `main()`.

- [ ] **Step 5: Run tests**

```bash
pytest tests/test_party_mode.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/party_mode.py ai_delegate/cli.py tests/test_party_mode.py
git commit -m "feat(party-mode): add --mode party for multi-turn adversarial debate where experts challenge each other's findings"
```

---

## Task 5: Checkpoint Preview — Concern-Organized Output

**Files:**

- Create: `ai_delegate/checkpoint.py`
- Modify: `ai_delegate/cli.py` (add `--checkpoint` flag)
- Create: `tests/test_checkpoint.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_checkpoint.py
from ai_delegate.checkpoint import CheckpointPresenter
from ai_delegate.models import Verdict, Finding

def make_verdict_with_findings():
    return Verdict(
        task_type="audit",
        consensus_score=0.85,
        tier_used="standard",
        findings=[
            Finding(severity="critical", issue="SQL injection on line 42", 
                   location="auth.py:42", recommendation="Use parameterized queries"),
            Finding(severity="high", issue="Hardcoded API key", 
                   location="config.py:7", recommendation="Use environment variables"),
            Finding(severity="medium", issue="Missing rate limiting",
                   location="api.py:100", recommendation="Add rate limiting middleware"),
            Finding(severity="low", issue="Missing input validation",
                   location="forms.py:55", recommendation="Validate all user inputs"),
        ],
        recommendations=["Fix SQL injection immediately", "Rotate API keys"],
        action_items=["1. Fix SQL injection", "2. Remove hardcoded keys"],
    )

class TestCheckpointPresenter:
    def test_groups_findings_by_severity(self):
        """Checkpoint must group findings by severity, not by expert."""
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)
        
        # Critical must appear before high, high before medium
        critical_pos = report.index("CRITICAL")
        high_pos = report.index("HIGH")
        medium_pos = report.index("MEDIUM")
        assert critical_pos < high_pos < medium_pos

    def test_shows_finding_count_per_severity(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)
        
        assert "1 finding" in report or "1)" in report  # 1 critical
        assert "SQL injection" in report

    def test_includes_action_items_section(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)
        
        assert "ACTION ITEMS" in report or "action" in report.lower()
        assert "Fix SQL injection" in report

    def test_shows_risk_summary_header(self):
        verdict = make_verdict_with_findings()
        presenter = CheckpointPresenter()
        report = presenter.format(verdict)
        
        assert "CHECKPOINT" in report or "SUMMARY" in report
        assert "audit" in report.lower()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/test_checkpoint.py -v
```

Expected: FAIL — `checkpoint.py` doesn't exist.

- [ ] **Step 3: Create CheckpointPresenter**

```python
# ai_delegate/checkpoint.py
"""Checkpoint Preview: present findings organized by concern/severity."""

from typing import List, Dict
from .models import Verdict, Finding


SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
SEVERITY_ICONS = {
    "critical": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "info": "⚪",
}


class CheckpointPresenter:
    """Format Verdict as human-readable checkpoint report organized by severity."""

    def format(self, verdict: Verdict) -> str:
        """Format verdict into concern-organized checkpoint report."""
        lines = []
        
        # Header
        lines.append(f"{'=' * 60}")
        lines.append(f"  CHECKPOINT REVIEW — {verdict.task_type.upper()}")
        lines.append(f"  Consensus: {verdict.consensus_score:.0%} | Tier: {verdict.tier_used.upper()}")
        lines.append(f"{'=' * 60}")
        lines.append("")
        
        # Group findings by severity
        by_severity: Dict[str, List[Finding]] = {}
        for finding in verdict.findings:
            sev = finding.severity.lower()
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(finding)
        
        if not verdict.findings:
            lines.append("  ✅ No findings — analysis returned clean results.")
            lines.append("  ⚠️  Consider running with --elicit red-team to verify.")
            lines.append("")
        else:
            # Print by severity order
            for severity in SEVERITY_ORDER:
                if severity not in by_severity:
                    continue
                findings = by_severity[severity]
                icon = SEVERITY_ICONS.get(severity, "•")
                lines.append(f"{icon} {severity.upper()} ({len(findings)} finding{'s' if len(findings) != 1 else ''})")
                lines.append(f"{'─' * 40}")
                for i, f in enumerate(findings, 1):
                    lines.append(f"  {i}. {f.issue}")
                    if f.location:
                        lines.append(f"     📍 {f.location}")
                    if f.recommendation:
                        lines.append(f"     💡 {f.recommendation}")
                lines.append("")
        
        # Recommendations
        if verdict.recommendations:
            lines.append("RECOMMENDATIONS")
            lines.append("─" * 40)
            for rec in verdict.recommendations:
                lines.append(f"  • {rec}")
            lines.append("")
        
        # Action Items
        if verdict.action_items:
            lines.append("ACTION ITEMS")
            lines.append("─" * 40)
            for item in verdict.action_items:
                lines.append(f"  {item}")
            lines.append("")
        
        lines.append("=" * 60)
        return "\n".join(lines)
```

- [ ] **Step 4: Add --checkpoint flag to CLI**

In `ai_delegate/cli.py`:

```python
parser.add_argument(
    "--checkpoint",
    action="store_true",
    help="Output findings organized by severity/concern (human-readable checkpoint review)",
)
```

In `main()`, after getting the result:

```python
if args.checkpoint:
    from .checkpoint import CheckpointPresenter
    from .models import Verdict, Finding
    # Reconstruct verdict for presentation
    findings = [Finding.from_dict(f) for f in result.get("findings", [])]
    verdict_obj = Verdict(
        task_type=result["task_type"],
        consensus_score=result["consensus_score"],
        tier_used=result["tier_used"],
        findings=findings,
        recommendations=result.get("recommendations", []),
        action_items=result.get("action_items", []),
    )
    presenter = CheckpointPresenter()
    print(presenter.format(verdict_obj))
elif args.output == "json":
    print(json.dumps(result, indent=2))
else:
    # existing text output
    ...
```

- [ ] **Step 5: Run all tests**

```bash
pytest tests/test_checkpoint.py tests/ -v --tb=short 2>&1 | tail -20
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add ai_delegate/checkpoint.py ai_delegate/cli.py tests/test_checkpoint.py
git commit -m "feat(checkpoint): add --checkpoint flag for concern-organized severity-grouped output (BMAD Checkpoint Preview)"
```

---

## Task 6: Final Integration & Tag

- [ ] **Step 1: Run complete test suite**

```bash
pytest tests/ -v --cov=ai_delegate --cov-report=term-missing 2>&1 | tail -30
```

Expected: 370+ tests pass, coverage ≥ 97%.

- [ ] **Step 2: Smoke test new features**

```bash
echo "def login(user, pwd): return db.query(f'SELECT * FROM users WHERE u={user}')" | \
  python -m ai_delegate audit --checkpoint
```

Expected: Checkpoint report with CRITICAL SQL injection finding.

```bash
echo "some_code = 'test'" | python -m ai_delegate analyze --elicit pre-mortem --tier fast
```

Expected: JSON output with elicitation results.

- [ ] **Step 3: Update version and tag**

In `ai_delegate/__init__.py`, change version to `"0.1.0"`.
In `ai_delegate/cli.py`, change `version="%(prog)s 0.0.2"` to `"%(prog)s 0.1.0"`.

```bash
git add ai_delegate/__init__.py ai_delegate/cli.py
git commit -m "chore: bump version to 0.1.0 — Phase 2 BMAD patterns complete"
git tag v0.1.0
```
