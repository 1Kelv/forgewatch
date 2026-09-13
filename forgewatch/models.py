from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


SEVERITY_ORDER = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}


def normalise_severity(value: str) -> str:
    value = (value or "medium").lower()
    aliases = {"warning": "medium", "error": "high", "unknown": "medium"}
    value = aliases.get(value, value)
    return value if value in SEVERITY_ORDER else "medium"


@dataclass
class Location:
    path: str
    start_line: int = 1
    end_line: int = 1
    start_column: int = 1
    end_column: int = 1


@dataclass
class Finding:
    scanner: str
    rule_id: str
    category: str
    severity: str
    confidence: str
    title: str
    explanation: str
    remediation: str
    locations: List[Location]
    evidence: str = ""
    cwes: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    validation_status: str = "not_attempted"
    origin: str = "scanner"
    source_ids: List[str] = field(default_factory=list)
    fingerprint: str = ""
    status: str = "open"

    def __post_init__(self) -> None:
        self.severity = normalise_severity(self.severity)
        self.evidence = self.evidence[:1000]
        if not self.source_ids:
            self.source_ids = [f"{self.scanner}:{self.rule_id}"]
        if not self.fingerprint:
            self.fingerprint = self.make_fingerprint()

    def make_fingerprint(self) -> str:
        location = self.locations[0] if self.locations else Location("unknown")
        if self.category in {"dependency", "secret"}:
            identity = self.rule_id.lower()
        else:
            identity = ",".join(sorted(self.cwes)) or self.rule_id.lower()
        canonical = "|".join(
            [self.category.lower(), identity, location.path.replace("\\", "/").lower(), str(location.start_line)]
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:24]

    def merge(self, other: "Finding") -> None:
        if SEVERITY_ORDER[other.severity] > SEVERITY_ORDER[self.severity]:
            self.severity = other.severity
        self.source_ids = sorted(set(self.source_ids + other.source_ids))
        self.cwes = sorted(set(self.cwes + other.cwes))
        self.references = sorted(set(self.references + other.references))
        known = {(loc.path, loc.start_line, loc.end_line) for loc in self.locations}
        self.locations.extend(
            loc for loc in other.locations if (loc.path, loc.start_line, loc.end_line) not in known
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ScannerRun:
    scanner: str
    version: str
    status: str
    coverage: str
    duration_ms: int
    findings: List[Finding] = field(default_factory=list)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        value = asdict(self)
        value["findings"] = [finding.to_dict() for finding in self.findings]
        return value


@dataclass
class ScanResult:
    scan_id: str
    repository: str
    commit_sha: str
    trigger: str
    ref: str
    started_at: str
    finished_at: str
    status: str
    scanner_runs: List[ScannerRun]
    findings: List[Finding]
    worktree_clean: bool = True
    default_branch_verified: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "schema_version": 1,
            "scan_id": self.scan_id,
            "repository": self.repository,
            "commit_sha": self.commit_sha,
            "trigger": self.trigger,
            "ref": self.ref,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "worktree_clean": self.worktree_clean,
            "default_branch_verified": self.default_branch_verified,
            "scanner_runs": [run.to_dict() for run in self.scanner_runs],
            "findings": [finding.to_dict() for finding in self.findings],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, sort_keys=True)
