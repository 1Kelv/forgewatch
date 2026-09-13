#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from forgewatch.engine import scan, verified_default_branch
from forgewatch.remediation import SUPPORTED_RULE, prepare_fix
from forgewatch.reporting import write_reports
from forgewatch.store import Store


def command(root: Path, *args: str) -> None:
    process = subprocess.run(list(args), cwd=str(root), capture_output=True, text=True, check=False)
    if process.returncode != 0:
        raise RuntimeError(process.stderr or process.stdout)


def main() -> int:
    project = Path(__file__).resolve().parents[1]
    missing = [binary for binary in ("semgrep", "osv-scanner", "gitleaks") if not shutil.which(binary)]
    if missing:
        print(f"Missing scanner binaries: {', '.join(missing)}", file=sys.stderr)
        return 2
    (project / ".forgewatch").mkdir(exist_ok=True)
    # Keep the target outside Forgewatch's ignored state directory. OSV-Scanner
    # honors parent .gitignore files and would otherwise skip the entire fixture.
    target = Path(tempfile.mkdtemp(prefix="forgewatch-demo-target-"))
    try:
        for filename in ("reverse_tabnabbing.tsx", "package.json", "package-lock.json"):
            source = project / "fixtures" / "vulnerable" / filename
            destination = target / ("App.tsx" if filename == "reverse_tabnabbing.tsx" else filename)
            shutil.copy2(source, destination)
        command(target, "git", "init", "-q", "-b", "main")
        command(target, "git", "add", ".")
        command(
            target,
            "git", "-c", "user.name=Forgewatch Fixture", "-c", "user.email=fixture@example.invalid",
            "commit", "-qm", "deliberately vulnerable fixture",
        )
        config = {
            "schema_version": 1,
            "_config_dir": str(project),
            "repository": {"slug": "local/forgewatch-fixture", "default_branch": "main"},
            "policy": {"fix_generation": "automatic"},
            "scanners": {
                "semgrep": {
                    "enabled": True, "binary": "semgrep", "config": "rules/semgrep.yml",
                    "timeout_seconds": 120, "_config_dir": str(project),
                },
                "osv": {"enabled": True, "binary": "osv-scanner", "timeout_seconds": 120},
                "gitleaks": {"enabled": True, "binary": "gitleaks", "history": False, "timeout_seconds": 120},
            },
            "execution": {
                "isolation": "container", "container_image": "node:20-bookworm", "network": "none",
                "timeout_seconds": 120, "validation_commands": [],
            },
            "state": {
                "database": ".forgewatch/demo-state.db",
                "artifacts": ".forgewatch/artifacts/demo-fixture",
            },
        }
        database = project / ".forgewatch" / "demo-state.db"
        if database.exists():
            database.unlink()
        store = Store(database)
        try:
            result = scan(target, config, "manual", "main")
            result.default_branch_verified = verified_default_branch(target, "main", "main", result.commit_sha)
            store.record_scan(result, result.default_branch_verified)
            report_dir = project / ".forgewatch" / "artifacts" / "demo-fixture"
            write_reports(result, report_dir)
            supported = next((finding for finding in result.findings if finding.rule_id == SUPPORTED_RULE), None)
            if supported is None:
                raise RuntimeError("the real Semgrep run did not detect the deliberately vulnerable fixture")
            artifact = prepare_fix(target, config, store, supported.fingerprint, result.commit_sha)
            metadata = json.loads((artifact / "metadata.json").read_text(encoding="utf-8"))
            output = {
                "scan_status": result.status,
                "scanner_statuses": {run.scanner: run.status for run in result.scanner_runs},
                "finding": supported.fingerprint,
                "security_test_before": metadata["regression_check"]["before"],
                "security_test_after": metadata["regression_check"]["after"],
                "security_rescan": metadata["security_rescan"]["status"],
                "isolated_validation": metadata["validation_status"],
                "validation_limitation": metadata["validation_error"],
                "scan_report": str(report_dir / "scan.md"),
                "patch_artifact": str(artifact / "change.patch"),
            }
            print(json.dumps(output, indent=2))
            return 0
        finally:
            store.close()
    except (OSError, RuntimeError, ValueError, StopIteration) as error:
        print(f"Forgewatch demo failed: {error}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(target, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
