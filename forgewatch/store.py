from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterable, List, Optional

from .models import Finding, ScanResult


SCHEMA = """
PRAGMA journal_mode=WAL;
CREATE TABLE IF NOT EXISTS scans (
  id TEXT PRIMARY KEY,
  repository TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  trigger TEXT NOT NULL,
  ref TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT NOT NULL,
  status TEXT NOT NULL,
  report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS findings (
  repository TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  status TEXT NOT NULL,
  present INTEGER NOT NULL DEFAULT 1,
  first_seen_scan TEXT NOT NULL,
  last_seen_scan TEXT NOT NULL,
  last_seen_commit TEXT NOT NULL,
  details_json TEXT NOT NULL,
  dismissal_reason TEXT,
  dismissed_by TEXT,
  dismissed_at TEXT,
  PRIMARY KEY (repository, fingerprint)
);
CREATE TABLE IF NOT EXISTS scan_findings (
  scan_id TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  PRIMARY KEY (scan_id, fingerprint)
);
CREATE TABLE IF NOT EXISTS approvals (
  nonce TEXT PRIMARY KEY,
  repository TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  action TEXT NOT NULL,
  actor TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  used_at INTEGER
);
CREATE TABLE IF NOT EXISTS webhook_deliveries (
  delivery_id TEXT PRIMARY KEY,
  received_at INTEGER NOT NULL,
  event TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS fix_leases (
  repository TEXT NOT NULL,
  fingerprint TEXT NOT NULL,
  commit_sha TEXT NOT NULL,
  owner TEXT NOT NULL,
  expires_at INTEGER NOT NULL,
  PRIMARY KEY (repository, fingerprint)
);
"""


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row
        self._lock = threading.RLock()
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        with self._lock:
            self.connection.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.connection.close()

    def record_scan(self, result: ScanResult, is_default_branch: bool) -> None:
        report = result.to_json()
        seen = {finding.fingerprint for finding in result.findings}
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT OR REPLACE INTO scans VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.scan_id,
                    result.repository,
                    result.commit_sha,
                    result.trigger,
                    result.ref,
                    result.started_at,
                    result.finished_at,
                    result.status,
                    report,
                ),
            )
            for finding in result.findings:
                previous = self.connection.execute(
                    "SELECT status, present FROM findings WHERE repository=? AND fingerprint=?",
                    (result.repository, finding.fingerprint),
                ).fetchone()
                if previous and previous["status"] == "dismissed" and previous["present"]:
                    finding.status = "dismissed"
                elif previous and previous["status"] == "dismissed" and not previous["present"]:
                    finding.status = "open"
                else:
                    finding.status = previous["status"] if previous and previous["status"] == "open" else "open"
                self.connection.execute(
                    """
                    INSERT INTO findings(repository, fingerprint, status, present, first_seen_scan,
                      last_seen_scan, last_seen_commit, details_json)
                    VALUES (?, ?, ?, 1, ?, ?, ?, ?)
                    ON CONFLICT(repository, fingerprint) DO UPDATE SET
                      status=excluded.status, present=1, last_seen_scan=excluded.last_seen_scan,
                      last_seen_commit=excluded.last_seen_commit, details_json=excluded.details_json,
                      dismissal_reason=CASE WHEN excluded.status='open' THEN NULL ELSE findings.dismissal_reason END,
                      dismissed_by=CASE WHEN excluded.status='open' THEN NULL ELSE findings.dismissed_by END,
                      dismissed_at=CASE WHEN excluded.status='open' THEN NULL ELSE findings.dismissed_at END
                    """,
                    (
                        result.repository,
                        finding.fingerprint,
                        finding.status,
                        result.scan_id,
                        result.scan_id,
                        result.commit_sha,
                        json.dumps(finding.to_dict(), sort_keys=True),
                    ),
                )
                self.connection.execute(
                    "INSERT OR IGNORE INTO scan_findings(scan_id, fingerprint) VALUES (?, ?)",
                    (result.scan_id, finding.fingerprint),
                )
            if is_default_branch and result.status != "incomplete":
                rows = self.connection.execute(
                    "SELECT fingerprint, status FROM findings WHERE repository=? AND present=1",
                    (result.repository,),
                ).fetchall()
                for row in rows:
                    if row["fingerprint"] not in seen:
                        status = "resolved" if row["status"] == "open" else row["status"]
                        self.connection.execute(
                            "UPDATE findings SET present=0, status=? WHERE repository=? AND fingerprint=?",
                            (status, result.repository, row["fingerprint"]),
                        )

    def dismiss(self, repository: str, fingerprint: str, reason: str, actor: str, timestamp: str) -> None:
        if not reason.strip():
            raise ValueError("a dismissal reason is required")
        with self._lock, self.connection:
            cursor = self.connection.execute(
                """UPDATE findings SET status='dismissed', dismissal_reason=?, dismissed_by=?, dismissed_at=?
                   WHERE repository=? AND fingerprint=? AND present=1""",
                (reason.strip(), actor, timestamp, repository, fingerprint),
            )
            if cursor.rowcount != 1:
                raise ValueError("finding is unknown or not currently present")

    def get_finding(self, repository: str, fingerprint: str) -> Optional[sqlite3.Row]:
        with self._lock:
            return self.connection.execute(
                "SELECT * FROM findings WHERE repository=? AND fingerprint=?",
                (repository, fingerprint),
            ).fetchone()

    def findings(self, repository: str, statuses: Iterable[str] = ("open", "dismissed")) -> List[sqlite3.Row]:
        statuses = tuple(statuses)
        placeholders = ",".join("?" for _ in statuses)
        with self._lock:
            return self.connection.execute(
                f"SELECT * FROM findings WHERE repository=? AND status IN ({placeholders}) ORDER BY last_seen_scan DESC",
                (repository, *statuses),
            ).fetchall()

    def register_approval(
        self,
        nonce: str,
        repository: str,
        fingerprint: str,
        commit_sha: str,
        action: str,
        actor: str,
        expires_at: int,
    ) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, NULL)",
                (nonce, repository, fingerprint, commit_sha, action, actor, expires_at),
            )

    def consume_approval(
        self,
        nonce: str,
        repository: str,
        fingerprint: str,
        commit_sha: str,
        action: str,
        now: int,
    ) -> None:
        with self._lock, self.connection:
            row = self.connection.execute(
                "SELECT * FROM approvals WHERE nonce=?", (nonce,)
            ).fetchone()
            if row is None:
                raise ValueError("approval is not registered")
            if row["used_at"] is not None:
                raise ValueError("approval has already been used")
            if row["expires_at"] < now:
                raise ValueError("approval has expired")
            expected = (repository, fingerprint, commit_sha, action)
            actual = (row["repository"], row["fingerprint"], row["commit_sha"], row["action"])
            if actual != expected:
                raise ValueError("approval scope does not match the requested action")
            cursor = self.connection.execute(
                "UPDATE approvals SET used_at=? WHERE nonce=? AND used_at IS NULL", (now, nonce)
            )
            if cursor.rowcount != 1:
                raise ValueError("approval replay detected")

    def record_webhook_delivery(self, delivery_id: str, event: str, now: int) -> bool:
        try:
            with self._lock, self.connection:
                self.connection.execute(
                    "INSERT INTO webhook_deliveries VALUES (?, ?, ?)",
                    (delivery_id, now, event),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def acquire_fix_lease(
        self,
        repository: str,
        fingerprint: str,
        commit_sha: str,
        owner: str,
        ttl_seconds: int = 1800,
    ) -> None:
        now = int(time.time())
        with self._lock, self.connection:
            self.connection.execute("DELETE FROM fix_leases WHERE expires_at < ?", (now,))
            try:
                self.connection.execute(
                    "INSERT INTO fix_leases VALUES (?, ?, ?, ?, ?)",
                    (repository, fingerprint, commit_sha, owner, now + ttl_seconds),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("a fix is already being prepared for this finding") from error

    def release_fix_lease(self, repository: str, fingerprint: str, owner: str) -> None:
        with self._lock, self.connection:
            self.connection.execute(
                "DELETE FROM fix_leases WHERE repository=? AND fingerprint=? AND owner=?",
                (repository, fingerprint, owner),
            )
