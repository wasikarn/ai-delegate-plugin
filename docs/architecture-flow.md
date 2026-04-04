# Architecture Flow

Claude Code as main orchestrator with ai-delegate-plugin as enhancement layer.

## Flow Diagram

```
User
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│                      Claude Code                              │
│                   (Main Orchestrator)                         │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    Plugins                            │   │
│  │  ┌─────────────────────────────────────────────┐    │   │
│  │  │         ai-delegate-plugin                  │    │   │
│  │  │                                              │    │   │
│  │  │  Skills:                                     │    │   │
│  │  │  - ai-delegate (auto-trigger on keywords)   │    │   │
│  │  │                                              │    │   │
│  │  │  Agents:                                     │    │   │
│  │  │  - security-expert                          │    │   │
│  │  │  - performance-expert                       │    │   │
│  │  │  - architecture-expert                       │    │   │
│  │  │                                              │    │   │
│  │  │  Hooks:                                      │    │   │
│  │  │  - SessionStart → auto-install               │    │   │
│  │  │  - UserPromptSubmit → keyword detection      │    │   │
│  │  │  - SubagentStart → context injection         │    │   │
│  │  │  - etc.                                      │    │   │
│  │  └─────────────────────────────────────────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
  │
  │ (when user says: "audit this file" or "security review")
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│                ai-delegate (Python Package)                  │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              Smart Router                             │   │
│  │                                                       │   │
│  │  Detects: ollama ✓ | gemini ✗ | codex ✗ | claude ✓  │   │
│  │                                                       │   │
│  │  Selects: Ollama/glm-5:cloud for "audit"             │   │
│  └──────────────────────────────────────────────────────┘   │
  │
  ▼
┌─────────────────────────────────────────────────────────────┐
│                    Ollama CLI                                │
│                  (External AI Service)                        │
│                                                              │
│  $ ollama run glm-5:cloud --format json "..."               │
└─────────────────────────────────────────────────────────────┘
```

## Component Roles

| Component | Role | Responsibility |
|-----------|------|----------------|
| **User** | Initiator | Sends requests to Claude Code |
| **Claude Code** | Main Orchestrator | Conversation, decides when to invoke plugins |
| **ai-delegate-plugin** | Enhancement Layer | Skills, Agents, Hooks for code analysis |
| **Python Package** | Implementation | Smart Router, Debate Orchestrator, Experts |
| **Ollama/Gemini/Codex** | External AI | Delegated analysis tasks |

## Trigger Flow

### 1. User Request

```
User: "ช่วย audit ไฟล์นี้หน่อย src/auth.py"
```

### 2. Hook Detection (UserPromptSubmit)

```bash
# hooks/detect-analysis-task.sh
# Detects: "audit", "security", "vulnerability"
# Suggests: "ai-delegate audit --file <path>"
```

### 3. Claude Code Decision

Claude Code recognizes the task and invokes:

- Skill: `ai-delegate`
- Or Agent: `security-expert`

### 4. Python Package Execution

```python
# Smart Router selects CLI and model
router = SmartRouter()
cli_type, model = router.select_cli_for_task("audit")
# Returns: (CLIType.OLLAMA, "glm-5:cloud")
```

### 5. External AI Call

```bash
ollama run glm-5:cloud --format json "Analyze for security..."
```

### 6. Debate Process

```
ExpertRunner (parallel)
    │
    ├── OWASP Expert ─────┐
    ├── Auth Expert ──────┼──► DebatePhase
    └── Input Expert ─────┘        │
                                   ▼
                            Adjudicator
                                   │
                                   ▼
                            Consensus + Verdict
```

### 7. Result Return

```
Claude Code receives findings → Presents to user
```

## Hook Events

| Event | When | Action |
|-------|------|--------|
| `SessionStart` | Session begins | Auto-install Python package |
| `UserPromptSubmit` | User sends prompt | Detect analysis keywords |
| `PreToolUse/Bash` | Before Bash command | Validate ai-delegate commands |
| `PostToolUse/Write` | After file edit | Auto-audit sensitive files |
| `SubagentStart` | Expert spawns | Inject domain context |
| `SubagentStop` | Expert finishes | Validate output format |
| `Stop` | Claude finishes | Generate summary |

## Agent Orchestration

```
Claude Code
    │
    ├─► Spawns Agent (security-expert)
    │       │
    │       ├─► Hook: SubagentStart → inject context
    │       │
    │       └─► Analyzes code
    │               │
    │               └─► Hook: SubagentStop → validate output
    │
    └─► Receives findings from all experts
            │
            └─► Synthesizes final response to user
```

## Data Flow

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Claude    │────►│ ai-delegate │────►│   Ollama    │
│    Code     │     │   Plugin    │     │    CLI      │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                    │
       │                   │                    │
       ▼                   ▼                    ▼
  Conversation        Analysis           Expert Debates
    Context          Request              + Verdict
       │                   │                    │
       │                   │                    │
       └───────────────────┴────────────────────┘
                           │
                           ▼
                    Final Response
                    to User
```

## Fallback Chain

```
Primary: Ollama (glm-5:cloud, kimi-k2.5:cloud)
    │
    ├─► Not available? → Gemini CLI (gemini-2.0-flash)
    │                         │
    │                         ├─► Not available? → Codex CLI (o3-mini)
    │                         │                         │
    │                         │                         └─► Claude CLI (sonnet/opus)
    │                         │
    │                         └─► Fallback
    │
    └─► Rate limited? → Try next in chain
```

## Key Points

1. **Claude Code is always the entry point** - User interacts with Claude Code
2. **Plugin enhances capabilities** - ai-delegate adds domain expertise
3. **Smart Router optimizes** - Selects best available AI for task
4. **Hooks automate** - Detect keywords, inject context, validate output
5. **Agents parallelize** - Multiple experts analyze simultaneously
6. **External AIs do the heavy lifting** - Ollama/Gemini/Codex run analysis
