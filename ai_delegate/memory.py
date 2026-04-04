"""
Analysis memory for cross-session regression detection.
Stores results in SQLite at ~/.ai-delegate/memory.db.
"""
import sqlite3
from dataclasses import dataclass
from datetime import datetime
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
            self.timestamp = datetime.utcnow().isoformat()


class AnalysisMemory:
    """Stores and queries analysis results across sessions."""

    DEFAULT_DB = Path.home() / ".ai-delegate" / "memory.db"

    def __init__(self, db_path: Optional[Path] = None):
        self._db_path = Path(db_path) if db_path else self.DEFAULT_DB
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self._db_path))

    def _init_db(self) -> None:
        with self._connect() as conn:
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

    def store(self, record: MemoryRecord) -> None:
        with self._connect() as conn:
            conn.execute(
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
        timestamp = datetime.utcnow().isoformat()
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

    def search_findings(self, query: str, task_type: Optional[str] = None, limit: int = 20) -> List[Dict]:
        """Full-text search across stored findings using FTS5."""
        with self._connect() as conn:
            if task_type:
                rows = conn.execute(
                    """SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
                       FROM findings_fts
                       JOIN findings f ON findings_fts.rowid = f.id
                       WHERE findings_fts MATCH ? AND f.task_type = ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, task_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT f.id, f.analysis_run_id, f.task_type, f.severity, f.issue_text, f.timestamp
                       FROM findings_fts
                       JOIN findings f ON findings_fts.rowid = f.id
                       WHERE findings_fts MATCH ?
                       ORDER BY rank
                       LIMIT ?""",
                    (query, limit),
                ).fetchall()
        return [
            {"id": r[0], "analysis_run_id": r[1], "task_type": r[2],
             "severity": r[3], "issue_text": r[4], "timestamp": r[5]}
            for r in rows
        ]
