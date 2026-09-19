from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from .approvals import issue
from .dashboard import serve_dashboard
from .engine import git_sha, scan, utc_now, verified_default_branch
from .github import publish_pull_request
from .models import SEVERITY_ORDER
from .redaction import redact
from .remediation import SUPPORTED_RULE, prepare_fix
from .reporting import plain_language, write_reports
from .service import serve
from .store import Store
from .webhooks import accept_delivery


def load_config(root: Path, path: str) -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.is_absolute():
        config_path = config_path.resolve()
    with config_path.open(encoding="utf-8") as handle:
        config = json.load(handle)
    if config.get("schema_version") != 1:
        raise ValueError("unsupported configuration schema_version")
    repository = os.environ.get("FORGEWATCH_REPOSITORY")
    if repository:
        config.setdefault("repository", {})["slug"] = repository
    config["_config_dir"] = str(config_path.parent.resolve())
    for scanner in config.get("scanners", {}).values():
        scanner["_config_dir"] = config["_config_dir"]
    return config


def state_path(root: Path, config: Dict[str, Any]) -> Path:
    path = Path(config.get("state", {}).get("database", ".forgewatch/state.db"))
    return path if path.is_absolute() else Path(config["_config_dir"]) / path


def _is_default_ref(ref: str, default_branch: str) -> bool:
    return ref in {default_branch, f"refs/heads/{default_branch}"}


def command_scan(args: argparse.Namespace, root: Path, config: Dict[str, Any], store: Store) -> int:
    result = scan(root, config, args.trigger, args.ref)
    result.default_branch_verified = verified_default_branch(
        root, config["repository"]["default_branch"], args.ref, result.commit_sha
    )
    store.record_scan(result, result.default_branch_verified)
    report_dir = Path(args.report_dir)
    if not report_dir.is_absolute():
        report_dir = Path(config["_config_dir"]) / report_dir
    write_reports(result, report_dir)
    prepared = []
    preparation_errors = []
    if args.prepare_fixes and config.get("policy", {}).get("fix_generation", "automatic") == "automatic":
        for finding in result.findings:
            if finding.rule_id != SUPPORTED_RULE or finding.status == "dismissed":
                continue
            try:
                prepared.append(
                    str(prepare_fix(root, config, store, finding.fingerprint, result.commit_sha))
                )
            except (ValueError, RuntimeError) as error:
                preparation_errors.append({"finding": finding.fingerprint, "error": str(error)})
    simple = plain_language(result)
    summary = {
        "result": simple["headline"],
        "next_step": simple["next_step"],
        "scan_id": result.scan_id,
        "status": result.status,
        "commit_sha": result.commit_sha,
        "findings": len(result.findings),
        "prepared_fixes": prepared,
        "fix_errors": preparation_errors,
        "report_dir": str(report_dir),
    }
    print(json.dumps(redact(summary), indent=2))
    if result.status == "incomplete":
        return 2
    threshold = SEVERITY_ORDER[args.fail_on]
    if any(SEVERITY_ORDER[finding.severity] >= threshold for finding in result.findings):
        return 1
    return 0


def command_findings(config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    statuses = tuple(args.status) if args.status else ("open", "dismissed")
    rows = store.findings(config["repository"]["slug"], statuses)
    values = []
    for row in rows:
        value = dict(row)
        value["details"] = json.loads(value.pop("details_json"))
        values.append(value)
    print(json.dumps(redact(values), indent=2, sort_keys=True))
    return 0


def command_dismiss(config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    store.dismiss(config["repository"]["slug"], args.finding, args.reason, args.actor, utc_now())
    print(f"Dismissed {args.finding} with a recorded reason.")
    return 0


def command_approve(root: Path, config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    key = os.environ.get("SECURITY_APPROVAL_KEY")
    if not key:
        raise ValueError("SECURITY_APPROVAL_KEY is required to authenticate an approval")
    repository = config["repository"]["slug"]
    row = store.get_finding(repository, args.finding)
    if row is None or not row["present"] or row["last_seen_commit"] != args.commit:
        raise ValueError("finding is not present at the requested commit")
    if git_sha(root) != args.commit:
        raise ValueError("approval target is stale relative to the checkout")
    token = issue(store, key, repository, args.finding, args.commit, args.actor, args.ttl)
    print(token)
    return 0


def command_prepare(root: Path, config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    target = prepare_fix(
        root,
        config,
        store,
        args.finding,
        args.commit,
        approval_token=args.approval,
        approval_key=os.environ.get("SECURITY_APPROVAL_KEY"),
        use_ai=args.ai,
    )
    print(target)
    return 0


def command_publish(root: Path, config: Dict[str, Any], args: argparse.Namespace) -> int:
    url = publish_pull_request(root, config, Path(args.artifact).resolve())
    print(url)
    return 0


def command_webhook(store: Store, args: argparse.Namespace) -> int:
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET")
    if not secret:
        raise ValueError("GITHUB_WEBHOOK_SECRET is required")
    body = Path(args.payload).read_bytes()
    accept_delivery(store, body, args.signature, secret, args.delivery_id, args.event)
    print("Webhook accepted.")
    return 0


def command_serve(config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    serve(config, store, args.host, args.port)
    return 0


def command_dashboard(config: Dict[str, Any], store: Store, args: argparse.Namespace) -> int:
    serve_dashboard(
        config,
        store,
        host=args.host,
        port=args.port,
        state_file=args.state_file,
        open_browser=not args.no_open,
    )
    return 0


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(prog="forgewatch", description="Scan, track and prepare reviewable security fixes.")
    value.add_argument("--root", default=".", help="repository checkout")
    value.add_argument("--config", default=".forgewatch.json")
    value.add_argument("--repository", help="portable repository identifier, for example gitlab.example/team/service")
    value.add_argument("--default-branch", help="override the configured default branch for this target")
    commands = value.add_subparsers(dest="command", required=True)

    scan_parser = commands.add_parser("scan")
    scan_parser.add_argument("--trigger", choices=("manual", "push", "pull_request", "schedule", "webhook"), default="manual")
    scan_parser.add_argument("--ref", default="main")
    scan_parser.add_argument("--report-dir", default=".forgewatch/artifacts/latest")
    scan_parser.add_argument("--fail-on", choices=tuple(SEVERITY_ORDER), default="high")
    scan_parser.add_argument("--prepare-fixes", action="store_true")

    findings_parser = commands.add_parser("findings")
    findings_parser.add_argument("--status", action="append", choices=("open", "dismissed", "resolved"))

    dismiss_parser = commands.add_parser("dismiss")
    dismiss_parser.add_argument("--finding", required=True)
    dismiss_parser.add_argument("--reason", required=True)
    dismiss_parser.add_argument("--actor", required=True)

    approval_parser = commands.add_parser("approve-fix")
    approval_parser.add_argument("--finding", required=True)
    approval_parser.add_argument("--commit", required=True)
    approval_parser.add_argument("--actor", required=True)
    approval_parser.add_argument("--ttl", type=int, default=900)

    prepare_parser = commands.add_parser("prepare-fix")
    prepare_parser.add_argument("--finding", required=True)
    prepare_parser.add_argument("--commit", required=True)
    prepare_parser.add_argument("--approval")
    prepare_parser.add_argument("--ai", action="store_true")

    publish_parser = commands.add_parser("publish-pr")
    publish_parser.add_argument("--artifact", required=True)

    webhook_parser = commands.add_parser("accept-webhook")
    webhook_parser.add_argument("--payload", required=True)
    webhook_parser.add_argument("--signature", required=True)
    webhook_parser.add_argument("--delivery-id", required=True)
    webhook_parser.add_argument("--event", required=True)
    serve_parser = commands.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    dashboard_parser = commands.add_parser("dashboard", help="open the local Forgewatch dashboard")
    dashboard_parser.add_argument("--host", default="127.0.0.1")
    dashboard_parser.add_argument("--port", type=int, default=8790)
    dashboard_parser.add_argument("--state-file", default=".forgewatch/dashboard.json")
    dashboard_parser.add_argument("--no-open", action="store_true", help="do not open a browser automatically")
    return value


def main(argv: Optional[List[str]] = None) -> int:
    args = parser().parse_args(argv)
    root = Path(args.root).resolve()
    try:
        config = load_config(root, args.config)
        if args.repository:
            config.setdefault("repository", {})["slug"] = args.repository
        if args.default_branch:
            config.setdefault("repository", {})["default_branch"] = args.default_branch
        store = Store(state_path(root, config))
        try:
            if args.command == "scan":
                return command_scan(args, root, config, store)
            if args.command == "findings":
                return command_findings(config, store, args)
            if args.command == "dismiss":
                return command_dismiss(config, store, args)
            if args.command == "approve-fix":
                return command_approve(root, config, store, args)
            if args.command == "prepare-fix":
                return command_prepare(root, config, store, args)
            if args.command == "publish-pr":
                return command_publish(root, config, args)
            if args.command == "accept-webhook":
                return command_webhook(store, args)
            if args.command == "serve":
                return command_serve(config, store, args)
            if args.command == "dashboard":
                return command_dashboard(config, store, args)
            raise ValueError(f"unknown command: {args.command}")
        finally:
            store.close()
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"forgewatch: {redact(error)}", file=sys.stderr)
        return 2
