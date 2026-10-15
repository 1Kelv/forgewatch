"""Evidence-based advice only. Reading project files never executes project code."""
from __future__ import annotations

import json
import re
import shlex
from pathlib import Path
from typing import Any, Dict, List

from .models import Finding
from .redaction import redact


DISCLAIMER = (
    "These are suggested steps based on the scanned files, not an applied or tested patch. "
    "A version listed by one advisory may still have other issues. Check compatibility and scan again."
)


def _json_file(root: Path, relative: Path) -> Dict[str, Any]:
    try:
        path = (root / relative).resolve()
        path.relative_to(root.resolve())
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            return {}
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, UnicodeError, RuntimeError):
        return {}


def _project(root: Path, location: str) -> tuple:
    # Reject traversal and symlinks that leave the target before looking for manifests.
    try:
        source = (root / location).resolve()
        source.relative_to(root.resolve())
    except (ValueError, OSError, RuntimeError):
        return Path("package.json"), {}
    directory = source.parent
    while directory.is_relative_to(root.resolve()):
        relative = directory.relative_to(root.resolve()) / "package.json"
        manifest = _json_file(root, relative)
        if manifest:
            return relative, manifest
        if directory == root.resolve():
            break
        directory = directory.parent
    return Path("package.json"), {}


def _manager(root: Path, directory: Path, manifest: Dict[str, Any]) -> str:
    declared = str(manifest.get("packageManager", "")).split("@", 1)[0]
    if declared in {"npm", "pnpm", "yarn", "bun"}:
        return declared
    for filename, name in (("pnpm-lock.yaml", "pnpm"), ("yarn.lock", "yarn"), ("bun.lock", "bun"), ("bun.lockb", "bun"), ("package-lock.json", "npm")):
        if (root / directory / filename).is_file():
            return name
    return ""


def _checks(manifest: Dict[str, Any], manager: str) -> List[str]:
    scripts = manifest.get("scripts", {})
    if not isinstance(scripts, dict) or not manager:
        return []
    return [f"{manager} run {name}" for name in ("test", "typecheck", "lint", "build") if isinstance(scripts.get(name), str)]


def enrich_guidance(root: Path, findings: List[Finding]) -> None:
    for item in findings:
        location = item.locations[0] if item.locations else None
        if not location:
            continue
        manifest_path, manifest = _project(root, location.path)
        manager = _manager(root, manifest_path.parent, manifest) if manifest else ""
        basis = [f"Reported location: {location.path}, line {location.start_line}."]
        steps: List[str] = []
        commands: List[str] = []
        dependency = item.dependency
        if item.category == "dependency" and dependency:
            name = str(dependency.get("name", ""))
            version = str(dependency.get("version", ""))
            basis.append(f"The scanned dependency file resolves {name} {version}.")
            if dependency.get("fixed_versions"):
                steps.append(
                    "This advisory lists these releases where this particular issue was fixed: "
                    + ", ".join(dependency["fixed_versions"][:20])
                    + ". These are starting points, not verified upgrade choices. Prefer a compatible, maintained stable release; some listed releases may be older than your version or pre-release builds."
                )
            else:
                steps.append("The checker did not supply a fixed release for this package. Read the linked advisory before choosing an update; do not guess a version.")
            npm_package = dependency.get("ecosystem") == "npm"
            section = next((key for key in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies")
                            if isinstance(manifest.get(key), dict) and name in manifest[key]), None) if npm_package else None
            if section:
                basis.append(f"{manifest_path.as_posix()} lists {name} under {section} as {manifest[section][name]}.")
                steps.append(f"Update {name} in {manifest_path.as_posix()} ({section}), using a release compatible with this project's other packages. Check the package's migration notes if a major-version change is needed.")
            elif npm_package and manifest:
                basis.append(f"{name} is not directly declared in {manifest_path.as_posix()}; it may come through another package or a workspace.")
                lock = _json_file(root, Path(location.path)) if Path(location.path).name == "package-lock.json" else {}
                packages = lock.get("packages", {})
                parents = []
                if isinstance(packages, dict):
                    for path, entry in packages.items():
                        if path and isinstance(entry, dict) and any(isinstance(entry.get(key), dict) and name in entry[key] for key in ("dependencies", "optionalDependencies")):
                            parents.append(path)
                if parents:
                    basis.append("Lockfile entries that depend on it include: " + ", ".join(sorted(parents)[:5]) + ".")
                steps.append(f"Find which dependency brings in {name}. Update that parent package or the relevant workspace manifest, rather than adding an unrelated direct dependency just to hide the warning.")
            else:
                steps.append(f"Use the package manager for {location.path} to update {name} and regenerate the dependency file. Do not hand-edit the resolved version alone.")
            if npm_package and manager:
                # Names are untrusted. Only emit a diagnostic command for valid npm-style names.
                if re.fullmatch(r"(?:@[a-zA-Z0-9_.-]+/)?[a-zA-Z0-9_][a-zA-Z0-9_.-]*", name):
                    verb = "why" if manager in {"yarn", "pnpm"} else "pm ls" if manager == "bun" else "explain"
                    commands.append(f"{manager} {verb} {shlex.quote(name)}" if manager != "bun" else "bun pm ls")
                steps.append(f"Regenerate {location.path} with {manager}, review both the manifest and lockfile changes, and keep unrelated upgrades out of the fix.")
        elif item.category == "secret":
            steps = [
                "Confirm privately whether this is a real credential. Do not paste its value into chat, an issue, or this report.",
                "If real, revoke or rotate it with its provider first; deleting the line does not invalidate it.",
                f"Remove the value from {location.path}, replace it with a secret-store or environment-variable reference, and check whether repository history also needs cleaning.",
            ]
        elif item.rule_id == "forgewatch.javascript.browser.reverse-tabnabbing":
            steps = [
                f'Open {location.path} around line {location.start_line}. On the link using target="_blank", add rel="noopener noreferrer"; preserve any existing rel values.',
                "Confirm the link still opens its intended destination in a new tab, then rerun the scan.",
            ]
        elif item.rule_id == "forgewatch.react.security.dangerously-set-inner-html":
            steps = [
                f"Open {location.path} around line {location.start_line} and trace the value passed into dangerouslySetInnerHTML.",
                "If HTML formatting is not needed, render the value as ordinary React text instead. React will escape it rather than treating it as page markup.",
                "If formatted HTML is required, use a maintained HTML sanitizer before rendering. Do not rely on regular-expression replacements; add tests covering unsafe links and script-like content.",
            ]
        else:
            steps = [f"Review {location.path} around line {location.start_line}.", item.remediation]
        if manifest:
            basis.append(f"Project commands were read from {manifest_path.as_posix()}; no project script was executed.")
        checks = _checks(manifest, manager)
        commands.extend(checks)
        steps.append("After reviewing the change, run the project's checks in a trusted development environment, then scan the same branch again. " + ("Suggested existing commands are below." if checks else "No recognised test command was found here; use the project's documented checks."))
        item.fix_guidance = redact({
            "steps": steps, "basis": basis, "commands": commands,
            "working_directory": manifest_path.parent.as_posix() if manifest else ".",
            "disclaimer": DISCLAIMER,
        })
