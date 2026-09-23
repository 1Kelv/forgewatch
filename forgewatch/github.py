from __future__ import annotations

import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List

from .redaction import redact_text


BRANCH_COMPONENT = re.compile(r"[^a-zA-Z0-9._-]+")


def _run(args: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True, check=False)


def publish_pull_request(root: Path, config: Dict[str, Any], artifact: Path) -> str:
    """Publish a validated patch as a PR. Deliberately provides no merge operation."""
    gh = shutil.which("gh")
    if not gh:
        raise RuntimeError("GitHub CLI is required in the credential-bearing controller environment")
    metadata = json.loads((artifact / "metadata.json").read_text(encoding="utf-8"))
    if metadata.get("validation_status") != "passed":
        raise ValueError("only a fully validated patch can be published")
    repository = config["repository"]["slug"]
    if metadata.get("repository") != repository:
        raise ValueError("artifact belongs to a different repository")
    default_branch = config["repository"]["default_branch"]
    remote = _run(
        [gh, "api", f"repos/{repository}/git/ref/heads/{default_branch}", "--jq", ".object.sha"], root
    )
    if remote.returncode != 0:
        raise RuntimeError(f"could not recheck the default branch: {redact_text(remote.stderr)}")
    base_commit = metadata["base_commit"]
    if remote.stdout.strip() != base_commit:
        raise ValueError("the default branch changed after validation; rescan and regenerate the patch")
    fingerprint = metadata["finding"]
    branch = "forgewatch/" + BRANCH_COMPONENT.sub("-", fingerprint)[:40] + "-" + base_commit[:8]
    with tempfile.TemporaryDirectory(prefix="forgewatch-pr-") as directory:
        workspace = Path(directory) / "repo"
        added = _run(["git", "worktree", "add", "--detach", str(workspace), base_commit], root)
        if added.returncode != 0:
            raise RuntimeError(f"could not create PR worktree: {redact_text(added.stderr)}")
        try:
            applied = subprocess.run(
                ["git", "apply", "--whitespace=error", str((artifact / "change.patch").resolve())],
                cwd=str(workspace), capture_output=True, text=True, check=False
            )
            if applied.returncode != 0:
                raise RuntimeError(f"validated patch no longer applies: {redact_text(applied.stderr)}")
            for command in (
                ["git", "switch", "-c", branch],
                ["git", "add", "--", *metadata["changed_files"]],
                ["git", "-c", "user.name=Forgewatch", "-c", "user.email=forgewatch@users.noreply.github.com", "commit", "-m", f"security: remediate {fingerprint}"],
                ["git", "push", "origin", f"HEAD:refs/heads/{branch}"],
            ):
                result = _run(command, workspace)
                if result.returncode != 0:
                    raise RuntimeError(f"PR publication failed: {redact_text(result.stderr)}")
            title = f"security: remediate {metadata['rule_id']}"
            created = _run(
                [
                    gh,
                    "pr",
                    "create",
                    "--repo",
                    repository,
                    "--base",
                    default_branch,
                    "--head",
                    branch,
                    "--title",
                    title[:240],
                    "--body-file",
                    str((artifact / "pr.md").resolve()),
                ],
                workspace,
            )
            if created.returncode != 0:
                raise RuntimeError(f"GitHub rejected the pull request: {redact_text(created.stderr)}")
            return created.stdout.strip()
        finally:
            _run(["git", "worktree", "remove", "--force", str(workspace)], root)
