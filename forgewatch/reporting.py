from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding, SEVERITY_ORDER, ScanResult
from .redaction import redact


PRIORITY = {
    "critical": ("Urgent", "Review immediately. This may have a serious security impact."),
    "high": ("Important", "Review and fix soon."),
    "medium": ("Needs attention", "Plan a fix after the important items."),
    "low": ("Lower priority", "Review when practical."),
    "info": ("For awareness", "No immediate action is normally required."),
}

SCAN_STATUS = {
    "clean": "No supported problems found",
    "findings": "Problems need review",
    "incomplete": "The scan could not finish",
}

CHECK_NAMES = {
    "semgrep": "Code safety checks",
    "osv-scanner": "Dependency version checks",
    "osv": "Dependency version checks",
    "gitleaks": "Exposed secret checks",
}

CHECK_STATUS = {
    "passed": "Finished, with no matching problem",
    "findings": "Finished and found items to review",
    "not_applicable": "Not applicable because no supported files were found",
    "failed": "Could not finish",
    "skipped": "Did not run",
}

VALIDATION = {
    "not_attempted": "Not tested yet",
    "passed": "The proposed fix passed its checks",
    "failed": "The proposed fix failed a check",
    "blocked": "The checks could not safely run",
}


def _location(finding: Finding) -> str:
    if not finding.locations:
        return "Location not available"
    first = finding.locations[0]
    return f"{first.path}, line {first.start_line}"


def _plain_title(finding: Finding) -> str:
    if finding.category == "dependency":
        package = finding.title.split(":", 1)[0].strip()
        lowered = finding.title.lower()
        if any(term in lowered for term in ("denial of service", "memory growth", "loop indefinitely", "termination")):
            effect = "it can make a tool or app stop responding"
        elif any(term in lowered for term in ("path traversal", "file disclosure", "deny bypass")):
            effect = "it may expose files that should stay private"
        elif "command injection" in lowered:
            effect = "it may allow an unsafe command to run"
        elif "hash disclosure" in lowered:
            effect = "it may expose login information"
        else:
            effect = "a known security issue affects this version"
        return f"Update {package} because {effect}"
    if finding.category == "secret":
        return f"Check a possible exposed secret in {_location(finding)}"
    if finding.rule_id == "pervigil.javascript.browser.reverse-tabnabbing":
        return "A new-tab link could let another site control the original page"
    if finding.rule_id == "pervigil.react.security.dangerously-set-inner-html":
        return "Untrusted page content could be treated as executable HTML"
    return finding.title


def _why_it_matters(finding: Finding) -> str:
    if finding.category == "dependency":
        return (
            "This exact package version appears in the repository's dependency lockfile and is listed in a "
            "public security database. That does not prove the application can be attacked through it. Check "
            "whether the package is used in production, development, or only during builds."
        )
    if finding.category == "secret":
        return (
            "If the match is a real password, token, or key, someone with repository access may be able to use it. "
            "Confirm it through an approved private channel and replace it if it is real."
        )
    if finding.rule_id == "pervigil.javascript.browser.reverse-tabnabbing":
        return (
            "A page opened in a new tab may be able to redirect or change the page that opened it. Adding a small "
            "link safety setting prevents that behaviour."
        )
    return finding.explanation


def _what_to_do(finding: Finding) -> str:
    if finding.category == "dependency":
        return (
            "Find the nearest compatible package version that includes the security fix, update the dependency "
            "lockfile, then run the application's tests and build."
        )
    if finding.category == "secret":
        return (
            "If the value is real, revoke or rotate it first. Then remove it from the current files and, when "
            "necessary, from Git history."
        )
    if finding.rule_id == "pervigil.javascript.browser.reverse-tabnabbing":
        return 'Add rel="noopener noreferrer" to the link, then rerun the code safety check and project tests.'
    return finding.remediation


def finding_plain_language(finding: Finding) -> Dict[str, str]:
    return {
        "title": _plain_title(finding),
        "priority": PRIORITY[finding.severity][0],
        "where": _location(finding),
        "why_it_matters": _why_it_matters(finding),
        "what_to_do": _what_to_do(finding),
        "fix_check": VALIDATION.get(finding.validation_status, finding.validation_status),
    }


def _safe_markdown(value: Any) -> str:
    return (
        str(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace("`", "'")
        .replace("|", "\\|")
        .replace("\r", " ")
        .replace("\n", " ")
    )


def _priority_counts(result: ScanResult) -> str:
    counts: Dict[str, int] = {}
    for finding in result.findings:
        counts[finding.severity] = counts.get(finding.severity, 0) + 1
    wording = {
        "critical": ("urgent item", "urgent items"),
        "high": ("important item", "important items"),
        "medium": ("item needing attention", "items needing attention"),
        "low": ("lower-priority item", "lower-priority items"),
        "info": ("information-only item", "information-only items"),
    }
    parts = []
    for severity in sorted(PRIORITY, key=SEVERITY_ORDER.get, reverse=True):
        count = counts.get(severity, 0)
        if count:
            noun = wording[severity][0 if count == 1 else 1]
            parts.append(f"{count} {noun}")
    return ", ".join(parts)


def _plain_coverage(scanner: str, coverage: str) -> str:
    if scanner == "semgrep":
        counts = re.search(r"(\d+) files scanned, (\d+) skipped", coverage)
        if counts:
            return f"{counts.group(1)} JavaScript or TypeScript files; {counts.group(2)} files were skipped"
        return "JavaScript and TypeScript source files"
    if scanner in {"osv", "osv-scanner"}:
        count = re.search(r"(\d+) supported", coverage)
        return (
            f"{count.group(1)} file that records exact package versions"
            if count and count.group(1) == "1"
            else f"{count.group(1)} files that record exact package versions"
            if count
            else "Files that record exact package versions"
        )
    if scanner == "gitleaks":
        return "Current repository files, looking for passwords, tokens, and keys"
    return coverage


def plain_language(result: ScanResult) -> Dict[str, Any]:
    if result.status == "incomplete":
        next_step = "Fix the checks that did not run, then scan again. Do not treat this result as an all-clear."
    elif result.findings:
        next_step = "Review the urgent and important items first. Confirm real-world impact before changing code."
    else:
        next_step = "No supported problem was found. This is not a guarantee that the repository has no security issues."
    return {
        "headline": SCAN_STATUS.get(result.status, result.status),
        "summary": (
            f"Forgewatch recorded {_priority_counts(result)} for review."
            if result.findings
            else "Forgewatch recorded no items for review."
        ),
        "next_step": next_step,
        "severity_guide": {severity: {"label": value[0], "meaning": value[1]} for severity, value in PRIORITY.items()},
        "findings": {
            finding.fingerprint: finding_plain_language(finding)
            for finding in result.findings
        },
    }


def markdown(result: ScanResult) -> str:
    simple = plain_language(result)
    lines: List[str] = [
        "# Forgewatch security report",
        "",
        f"## {simple['headline']}",
        "",
        simple["summary"],
        "",
        simple["next_step"],
        "",
        "### What was scanned",
        "",
        f"- Repository: `{_safe_markdown(result.repository)}`",
        f"- Exact version: `{_safe_markdown(result.commit_sha)}`",
        f"- Started by: `{_safe_markdown(result.trigger)}` on `{_safe_markdown(result.ref)}`",
        f"- The files had no local changes: {'yes' if result.worktree_clean else 'no'}",
        f"- This was confirmed as the latest default branch version: {'yes' if result.default_branch_verified else 'no'}",
        "",
        "### Priority guide",
        "",
        "- **Urgent:** review immediately.",
        "- **Important:** review and fix soon.",
        "- **Needs attention:** plan a fix after important items.",
        "- **Lower priority:** review when practical.",
        "",
        "## Checks that ran",
        "",
        "| Check | Result | What it checked | Tool version |",
        "|---|---|---|---|",
    ]
    for run in result.scanner_runs:
        coverage = _safe_markdown(_plain_coverage(run.scanner, run.coverage))
        name = _safe_markdown(CHECK_NAMES.get(run.scanner, run.scanner))
        status = _safe_markdown(CHECK_STATUS.get(run.status, run.status))
        lines.append(f"| {name} | {status} | {coverage} | {_safe_markdown(run.version)} |")
        if run.error:
            lines.extend(["", f"> **Why {name.lower()} did not finish:** {_safe_markdown(run.error[:500])}"])
    lines.extend(["", "<details>", "<summary>Exact technical coverage</summary>", ""])
    for run in result.scanner_runs:
        lines.append(f"- {_safe_markdown(run.scanner)}: {_safe_markdown(run.coverage)}")
    lines.extend(["", "</details>"])
    lines.extend(["", "## Items to review", ""])
    if not result.findings:
        if result.status == "clean":
            lines.append(
                "The completed checks did not find a problem they are designed to detect. Other issue types may still exist."
            )
        else:
            lines.append("No item is listed because one or more checks did not finish. Run the scan again after fixing that problem.")
    for finding in sorted(result.findings, key=lambda item: (-SEVERITY_ORDER[item.severity], item.fingerprint)):
        label, meaning = PRIORITY[finding.severity]
        confidence = finding.confidence.capitalize()
        origin = "Automated scanner, not an AI guess" if finding.origin == "scanner" else "AI suggestion, not a confirmed scanner result"
        lines.extend(
            [
                f"### {label}: {_safe_markdown(_plain_title(finding))}",
                "",
                f"- **Priority:** {label}. {meaning}",
                f"- **Confidence:** {confidence}",
                f"- **Where:** `{_safe_markdown(_location(finding))}`",
                f"- **Fix check:** {_safe_markdown(VALIDATION.get(finding.validation_status, finding.validation_status))}",
                f"- **Found by:** {origin}",
                "",
                "**Why this matters**",
                "",
                _safe_markdown(_why_it_matters(finding)),
                "",
                "**What to do**",
                "",
                _safe_markdown(_what_to_do(finding)),
                "",
                "<details>",
                "<summary>Technical details for maintainers</summary>",
                "",
                f"- Finding ID: `{_safe_markdown(finding.fingerprint)}`",
                f"- Scanner rule or advisory: `{_safe_markdown(', '.join(finding.source_ids))}`",
                f"- Original scanner message: {_safe_markdown(finding.title)}",
                f"- Scanner evidence: {_safe_markdown(finding.evidence)}",
                "",
                "</details>",
                "",
            ]
        )
    return str(redact("\n".join(lines))) + "\n"


def write_reports(result: ScanResult, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    payload = result.to_dict()
    payload["plain_language"] = plain_language(result)
    payload = redact(payload)
    (directory / "scan.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (directory / "scan.md").write_text(markdown(result), encoding="utf-8")
