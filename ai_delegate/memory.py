"""
Analysis memory for cross-session regression detection.
Stores results in SQLite at ~/.ai-delegate/memory.db.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class MemoryRecord:
    file_path: str
    task_type: str
    consensus_score: float
    finding_count: int
    critical_count: int
    high_count: int
    findings_summary: str
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class AnalysisMemory:
    """Stores and queries analysis results across sessions."""

    DEFAULT_DB = Path.home() / ".ai-delegate" / "memory.db"

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _column_exists(self, conn: sqlite3.Connection, table: str, column: str) -> bool:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return any(row[1] == column for row in rows)

    def _seed_cli_priors(self, conn: sqlite3.Connection) -> None:
        """Seed cli_performance with CLI_PRIORS if rows don't exist yet."""
        from .constants import CLI_PRIORS
        timestamp = datetime.now(timezone.utc).isoformat()
        for cli_name, task_rates in CLI_PRIORS.items():
            for task_type, win_rate in task_rates.items():
                existing = conn.execute(
                    "SELECT 1 FROM cli_performance WHERE cli_name = ? AND task_type = ?",
                    (cli_name, task_type),
                ).fetchone()
                if existing:
                    continue
                virtual_runs = 10
                win_count = round(win_rate * virtual_runs)
                loss_count = virtual_runs - win_count
                conn.execute(
                    """INSERT INTO cli_performance
                       (cli_name, task_type, run_count, win_count, loss_count, win_rate, last_updated)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cli_name, task_type, virtual_runs, win_count, loss_count, win_rate, timestamp),
                )

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=-65536")  # 64 MB page cache
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analysis_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    consensus_score REAL NOT NULL,
                    finding_count INTEGER NOT NULL,
                    critical_count INTEGER NOT NULL,
                    high_count INTEGER NOT NULL,
                    findings_summary TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_file_task ON analysis_runs (file_path, task_type)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS findings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    analysis_run_id INTEGER,
                    task_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    issue_text TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_findings_task ON findings (task_type)"
            )
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS findings_fts
                USING fts5(issue_text, severity, task_type, content=findings, content_rowid=id)
            """)
            # Adaptive routing schema (backward-compatible)
            if not self._column_exists(conn, "analysis_runs", "cli_name"):
                conn.execute("ALTER TABLE analysis_runs ADD COLUMN cli_name TEXT")
            if not self._column_exists(conn, "analysis_runs", "user_rating"):
                conn.execute("ALTER TABLE analysis_runs ADD COLUMN user_rating INTEGER")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_cli_task ON analysis_runs (cli_name, task_type)"
            )
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cli_performance (
                    cli_name     TEXT NOT NULL,
                    task_type    TEXT NOT NULL,
                    run_count    INTEGER NOT NULL DEFAULT 0,
                    win_count    INTEGER NOT NULL DEFAULT 0,
                    loss_count   INTEGER NOT NULL DEFAULT 0,
                    win_rate     REAL NOT NULL DEFAULT 0.0,
                    last_updated TEXT NOT NULL,
                    PRIMARY KEY (cli_name, task_type)
                )
            """)
            self._seed_cli_priors(conn)

    def store(self, record: MemoryRecord) -> int:
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT INTO analysis_runs
                   (file_path, task_type, consensus_score, finding_count,
                    critical_count, high_count, findings_summary, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record.file_path, record.task_type, record.consensus_score,
                    record.finding_count, record.critical_count, record.high_count,
                    record.findings_summary, record.timestamp,
                ),
            )
            return int(cursor.lastrowid) if cursor.lastrowid is not None else 0

    def get_history(self, file_path: str, task_type: str, limit: int = 10) -> List[MemoryRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT file_path, task_type, consensus_score, finding_count,
                          critical_count, high_count, findings_summary, timestamp
                   FROM analysis_runs WHERE file_path = ? AND task_type = ?
                   ORDER BY id DESC LIMIT ?""",
                (file_path, task_type, limit),
            ).fetchall()
        return [
            MemoryRecord(
                file_path=r[0], task_type=r[1], consensus_score=r[2],
                finding_count=r[3], critical_count=r[4], high_count=r[5],
                findings_summary=r[6], timestamp=r[7],
            )
            for r in rows
        ]

    def detect_regression(self, current: MemoryRecord) -> Optional[Dict]:
        """Compare current result against most recent stored result. Returns regression dict or None."""
        history = self.get_history(current.file_path, current.task_type, limit=1)
        if not history:
            return None
        prev = history[0]
        new_findings = current.finding_count - prev.finding_count
        new_critical = current.critical_count - prev.critical_count
        if new_findings > 0 or new_critical > 0:
            return {
                "new_findings": max(new_findings, 0),
                "new_critical": max(new_critical, 0),
                "prev_findings": prev.finding_count,
                "curr_findings": current.finding_count,
                "prev_score": prev.consensus_score,
                "curr_score": current.consensus_score,
            }
        return None

    def store_findings(
        self,
        analysis_run_id: Optional[int],
        task_type: str,
        findings: List[Dict],
    ) -> None:
        """Store individual findings and update FTS5 index."""
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            for f in findings:
                cursor = conn.execute(
                    """INSERT INTO findings (analysis_run_id, task_type, severity, issue_text, timestamp)
                       VALUES (?, ?, ?, ?, ?)""",
                    (analysis_run_id, task_type, f.get("severity", ""), f.get("issue", ""), timestamp),
                )
                rowid = cursor.lastrowid
                conn.execute(
                    "INSERT INTO findings_fts(rowid, issue_text, severity, task_type) VALUES (?, ?, ?, ?)",
                    (rowid, f.get("issue", ""), f.get("severity", ""), task_type),
                )

    def get_all_findings(self, task_type: Optional[str] = None) -> List[Dict]:
        """Return all stored findings, optionally filtered by task_type."""
        with self._connect() as conn:
            if task_type:
                rows = conn.execute(
                    "SELECT id, analysis_run_id, task_type, severity, issue_text, timestamp FROM findings WHERE task_type = ?",
                    (task_type,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, analysis_run_id, task_type, severity, issue_text, timestamp FROM findings"
                ).fetchall()
        return [
            {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
             "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
            for r in rows
        ]

    def search_findings(
        self,
        query: str,
        task_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
    ) -> List[Dict]:
        """Full-text search across stored findings using FTS5."""
        conditions = ["findings_fts MATCH ?"]
        params: List = [query]

        if task_type:
            conditions.append("f.task_type = ?")
            params.append(task_type)
        if severity:
            conditions.append("f.severity = ?")
            params.append(severity)

        where = " AND ".join(conditions)
        params.append(limit)

        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
                   FROM findings_fts
                   JOIN findings f ON findings_fts.rowid = f.id
                   WHERE {where}
                   ORDER BY rank
                   LIMIT ?""",
                params,
            ).fetchall()
        return [
            {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
             "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
            for r in rows
        ]

    def record_cli_run(self, run_id: int, cli_name: str) -> None:
        """Backfill cli_name into analysis_runs after a run completes."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE analysis_runs SET cli_name = ? WHERE id = ?",
                (cli_name, run_id),
            )

    def store_rating(self, run_id: int, rating: int) -> None:
        """Store binary rating (0/1) and incrementally update cli_performance."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT cli_name, task_type FROM analysis_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if not row or not row[0]:
                return
            cli_name, task_type = row
            conn.execute(
                "UPDATE analysis_runs SET user_rating = ? WHERE id = ?",
                (rating, run_id),
            )
            timestamp = datetime.now(timezone.utc).isoformat()
            if rating == 1:
                conn.execute(
                    """UPDATE cli_performance
                       SET win_count = win_count + 1,
                           run_count = run_count + 1,
                           win_rate = CAST(win_count + 1 AS REAL) / (win_count + loss_count + 1),
                           last_updated = ?
                       WHERE cli_name = ? AND task_type = ?""",
                    (timestamp, cli_name, task_type),
                )
            else:
                conn.execute(
                    """UPDATE cli_performance
                       SET loss_count = loss_count + 1,
                           run_count = run_count + 1,
                           win_rate = CAST(win_count AS REAL) / (win_count + loss_count + 1),
                           last_updated = ?
                       WHERE cli_name = ? AND task_type = ?""",
                    (timestamp, cli_name, task_type),
                )
            # Upsert if CLI not in priors
            conn.execute(
                """INSERT OR IGNORE INTO cli_performance
                   (cli_name, task_type, run_count, win_count, loss_count, win_rate, last_updated)
                   VALUES (?, ?, 1, ?, ?, ?, ?)""",
                (cli_name, task_type,
                 1 if rating == 1 else 0,
                 0 if rating == 1 else 1,
                 float(rating), timestamp),
            )

    def get_cli_performance(self, task_type: str) -> List[Dict]:
        """Return all cli_performance rows for a task_type, ordered by win_rate DESC."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT cli_name, win_rate, win_count, loss_count, run_count, last_updated
                   FROM cli_performance WHERE task_type = ?
                   ORDER BY win_rate DESC""",
                (task_type,),
            ).fetchall()
        return [
            {
                "cli_name": r[0], "win_rate": r[1], "win_count": r[2],
                "loss_count": r[3], "run_count": r[4], "last_updated": r[5],
            }
            for r in rows
        ]

    def get_recent_cli_runs(self, task_type: str, limit: int = 3) -> List[str]:
        """Return cli_name of last N runs for task_type (newest first).
        Only includes rows where cli_name is set."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT cli_name FROM analysis_runs
                   WHERE task_type = ? AND cli_name IS NOT NULL
                   ORDER BY id DESC LIMIT ?""",
                (task_type, limit),
            ).fetchall()
        return [r[0] for r in rows]

    def get_routing_context(self, task_type: str, recent_limit: int = 3) -> tuple:
        """
        Batch query: fetch cli_performance rows AND recent run names in one connection.

        Returns:
            (perf_rows: List[Dict], recent_cli_names: List[str])
        """
        with self._connect() as conn:
            perf_rows = conn.execute(
                """SELECT cli_name, win_rate, win_count, loss_count, run_count, last_updated
                   FROM cli_performance WHERE task_type = ?
                   ORDER BY win_rate DESC""",
                (task_type,),
            ).fetchall()
            recent_rows = conn.execute(
                """SELECT cli_name FROM analysis_runs
                   WHERE task_type = ? AND cli_name IS NOT NULL
                   ORDER BY id DESC LIMIT ?""",
                (task_type, recent_limit),
            ).fetchall()
        return (
            [
                {
                    "cli_name": r[0], "win_rate": r[1], "win_count": r[2],
                    "loss_count": r[3], "run_count": r[4], "last_updated": r[5],
                }
                for r in perf_rows
            ],
            [r[0] for r in recent_rows],
        )

    def check_cache(
        self,
        content_hash: str,
        task_description: str,
        expert_names: list,
    ) -> None:
        """Check cache for previous analysis. Returns None (cache miss) until cache.py is implemented."""
        return None
