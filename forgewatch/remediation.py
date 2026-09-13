from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from . import ai
from .approvals import verify_and_consume
from .engine import git_sha, utc_now
from .models import Finding, Location
from .redaction import redact_text
from .reporting import _safe_markdown, finding_plain_language
from .scanners import run_configured_scanner
from .store import Store


SUPPORTED_RULE = "pervigil.javascript.browser.reverse-tabnabbing"
ANCHOR = re.compile(r"<a\b(?P<attrs>[^>]*\btarget=[\"']_blank[\"'][^>]*)>", re.IGNORECASE | re.DOTALL)
REL = re.compile(r"\brel\s*=", re.IGNORECASE)
FORBIDDEN_PATCH_MARKERS = (
    "nosemgrep",
    "semgrepignore",
    "eslint-disable",
    "@ts-ignore",
    "npm audit fix --force",
)


def finding_from_json(value: str) -> Finding:
    data = json.loads(value)
    data["locations"] = [Location(**location) for location in data.get("locations", [])]
    return Finding(**data)


def detect_reverse_tabnabbing(path: Path) -> List[int]:
    content = path.read_text(encoding="utf-8")
    lines = []
    for match in ANCHOR.finditer(content):
        if not REL.search(match.group("attrs")):
            lines.append(content.count("\n", 0, match.start()) + 1)
    return lines


def apply_reverse_tabnabbing_fix(root: Path, finding: Finding) -> List[str]:
    if finding.rule_id != SUPPORTED_RULE:
        raise ValueError(f"deterministic remediation does not support {finding.rule_id}")
    if len(finding.locations) != 1:
        raise ValueError("deterministic remediation requires exactly one location")
    location = finding.locations[0]
    path = (root / location.path).resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as error:
        raise ValueError("finding path escapes the repository") from error
    content = path.read_text(encoding="utf-8")
    candidates = []
    for match in ANCHOR.finditer(content):
        line = content.count("\n", 0, match.start()) + 1
        if line <= location.end_line and content.count("\n", 0, match.end()) + 1 >= location.start_line:
            if not REL.search(match.group("attrs")):
                candidates.append(match)
    if len(candidates) != 1:
        raise ValueError(f"expected one unfixed anchor at the finding location, found {len(candidates)}")
    match = candidates[0]
    replacement = match.group(0)[:-1] + ' rel="noopener noreferrer">'
    path.write_text(content[: match.start()] + replacement + content[match.end() :], encoding="utf-8")
    return [location.path]


def _patch_paths(patch: str) -> Set[str]:
    paths: Set[str] = set()
    for line in patch.splitlines():
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            paths.add(line[6:])
    paths.discard("/dev/null")
    return paths


def _validate_patch_scope(patch: str, allowed: Set[str]) -> None:
    lowered = patch.lower()
    for marker in FORBIDDEN_PATCH_MARKERS:
        if marker in lowered:
            raise ValueError(f"patch contains forbidden security-suppression marker: {marker}")
    changed = _patch_paths(patch)
    if not changed:
        raise ValueError("patch does not change a file")
    if not changed.issubset(allowed):
        raise ValueError(f"patch changes files outside the approved scope: {sorted(changed - allowed)}")


def _git(root: Path, args: List[str], input_text: Optional[str] = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=str(root), input=input_text, text=True, capture_output=True, check=False
    )


def _container_validation(worktree: Path, source_root: Path, config: Dict[str, Any]) -> List[Dict[str, Any]]:
    if config.get("isolation") != "container":
        raise RuntimeError("automated code execution is disabled because execution.isolation is not container")
    docker = shutil.which("docker")
    if not docker:
        raise RuntimeError("automated code execution is disabled because Docker isolation is unavailable")
    node_modules = source_root / "node_modules"
    if not node_modules.is_dir():
        raise RuntimeError("isolated validation requires preinstalled node_modules; bootstrap dependencies outside the code execution environment first")
    image = config.get("container_image", "node:20-bookworm")
    network = config.get("network", "none")
    timeout = int(config.get("timeout_seconds", 900))
    results = []
    for command in config.get("validation_commands", []):
        invocation = [
            docker,
            "run",
            "--rm",
            "--network",
            network,
            "--read-only",
            "--cap-drop",
            "ALL",
            "--security-opt",
            "no-new-privileges",
            "--pids-limit",
            "256",
            "--memory",
            "2g",
            "--cpus",
            "2",
            "--tmpfs",
            "/tmp:rw,noexec,nosuid,size=512m",
            "--user",
            f"{os.getuid()}:{os.getgid()}",
            "-v",
            f"{worktree}:/workspace:rw",
            "-v",
            f"{node_modules}:/workspace/node_modules:ro",
            "-w",
            "/workspace",
            image,
            "/bin/sh",
            "-lc",
            command,
        ]
        started = time.monotonic()
        try:
            process = subprocess.run(
                invocation, capture_output=True, text=True, timeout=timeout, check=False, env={"PATH": os.environ.get("PATH", "")}
            )
            result = {
                "command": command,
                "status": "passed" if process.returncode == 0 else "failed",
                "exit_code": process.returncode,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "output": redact_text((process.stdout + "\n" + process.stderr)[-4000:]),
            }
        except subprocess.TimeoutExpired:
            result = {
                "command": command,
                "status": "failed",
                "exit_code": 124,
                "duration_ms": int((time.monotonic() - started) * 1000),
                "output": f"timed out after {timeout}s",
            }
        results.append(result)
        if result["status"] != "passed":
            break
    return results


def _security_rescan(worktree: Path, config: Dict[str, Any], finding: Finding) -> Dict[str, Any]:
    scanner_key = {"code": "semgrep", "dependency": "osv", "secret": "gitleaks"}.get(finding.category)
    scanner_config = config.get("scanners", {}).get(scanner_key or "")
    if not scanner_key or not scanner_config:
        return {
            "scanner": scanner_key or finding.scanner,
            "status": "blocked",
            "finding_still_present": None,
            "error": "the relevant scanner is not configured for fix validation",
        }
    run = run_configured_scanner(scanner_key, worktree, scanner_config)
    if run.status in {"failed", "skipped"}:
        return {
            "scanner": run.scanner,
            "version": run.version,
            "status": "blocked",
            "finding_still_present": None,
            "error": run.error or "the relevant scanner did not complete",
        }
    still_present = any(item.fingerprint == finding.fingerprint for item in run.findings)
    return {
        "scanner": run.scanner,
        "version": run.version,
        "status": "failed" if still_present else "passed",
        "finding_still_present": still_present,
        "other_findings": len([item for item in run.findings if item.fingerprint != finding.fingerprint]),
        "error": None,
    }


def prepare_fix(
    root: Path,
    config: Dict[str, Any],
    store: Store,
    fingerprint: str,
    commit_sha: str,
    approval_token: Optional[str] = None,
    approval_key: Optional[str] = None,
    use_ai: bool = False,
) -> Path:
    repository = config["repository"]["slug"]
    current_sha = git_sha(root)
    if current_sha != commit_sha:
        raise ValueError("requested fix commit is stale or does not match the checkout")
    row = store.get_finding(repository, fingerprint)
    if row is None or not row["present"]:
        raise ValueError("finding is unknown or no longer present")
    if row["last_seen_commit"] != commit_sha:
        raise ValueError("finding was not observed at the requested commit")
    policy = config.get("policy", {}).get("fix_generation", "automatic")
    if policy == "require_approval":
        if not approval_token or not approval_key:
            raise ValueError("this policy requires a signed approval before fix generation")
        verify_and_consume(
            store,
            approval_token,
            approval_key,
            repository,
            fingerprint,
            commit_sha,
            current_sha,
        )
    elif policy != "automatic":
        raise ValueError(f"unsupported fix generation policy: {policy}")

    finding = finding_from_json(row["details_json"])
    owner = str(uuid.uuid4())
    store.acquire_fix_lease(repository, fingerprint, commit_sha, owner)
    agent_root = Path(config.get("_config_dir", root))
    workspaces = agent_root / ".forgewatch" / "workspaces"
    workspaces.mkdir(parents=True, exist_ok=True)
    workspace = workspaces / owner
    added = _git(root, ["worktree", "add", "--detach", str(workspace), commit_sha])
    if added.returncode != 0:
        store.release_fix_lease(repository, fingerprint, owner)
        raise RuntimeError(f"could not create isolated worktree: {redact_text(added.stderr)}")
    try:
        before = []
        if finding.rule_id == SUPPORTED_RULE and finding.locations:
            before = detect_reverse_tabnabbing(workspace / finding.locations[0].path)
        ai_metadata: Optional[Dict[str, Any]] = None
        if use_ai:
            ai_metadata = ai.generate_patch(workspace, finding, config.get("ai", {}))
            patch = ai_metadata.get("patch", "")
            allowed = {location.path for location in finding.locations}
            _validate_patch_scope(patch, allowed)
            applied = _git(workspace, ["apply", "--whitespace=error", "-"], patch)
            if applied.returncode != 0:
                raise ValueError(f"generated patch does not apply cleanly: {redact_text(applied.stderr)}")
            changed_files = sorted(_patch_paths(patch))
        else:
            changed_files = apply_reverse_tabnabbing_fix(workspace, finding)

        diff_process = _git(workspace, ["diff", "--binary", "--", *changed_files])
        patch = diff_process.stdout
        _validate_patch_scope(patch, set(changed_files))
        after = []
        if finding.rule_id == SUPPORTED_RULE and finding.locations:
            after = detect_reverse_tabnabbing(workspace / finding.locations[0].path)
        regression = {
            "check": finding.rule_id,
            "before": "failed" if before else "not_available",
            "after": "passed" if before and not after else "failed",
            "before_matches": before,
            "after_matches": after,
        }
        security_rescan = _security_rescan(workspace, config, finding)
        validation_status = "failed" if (
            regression["after"] != "passed" or security_rescan["status"] == "failed"
        ) else "blocked"
        validation_error = security_rescan.get("error")
        command_results: List[Dict[str, Any]] = []
        if validation_status != "failed" and security_rescan["status"] == "passed":
            try:
                command_results = _container_validation(workspace, root, config.get("execution", {}))
                validation_status = "passed" if all(
                    item["status"] == "passed" for item in command_results
                ) else "failed"
                validation_error = None
            except RuntimeError as error:
                validation_error = str(error)

        artifact = Path(config.get("state", {}).get("artifacts", ".forgewatch/artifacts"))
        if not artifact.is_absolute():
            artifact = agent_root / artifact
        target = artifact / "fixes" / f"{fingerprint}-{commit_sha[:12]}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "change.patch").write_text(patch, encoding="utf-8")
        metadata = {
            "schema_version": 1,
            "repository": repository,
            "finding": fingerprint,
            "rule_id": finding.rule_id,
            "base_commit": commit_sha,
            "created_at": utc_now(),
            "changed_files": changed_files,
            "validation_status": validation_status,
            "regression_check": regression,
            "security_rescan": security_rescan,
            "validation_commands": command_results,
            "validation_error": validation_error,
            "ai": ai_metadata,
            "merge_permitted": False,
        }
        (target / "metadata.json").write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        uncertainty = validation_error or "No remaining validation uncertainty was recorded."
        simple = finding_plain_language(finding)
        changed = ", ".join(f"`{_safe_markdown(path)}`" for path in changed_files)
        scanner_check = security_rescan["status"]
        project_check = {
            "passed": "The configured project checks passed in the isolated container.",
            "failed": "At least one required check failed. This patch is not ready for a pull request.",
            "blocked": "The project checks could not safely run. This patch is not ready for a pull request.",
        }[validation_status]
        body = (
            f"## What Forgewatch found\n\n{_safe_markdown(simple['title'])}\n\n"
            f"{_safe_markdown(simple['why_it_matters'])}\n\n"
            f"## What this patch changes\n\nChanged only {changed}.\n\n"
            f"{_safe_markdown(simple['what_to_do'])}\n\n"
            "## Checks\n\n"
            f"- Before the patch, the focused security check reproduced the problem: {'yes' if regression['before'] == 'failed' else 'no'}.\n"
            f"- After the patch, the focused security check no longer found it: {'yes' if regression['after'] == 'passed' else 'no'}.\n"
            f"- The relevant security scanner reran successfully: {'yes' if scanner_check == 'passed' else 'no'}.\n"
            f"- {_safe_markdown(project_check)}\n\n"
            f"## What still needs review\n\n{_safe_markdown(uncertainty)}\n\n"
            "A person must review this patch. Forgewatch cannot merge it, turn on auto-merge, or deploy it.\n\n"
            f"Technical reference: finding `{_safe_markdown(fingerprint)}` at commit `{_safe_markdown(commit_sha)}`.\n"
        )
        (target / "pr.md").write_text(str(redact_text(body)), encoding="utf-8")
        return target
    finally:
        _git(root, ["worktree", "remove", "--force", str(workspace)])
        store.release_fix_lease(repository, fingerprint, owner)
