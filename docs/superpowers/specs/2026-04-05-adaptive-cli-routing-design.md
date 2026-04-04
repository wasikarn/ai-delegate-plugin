# Adaptive CLI Routing Design

**Goal:** Make `ai-delegate` learn which CLI (ollama/codex/claude/gemini) performs best per task type and automatically adjust routing based on historical win rates.

**Signals:** Implicit (consensus_score stored per run) + Explicit (binary y/n user rating after each run)

**Override:** Automatic, with `--no-adaptive` flag to bypass.

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

### Migration Notes

- `ALTER TABLE` adds NULLable columns — backward compatible, no data loss
- `cli_performance` seeds from existing `analysis_runs` on first run via `_init_db()` ETL pass (single-process, no concurrency risk — SQLite write lock handles it)
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
```

---

## Section 2: Adaptive Routing Logic

### Algorithm (5 steps)

```
1. Query cli_performance for task_type
2. Filter: only CLIs that are available + run_count ≥ 10
   → If all cold-start: fallback to static _task_priority_map (no change)
3. Sort: win_rate DESC, CLIPriority ASC as tiebreaker
   → best_cli = top of list
4. Override if: best_cli.win_rate - static_cli.win_rate ≥ 0.15 (15pp)
   where static_cli = CLI that would have been selected by _task_priority_map without adaptation
5. Anti-thrash guard: if last 3 runs for task_type used ≥ 3 distinct CLIs → hold default_cli
```

### Constants

```python
class AdaptiveConfig:
    MIN_RUNS_BEFORE_OVERRIDE    = 10    # cold-start gate
    WIN_RATE_DELTA_THRESHOLD    = 0.15  # 15 percentage points
    ANTI_THRASH_WINDOW          = 3     # look-back runs
    ANTI_THRASH_DISTINCT_LIMIT  = 3     # distinct CLIs in window = thrashing
```

### Notes

- `consensus_score` does NOT factor into routing — it measures analysis quality, not CLI fitness
- `--no-adaptive` flag bypasses steps 1–5 entirely, uses static priority map only
- Logic lives in `SmartRouter.select_cli_for_task()` — no new class needed
- `AnalysisMemory.get_cli_performance()` is the only new dependency in router

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
| `ai_delegate/router.py` | Update `select_cli_for_task()` with adaptive override logic |
| `ai_delegate/constants.py` | Add `AdaptiveConfig` class |
| `ai_delegate/cli.py` | Add inline rating prompt + `rate` subcommand |
| `tests/test_memory.py` | Tests for new memory methods |
| `tests/test_router.py` | Tests for adaptive override logic |
| `tests/test_cli.py` | Tests for rating prompt + subcommand |
