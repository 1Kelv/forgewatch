from __future__ import annotations

import datetime as dt
import subprocess
import uuid
from pathlib import Path

from forgewatch.models import Finding, Location, ScanResult, ScannerRun


def finding(path: str = "App.tsx", line: int = 2, rule_id: str = "pervigil.javascript.browser.reverse-tabnabbing") -> Finding:
    return Finding(
        scanner="semgrep",
        rule_id=rule_id,
        category="code",
        severity="medium",
        confidence="high",
        title="Unsafe new-tab link",
        explanation="The opened page can access window.opener.",
        remediation='Add rel="noopener noreferrer".',
        locations=[Location(path, line, line)],
        evidence="fixture match",
        cwes=["CWE-1022"],
    )


def result(item: Finding, sha: str = "a" * 40, status: str = "findings") -> ScanResult:
    timestamp = dt.datetime.now(dt.timezone.utc).isoformat()
    return ScanResult(
        scan_id=str(uuid.uuid4()),
        repository="owner/repo",
        commit_sha=sha,
        trigger="manual",
        ref="main",
        started_at=timestamp,
        finished_at=timestamp,
        status=status,
        scanner_runs=[ScannerRun("semgrep", "1", "findings", "fixture", 1, [item])],
        findings=[item],
    )


def init_fixture_repo(root: Path) -> str:
    (root / "App.tsx").write_text(
        'export const App = () => (\n  <a href="https://example.invalid" target="_blank">Open</a>\n);\n',
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True)
    subprocess.run(["git", "add", "App.tsx"], cwd=str(root), check=True)
    subprocess.run(
        ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "fixture"],
        cwd=str(root),
        check=True,
    )
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), check=True, capture_output=True, text=True
    ).stdout.strip()
