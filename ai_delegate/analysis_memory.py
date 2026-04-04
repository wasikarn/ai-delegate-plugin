"""Cross-session analysis memory using SQLite for regression detection."""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

MEMORY_DB_PATH = Path.home() / ".ai-delegate" / "memory.db"


@dataclass
class AnalysisRecord:
    """A stored analysis result for regression comparison."""
    content_hash: str
    task_type: str
    findings_count: int
    severity_counts: dict = field(default_factory=dict)
    finding_keys: List[str] = field(default_factory=list)
    timestamp: str = ""


@dataclass
class RegressionResult:
    """Result of a regression check against prior analysis."""
    has_regression: bool
    new_findings: List[str] = field(default_factory=list)
    resolved_findings: List[str] = field(default_factory=list)
    summary: str = ""


class AnalysisMemory:
    """Stores and retrieves analysis results for regression detection."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or MEMORY_DB_PATH
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS analyses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_hash TEXT NOT NULL,
                    task_type TEXT NOT NULL,
                    findings_count INTEGER NOT NULL,
                    severity_counts TEXT NOT NULL,
                    finding_keys TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(str(self.db_path))

    @staticmethod
    def hash_content(content: str) -> str:
        """Stable hash for content identification."""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def store(self, content: str, task_type: str, findings: list) -> None:
        """Store analysis results for future regression checks."""
        content_hash = self.hash_content(content)
        severity_counts = {}
        finding_keys = []
        for f in findings:
            sev = f.get("severity", "unknown").lower() if isinstance(f, dict) else getattr(f, "severity", "unknown").lower()
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
            issue = f.get("issue", "") if isinstance(f, dict) else getattr(f, "issue", "")
            finding_keys.append(hashlib.md5(f"{sev}|{issue}".encode()).hexdigest())

        with self._connect() as conn:
            conn.execute(
                "INSERT INTO analyses (content_hash, task_type, findings_count, severity_counts, finding_keys) VALUES (?, ?, ?, ?, ?)",
                (content_hash, task_type, len(findings), json.dumps(severity_counts), json.dumps(finding_keys)),
            )

    def check_regression(self, content: str, task_type: str, findings: list) -> Optional[RegressionResult]:
        """Compare current findings against last stored run for same content."""
        content_hash = self.hash_content(content)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT finding_keys FROM analyses WHERE content_hash=? AND task_type=? ORDER BY id DESC LIMIT 1",
                (content_hash, task_type),
            ).fetchone()

        if row is None:
            return None  # No prior run to compare

        prior_keys = set(json.loads(row[0]))
        current_keys = set()
        for f in findings:
            sev = f.get("severity", "unknown").lower() if isinstance(f, dict) else getattr(f, "severity", "unknown").lower()
            issue = f.get("issue", "") if isinstance(f, dict) else getattr(f, "issue", "")
            current_keys.add(hashlib.md5(f"{sev}|{issue}".encode()).hexdigest())

        new_keys = current_keys - prior_keys
        resolved_keys = prior_keys - current_keys
        has_regression = len(new_keys) > 0

        parts = []
        if new_keys:
            parts.append(f"{len(new_keys)} new finding(s) appeared")
        if resolved_keys:
            parts.append(f"{len(resolved_keys)} finding(s) resolved")
        summary = "; ".join(parts) if parts else "No changes detected"

        return RegressionResult(
            has_regression=has_regression,
            new_findings=list(new_keys),
            resolved_findings=list(resolved_keys),
            summary=summary,
        )

    def get_history(self, content: str, task_type: str) -> List[AnalysisRecord]:
        """Get all stored runs for given content and task type."""
        content_hash = self.hash_content(content)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT content_hash, task_type, findings_count, severity_counts, finding_keys, timestamp FROM analyses WHERE content_hash=? AND task_type=? ORDER BY timestamp DESC",
                (content_hash, task_type),
            ).fetchall()

        records = []
        for row in rows:
            records.append(AnalysisRecord(
                content_hash=row[0],
                task_type=row[1],
                findings_count=row[2],
                severity_counts=json.loads(row[3]),
                finding_keys=json.loads(row[4]),
                timestamp=row[5],
            ))
        return records
