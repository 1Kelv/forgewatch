from __future__ import annotations

import json
import os
import ssl
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from .models import Finding, Location, ScannerRun
from .redaction import REDACTED, redact_text


SUPPORTED_LOCKFILES = {
    "bun.lock", "Cargo.lock", "composer.lock", "conan.lock", "Gemfile.lock", "go.mod",
    "mix.lock", "package-lock.json", "packages.lock.json", "Pipfile.lock", "pdm.lock",
    "pnpm-lock.yaml", "poetry.lock", "pubspec.lock", "pylock.toml", "renv.lock",
    "requirements.txt", "stack.yaml.lock", "uv.lock", "yarn.lock",
}


def _run(command: List[str], cwd: Path, timeout: int) -> Tuple[int, str, str, int]:
    started = time.monotonic()
    env = {
        key: value
        for key, value in os.environ.items()
        if key not in {"GITHUB_TOKEN", "GH_TOKEN", "OPENAI_API_KEY", "SECURITY_APPROVAL_KEY"}
    }
    env.setdefault("SEMGREP_LOG_FILE", str(Path(tempfile.gettempdir()) / "forgewatch-semgrep.log"))
    env.setdefault("SEMGREP_ENABLE_VERSION_CHECK", "0")
    default_ca_file = ssl.get_default_verify_paths().cafile
    if default_ca_file:
        env.setdefault("SSL_CERT_FILE", default_ca_file)
    else:
        try:
            import certifi

            env.setdefault("SSL_CERT_FILE", certifi.where())
        except ImportError:
            pass
    try:
        process = subprocess.run(
            command,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return (
            process.returncode,
            redact_text(process.stdout),
            redact_text(process.stderr),
            int((time.monotonic() - started) * 1000),
        )
    except FileNotFoundError:
        return 127, "", f"scanner executable not found: {command[0]}", int((time.monotonic() - started) * 1000)
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else (error.stdout or "")
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else (error.stderr or "")
        return 124, redact_text(stdout), redact_text(stderr or f"timed out after {timeout}s"), int(
            (time.monotonic() - started) * 1000
        )


def _version(binary: str, cwd: Path, args: Iterable[str] = ("--version",)) -> str:
    code, stdout, stderr, _ = _run([binary, *args], cwd, 20)
    if code != 0:
        return "unavailable"
    output = (stdout or stderr).strip().splitlines()
    return output[0][:160] if output else "unknown"


def _json(stdout: str) -> Dict[str, Any]:
    try:
        return json.loads(stdout or "{}")
    except json.JSONDecodeError:
        first = stdout.find("{")
        last = stdout.rfind("}")
        if first >= 0 and last > first:
            return json.loads(stdout[first : last + 1])
        raise


def _relative(root: Path, value: str) -> str:
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def run_semgrep(root: Path, config: Dict[str, Any]) -> ScannerRun:
    binary = config.get("binary", "semgrep")
    version = _version(binary, root)
    config_dir = Path(config.get("_config_dir", root))
    rule_path = (config_dir / config.get("config", "rules/semgrep.yml")).resolve()
    command = [
        binary,
        "scan",
        "--config",
        str(rule_path),
        "--json",
        "--error",
        "--disable-version-check",
        "--no-rewrite-rule-ids",
        "--metrics",
        "off",
        "--timeout",
        str(config.get("per_rule_timeout_seconds", 30)),
        "--exclude",
        "node_modules",
        "--exclude",
        "dist",
        "--exclude",
        "fixtures",
        ".",
    ]
    code, stdout, stderr, duration = _run(command, root, int(config.get("timeout_seconds", 300)))
    if code not in {0, 1}:
        return ScannerRun("semgrep", version, "failed", "TypeScript, TSX, JavaScript and JSX source", duration, error=stderr or stdout)
    try:
        payload = _json(stdout)
    except (json.JSONDecodeError, ValueError) as error:
        return ScannerRun("semgrep", version, "failed", "TypeScript, TSX, JavaScript and JSX source", duration, error=f"invalid JSON output: {error}")

    findings = []
    for item in payload.get("results", []):
        extra = item.get("extra", {})
        metadata = extra.get("metadata", {}) or {}
        start, end = item.get("start", {}), item.get("end", {})
        cwe = metadata.get("cwe", [])
        if isinstance(cwe, str):
            cwe = [cwe]
        path = _relative(root, item.get("path", "unknown"))
        rule_id = item.get("check_id", "semgrep.unknown")
        message = extra.get("message", rule_id)
        findings.append(
            Finding(
                scanner="semgrep",
                rule_id=rule_id,
                category="code",
                severity=extra.get("severity", "warning"),
                confidence=str(metadata.get("confidence", "medium")).lower(),
                title=message,
                explanation=message,
                remediation=metadata.get("remediation", "Review the data flow and apply the rule's safe alternative."),
                locations=[
                    Location(
                        path=path,
                        start_line=int(start.get("line", 1)),
                        end_line=int(end.get("line", start.get("line", 1))),
                        start_column=int(start.get("col", 1)),
                        end_column=int(end.get("col", 1)),
                    )
                ],
                evidence=(extra.get("lines") if extra.get("lines") not in {None, "", "requires login"} else f"Semgrep matched {rule_id} at {path}:{start.get('line', 1)}"),
                cwes=list(cwe),
                references=list(metadata.get("references", [])),
            )
        )
    paths = payload.get("paths", {}) or {}
    scanned_count = len(paths.get("scanned", []) or [])
    skipped_count = len(paths.get("skipped", []) or [])
    if scanned_count == 0:
        return ScannerRun(
            "semgrep", version, "not_applicable",
            "0 JavaScript, TypeScript, JSX or TSX files found",
            duration,
        )
    return ScannerRun(
        "semgrep",
        version,
        "findings" if findings else "passed",
        f"TypeScript, TSX, JavaScript and JSX source using committed rules; {scanned_count} files scanned, {skipped_count} skipped",
        duration,
        findings=findings,
    )


def _osv_severity(vulnerability: Dict[str, Any]) -> str:
    database = vulnerability.get("database_specific", {}) or {}
    named = str(database.get("severity", "")).lower()
    if named in {"low", "moderate", "medium", "high", "critical"}:
        return "medium" if named == "moderate" else named
    scores = vulnerability.get("severity", []) or []
    for score in scores:
        value = str(score.get("score", ""))
        if "/" in value:
            try:
                number = float(value.split("/")[-1])
            except ValueError:
                continue
            if number >= 9:
                return "critical"
            if number >= 7:
                return "high"
            if number >= 4:
                return "medium"
            return "low"
    return "medium"


def run_osv(root: Path, config: Dict[str, Any]) -> ScannerRun:
    binary = config.get("binary", "osv-scanner")
    version = _version(binary, root)
    command = [binary, "scan", "source", "--format", "json", "--recursive", "."]
    code, stdout, stderr, duration = _run(command, root, int(config.get("timeout_seconds", 300)))
    if code not in {0, 1}:
        return ScannerRun("osv-scanner", version, "failed", "supported manifests and lockfiles, including package-lock.json", duration, error=stderr or stdout)
    try:
        payload = _json(stdout)
    except (json.JSONDecodeError, ValueError) as error:
        return ScannerRun("osv-scanner", version, "failed", "supported manifests and lockfiles, including package-lock.json", duration, error=f"invalid JSON output: {error}")

    lockfiles = [
        path for path in root.rglob("*")
        if path.is_file()
        and path.name in SUPPORTED_LOCKFILES
        and not {".git", ".forgewatch", "node_modules", ".venv"}.intersection(path.parts)
    ]
    if not lockfiles:
        return ScannerRun(
            "osv-scanner", version, "not_applicable", "0 supported dependency manifests or lockfiles", duration,
        )

    findings = []
    for result in payload.get("results", []):
        source = result.get("source", {}) or {}
        path = _relative(root, source.get("path") or source.get("target") or "package-lock.json")
        for package_entry in result.get("packages", []):
            package = package_entry.get("package", {}) or {}
            package_name = package.get("name", "unknown package")
            package_version = package.get("version", "unknown version")
            vulnerabilities = package_entry.get("vulnerabilities", []) or []
            for vulnerability in vulnerabilities:
                vulnerability_id = vulnerability.get("id", "OSV-UNKNOWN")
                summary = vulnerability.get("summary") or vulnerability.get("details") or vulnerability_id
                aliases = vulnerability.get("aliases", []) or []
                references = [item.get("url") for item in vulnerability.get("references", []) if item.get("url")]
                findings.append(
                    Finding(
                        scanner="osv-scanner",
                        rule_id=f"{vulnerability_id}:{package_name}",
                        category="dependency",
                        severity=_osv_severity(vulnerability),
                        confidence="high",
                        title=f"{package_name} {package_version}: {summary}",
                        explanation=f"The lockfile resolves {package_name} {package_version}, which is affected by {vulnerability_id}.",
                        remediation="Upgrade to a fixed compatible version, regenerate the lockfile, and rerun tests and OSV-Scanner.",
                        locations=[Location(path=path)],
                        evidence=f"Affected dependency: {package_name}@{package_version}; advisory: {vulnerability_id}",
                        references=references,
                        source_ids=[f"osv-scanner:{vulnerability_id}", *[f"osv-scanner:{alias}" for alias in aliases]],
                    )
                )
    return ScannerRun(
        "osv-scanner",
        version,
        "findings" if findings else "passed",
        f"{len(lockfiles)} supported dependency manifest or lockfile(s)",
        duration,
        findings=findings,
    )


def run_gitleaks(root: Path, config: Dict[str, Any]) -> ScannerRun:
    binary = config.get("binary", "gitleaks")
    version = _version(binary, root, ("version",))
    with tempfile.TemporaryDirectory(prefix="forgewatch-gitleaks-") as directory:
        report = Path(directory) / "gitleaks.json"
        mode = "git" if config.get("history", False) else "dir"
        command = [
            binary,
            mode,
            "--no-banner",
            "--redact=100",
            "--report-format",
            "json",
            "--report-path",
            str(report),
            str(root),
        ]
        code, stdout, stderr, duration = _run(command, root, int(config.get("timeout_seconds", 300)))
        if code not in {0, 1}:
            return ScannerRun("gitleaks", version, "failed", "working tree" if mode == "dir" else "Git history", duration, error=stderr or stdout)
        try:
            payload = json.loads(report.read_text(encoding="utf-8")) if report.exists() else []
        except (json.JSONDecodeError, OSError) as error:
            return ScannerRun("gitleaks", version, "failed", "working tree" if mode == "dir" else "Git history", duration, error=f"invalid JSON report: {error}")

    findings = []
    for item in payload:
        path = _relative(root, item.get("File", "unknown"))
        rule_id = item.get("RuleID", "gitleaks.unknown")
        findings.append(
            Finding(
                scanner="gitleaks",
                rule_id=rule_id,
                category="secret",
                severity="high",
                confidence="high",
                title=item.get("Description", "Potential exposed secret"),
                explanation="A credential-like value was detected. The value is deliberately omitted from every agent report.",
                remediation="Validate out of band, revoke or rotate if real, remove it from the working tree and history, then rescan.",
                locations=[
                    Location(
                        path=path,
                        start_line=int(item.get("StartLine", 1)),
                        end_line=int(item.get("EndLine", item.get("StartLine", 1))),
                        start_column=int(item.get("StartColumn", 1)),
                        end_column=int(item.get("EndColumn", 1)),
                    )
                ],
                evidence=f"Gitleaks rule {rule_id} matched at {path}:{item.get('StartLine', 1)}; value={REDACTED}",
            )
        )
    return ScannerRun(
        "gitleaks",
        version,
        "findings" if findings else "passed",
        "working tree" if mode == "dir" else "complete Git history reachable from checkout",
        duration,
        findings=findings,
    )


SCANNERS = {"semgrep": run_semgrep, "osv": run_osv, "gitleaks": run_gitleaks}


def run_configured_scanner(name: str, root: Path, config: Dict[str, Any]) -> ScannerRun:
    if not config.get("enabled", True):
        return ScannerRun(name, "not-run", "skipped", "none", 0, error="disabled by configuration")
    return SCANNERS[name](root, config)
