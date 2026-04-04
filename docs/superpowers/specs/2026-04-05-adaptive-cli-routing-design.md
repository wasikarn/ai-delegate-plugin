# Adaptive CLI Routing Design

**Goal:** Make `ai-delegate` decisively route each task to the CLI best suited for it — "push the right man to the right job" — starting smart from run 1 and improving with every run.

**Signals:** Implicit (consensus_score stored per run) + Explicit (binary y/n user rating after each run)

**Override:** Automatic, with `--no-adaptive` flag to bypass.

**Three-phase intelligence:**

- **Phase 1 — Priors (runs 1+):** Start with known CLI strengths as pre-seeded weights. Decisive from the first run, no cold-start paralysis.
- **Phase 2 — Streak correction (runs 3+):** If a CLI wins or loses 3 consecutive times, flip routing immediately. Catches wrong priors in 3–5 runs.
- **Phase 3 — Win rate (runs 10+):** Long-run win rate delta ≥15pp triggers permanent routing decision.

**Health monitoring:** Before routing, check if CLI is actually usable (not just installed). Degraded CLIs are skipped automatically with fallback to next best.

---

## Section 1: Data Layer

### Schema Changes

```sql
-- Migration: add 2 nullable columns to existing analysis_runs table
ALTER TABLE analysis_runs ADD COLUMN cli_name TEXT;       -- "ollama","codex","claude","gemini"
ALTER TABLE analysis_runs ADD COLUMN user_rating INTEGER; -- NULL=unrated, 0=no, 1=yes

CREATE INDEX IF NOT EXISTS idx_cli_task ON analysis_runs (cli_name, task_type);

-- Precomputed aggregates — TABLE not VIEW (O(1) router lookup, incremental updates)
CREATE TABLE IF NOT EXISTS cli_performance (
    cli_name     TEXT NOT NULL,
    task_type    TEXT NOT NULL,
    run_count    INTEGER NOT NULL DEFAULT 0,
    win_count    INTEGER NOT NULL DEFAULT 0,   -- sum(user_rating = 1)
    loss_count   INTEGER NOT NULL DEFAULT 0,   -- sum(user_rating = 0)
    win_rate     REAL NOT NULL DEFAULT 0.0,    -- win_count / (win_count + loss_count)
    last_updated TEXT NOT NULL,
    PRIMARY KEY (cli_name, task_type)
);
```

### Pre-seeded Priors

`cli_performance` is seeded at `_init_db()` time with known CLI strengths — decisive from run 1:

```python
# In constants.py
CLI_PRIORS: Dict[str, Dict[str, float]] = {
    "codex":  {"architecture": 0.80, "refactor": 0.75, "migrate": 0.75},
    "claude": {"audit": 0.80, "analyze": 0.75, "review": 0.75},
    "ollama": {"audit": 0.70, "analyze": 0.70, "architecture": 0.65,
               "review": 0.70, "refactor": 0.65, "migrate": 0.65},
}
# Priors stored as virtual runs: win_rate=0.80 → win_count=8, loss_count=2, run_count=10
# Real runs dilute priors naturally as data accumulates
```

### Migration Notes

- `ALTER TABLE` adds NULLable columns — backward compatible, no data loss
- `cli_performance` seeded from `CLI_PRIORS` in `_init_db()` (single-process, SQLite write lock safe)
- `cli_performance` updates incrementally on each new run or rating — not recomputed from scratch

### New `AnalysisMemory` Methods

```python
def record_cli_run(self, run_id: int, cli_name: str) -> None:
    """Backfill cli_name into analysis_runs after a run completes."""

def store_rating(self, run_id: int, rating: int) -> None:
    """Store binary rating (0/1) and incrementally update cli_performance for affected
    (cli_name, task_type) using atomic SQL: UPDATE win_count = win_count + 1 (not full recompute).
    """

def get_cli_performance(self, task_type: str) -> List[Dict]:
    """Return all cli_performance rows for a task_type, ordered by win_rate DESC.
    Each dict has keys: cli_name (str), win_rate (float), win_count (int),
    loss_count (int), run_count (int), last_updated (str).
    """

def get_recent_cli_runs(self, task_type: str, limit: int = 3) -> List[str]:
    """Return cli_name of the last N runs for task_type (newest first).
    Used for streak detection in Phase 2.
    """
```

---

## Section 1b: CLI Health Monitoring

### Design

In-memory only — no SQLite. Health state is ephemeral: a CLI degraded last session may be healthy now. Persisting state would risk blacklisting healthy CLIs after restart.

```python
# In router.py — lives inside SmartRouter
class CliHealthMonitor:
    """In-memory CLI health tracker. Fresh per session, zero I/O on healthy runs."""

    _TTL: Dict[str, float] = {
        "rate_limit": 300.0,       # 5 min — temporary burst window
        "network":     60.0,       # 1 min — transient blip
        "auth":       float("inf"), # indefinite — needs user intervention
    }

    def __init__(self) -> None:
        self._degraded: Dict[CLIType, Tuple[float, str]] = {}
        # cli_type → (failed_at_timestamp, error_type)

    def mark_failed(self, cli: CLIType, error_type: str) -> None:
        """Mark CLI as degraded. error_type: 'rate_limit' | 'auth' | 'network'"""
        self._degraded[cli] = (time.monotonic(), error_type)

    def is_degraded(self, cli: CLIType) -> bool:
        """Returns True if CLI is within its TTL window."""
        if cli not in self._degraded:
            return False
        failed_at, error_type = self._degraded[cli]
        if time.monotonic() - failed_at > self._TTL[error_type]:
            del self._degraded[cli]
            return False
        return True

    def clear(self, cli: CLIType) -> None:
        """Manually clear degraded state (e.g., after user fixes auth)."""
        self._degraded.pop(cli, None)
```

### Error Classification

Errors caught in `client.py` are classified before marking degraded:

| HTTP / stderr pattern | error_type | TTL |
|----------------------|------------|-----|
| `429`, `rate limit`, `usage limit` | `rate_limit` | 5 min |
| `401`, `unauthorized`, `authentication` | `auth` | indefinite |
| `ECONNREFUSED`, `timeout`, `network` | `network` | 1 min |

### Routing Integration

Health check runs as **step 0** — before any adaptive logic:

```
── Step 0: Health gate (all phases, every run) ───────────────────────────────
0a. For each CLI in priority order: skip if health_monitor.is_degraded(cli)
0b. If auth-degraded CLI skipped → print warning once per session:
    "⚠ codex unavailable (auth error) — using ollama instead"
0c. If ALL CLIs degraded → raise RuntimeError with actionable message
```

Error callback from `client.py` → `health_monitor.mark_failed(cli, error_type)` → next run skips automatically.

### Constants

```python
class HealthConfig:
    RATE_LIMIT_TTL = 300   # seconds
    NETWORK_TTL    = 60    # seconds
    AUTH_TTL       = -1    # sentinel: indefinite (float("inf") in code)
```

---

## Section 2: Adaptive Routing Logic

### Three-Phase Algorithm

```
── Step 0: Health gate — skip degraded CLIs (see Section 1b) ─────────────────

── Phase 1: Priors (always active, runs 1+) ──────────────────────────────────
1. Query cli_performance (includes pre-seeded priors) for task_type
2. Filter: available CLIs only
3. Sort: win_rate DESC, CLIPriority ASC as tiebreaker → current_best

── Phase 2: Streak correction (runs 3+) ──────────────────────────────────────
4. Get last 3 cli_names for task_type via get_recent_cli_runs()
5. If all 3 are the same CLI (winning streak): lock that CLI → return immediately
6. If current_best lost last 3 runs (losing streak): skip current_best,
   use next available CLI in sort order → fast correction of wrong prior

── Phase 3: Win rate override (runs 10+, rated runs only) ────────────────────
7. If current_best.run_count ≥ 10 AND
   current_best.win_rate - static_cli.win_rate ≥ 0.15:
   → permanent override (logged when --verbose)
   where static_cli = CLI selected by _task_priority_map without adaptation

── Anti-thrash guard (all phases) ────────────────────────────────────────────
8. If last 3 runs used ≥ 3 distinct CLIs → hold static_cli (oscillation detected)
```

### Constants

```python
class AdaptiveConfig:
    STREAK_WINDOW               = 3     # consecutive runs to trigger streak
    MIN_RUNS_BEFORE_OVERRIDE    = 10    # Phase 3 gate (rated runs only)
    WIN_RATE_DELTA_THRESHOLD    = 0.15  # 15 percentage points
    ANTI_THRASH_WINDOW          = 3     # look-back window
    ANTI_THRASH_DISTINCT_LIMIT  = 3     # distinct CLIs = thrashing
```

### Notes

- `consensus_score` does NOT factor into routing — it measures analysis quality, not CLI fitness
- `--no-adaptive` flag bypasses all phases, uses static priority map only
- Logic lives in `SmartRouter.select_cli_for_task()` — no new class needed
- Phase 2 streak uses `get_recent_cli_runs()` — O(1) indexed query on `analysis_runs`

---

## Section 3: User Rating Interface

### 3a. Inline Prompt (after every analysis)

```
✓ Analysis complete — ollama glm-5:cloud — consensus 0.82

Was this result useful? (y/n, Enter to skip): _
```

- Waits indefinitely (no timeout) — user presses Enter to skip
- `EOFError` → silent skip (CI/pipe safe, no flag needed)
- `--no-rating` flag disables prompt entirely (for scripts)

### 3b. Retroactive Rating Subcommand

```bash
ai-delegate rate --last y     # rate the most recent run
ai-delegate rate --last n     # downvote most recent run
```

- `--last` resolves to the highest `id` in `analysis_runs`
- Validate: only `y` or `n` accepted
- After storing: recompute `cli_performance` immediately
- Print confirmation: `"✓ Rating saved (ollama / audit: 7 wins, 3 losses)"`

### 3c. Routing Change Feedback

Only shown when `--verbose` is passed:

```
[adaptive] audit → codex (was ollama) — codex: 78% win rate vs ollama: 51% (12 runs)
```

---

## File Map

| File | Change |
|------|--------|
| `ai_delegate/memory.py` | Add `cli_performance` table, `record_cli_run()`, `store_rating()`, `get_cli_performance()` |
| `ai_delegate/router.py` | Update `select_cli_for_task()` with adaptive override logic + add `CliHealthMonitor` class |
| `ai_delegate/constants.py` | Add `AdaptiveConfig`, `HealthConfig` classes + `CLI_PRIORS` dict |
| `ai_delegate/cli.py` | Add inline rating prompt + `rate` subcommand |
| `tests/test_memory.py` | Tests for new memory methods |
| `ai_delegate/client.py` | Classify errors → call `health_monitor.mark_failed()` on auth/rate-limit/network errors |
| `tests/test_router.py` | Tests for adaptive override logic + health monitor TTL/fallback |
| `tests/test_cli.py` | Tests for rating prompt + subcommand |
