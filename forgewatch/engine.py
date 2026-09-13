from __future__ import annotations

import datetime as dt
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding, ScanResult, ScannerRun
from .scanners import run_configured_scanner


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def git_sha(root: Path) -> str:
    process = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=str(root), capture_output=True, text=True, check=False
    )
    if process.returncode != 0:
        raise RuntimeError("the scan target must be a Git checkout with a resolvable HEAD")
    return process.stdout.strip()


def worktree_clean(root: Path) -> bool:
    process = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=str(root), capture_output=True, text=True, check=False
    )
    return process.returncode == 0 and not process.stdout.strip()


def verified_default_branch(root: Path, default_branch: str, ref: str, commit_sha: str) -> bool:
    if ref not in {default_branch, f"refs/heads/{default_branch}"} or not worktree_clean(root):
        return False
    for candidate in (f"refs/remotes/origin/{default_branch}", f"refs/heads/{default_branch}"):
        process = subprocess.run(
            ["git", "rev-parse", "--verify", candidate],
            cwd=str(root), capture_output=True, text=True, check=False
        )
        if process.returncode == 0:
            return process.stdout.strip() == commit_sha
    return False


def deduplicate(runs: List[ScannerRun]) -> List[Finding]:
    unique: Dict[str, Finding] = {}
    for run in runs:
        for finding in run.findings:
            if finding.fingerprint in unique:
                unique[finding.fingerprint].merge(finding)
            else:
                unique[finding.fingerprint] = finding
    return list(unique.values())


def scan(root: Path, config: Dict[str, Any], trigger: str, ref: str) -> ScanResult:
    started_at = utc_now()
    runs = [
        run_configured_scanner(name, root, scanner_config)
        for name, scanner_config in config.get("scanners", {}).items()
        if name in {"semgrep", "osv", "gitleaks"}
    ]
    expected = {"semgrep", "osv", "gitleaks"}
    configured = set(config.get("scanners", {}))
    for missing in sorted(expected - configured):
        runs.append(ScannerRun(missing, "not-run", "skipped", "none", 0, error="scanner is not configured"))
    findings = deduplicate(runs)
    if any(run.status in {"failed", "skipped"} for run in runs):
        status = "incomplete"
    elif findings:
        status = "findings"
    else:
        status = "clean"
    return ScanResult(
        scan_id=str(uuid.uuid4()),
        repository=config["repository"]["slug"],
        commit_sha=git_sha(root),
        trigger=trigger,
        ref=ref,
        started_at=started_at,
        finished_at=utc_now(),
        status=status,
        scanner_runs=runs,
        findings=findings,
        worktree_clean=worktree_clean(root),
    )
