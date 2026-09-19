from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from .engine import git_sha, scan, verified_default_branch
from .models import SEVERITY_ORDER
from .reporting import CHECK_NAMES, CHECK_STATUS, plain_language, write_reports
from .store import Store


FREQUENCIES = {
    "manual": ("Manual only", None),
    "every_6_hours": ("Every 6 hours", 6 * 60 * 60),
    "daily": ("Every day", 24 * 60 * 60),
    "weekly": ("Every week", 7 * 24 * 60 * 60),
}


def _git(root: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments], cwd=str(root), capture_output=True, text=True, check=False
    )
    return process.stdout.strip() if process.returncode == 0 else ""


def _repository_name(root: Path) -> str:
    remote = _git(root, "remote", "get-url", "origin")
    if remote:
        value = remote.removesuffix(".git")
        if value.startswith("git@") and ":" in value:
            value = value.split(":", 1)[1]
        elif "://" in value:
            value = urlparse(value).path.strip("/")
        if value.count("/") >= 1:
            return value
    return f"local/{root.name}"


def _default_branch(root: Path) -> str:
    remote_head = _git(root, "symbolic-ref", "--short", "refs/remotes/origin/HEAD")
    if remote_head.startswith("origin/"):
        return remote_head.split("/", 1)[1]
    current = _git(root, "branch", "--show-current")
    return current or "main"


def _utc_timestamp(value: Optional[float] = None) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(value or time.time()))


class DashboardController:
    def __init__(self, config: Dict[str, Any], store: Store, state_file: Path):
        self.config = config
        self.store = store
        self.state_file = state_file
        self.lock = threading.RLock()
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.stop_event = threading.Event()
        self.scheduler: Optional[threading.Thread] = None
        self.state = self._load()

    def _load(self) -> Dict[str, Any]:
        if not self.state_file.exists():
            return {"schema_version": 1, "repositories": []}
        try:
            value = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"dashboard settings could not be read: {error}") from error
        if value.get("schema_version") != 1 or not isinstance(value.get("repositories"), list):
            raise ValueError("dashboard settings use an unsupported format")
        return value

    def _save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
        temporary.write_text(json.dumps(self.state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.state_file)

    def start(self) -> None:
        if self.scheduler is not None:
            return
        self.scheduler = threading.Thread(target=self._schedule_loop, name="forgewatch-scheduler", daemon=True)
        self.scheduler.start()

    def close(self) -> None:
        self.stop_event.set()
        if self.scheduler is not None:
            self.scheduler.join(timeout=3)

    def _find(self, repository_id: str) -> Dict[str, Any]:
        for repository in self.state["repositories"]:
            if repository["id"] == repository_id:
                return repository
        raise KeyError("repository was not found")

    def add_repository(self, value: Dict[str, Any]) -> Dict[str, Any]:
        raw_path = str(value.get("path", "")).strip()
        if not raw_path:
            raise ValueError("Enter the folder containing the repository.")
        root = Path(raw_path).expanduser().resolve()
        if not root.is_dir():
            raise ValueError("That repository folder does not exist.")
        git_sha(root)
        slug = str(value.get("slug", "")).strip() or _repository_name(root)
        if len(slug) > 255 or not re.fullmatch(r"[A-Za-z0-9._@:/-]+", slug):
            raise ValueError("Repository name contains unsupported characters.")
        default_branch = str(value.get("default_branch", "")).strip() or _default_branch(root)
        if len(default_branch) > 255 or not re.fullmatch(r"[A-Za-z0-9._/-]+", default_branch):
            raise ValueError("Default branch contains unsupported characters.")
        frequency = str(value.get("frequency", "manual"))
        if frequency not in FREQUENCIES:
            raise ValueError("Choose one of the available scan frequencies.")
        repository_id = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:12]
        with self.lock:
            if any(item["id"] == repository_id for item in self.state["repositories"]):
                raise ValueError("That repository is already on the dashboard.")
            interval = FREQUENCIES[frequency][1]
            repository = {
                "id": repository_id,
                "slug": slug,
                "path": str(root),
                "default_branch": default_branch,
                "frequency": frequency,
                "next_scan_at": time.time() + interval if interval else None,
                "last_scan": None,
                "latest_report": None,
            }
            self.state["repositories"].append(repository)
            self._save()
            return copy.deepcopy(repository)

    def update_repository(self, repository_id: str, value: Dict[str, Any]) -> Dict[str, Any]:
        frequency = str(value.get("frequency", ""))
        if frequency not in FREQUENCIES:
            raise ValueError("Choose one of the available scan frequencies.")
        with self.lock:
            repository = self._find(repository_id)
            repository["frequency"] = frequency
            interval = FREQUENCIES[frequency][1]
            repository["next_scan_at"] = time.time() + interval if interval else None
            self._save()
            return copy.deepcopy(repository)

    def remove_repository(self, repository_id: str) -> None:
        with self.lock:
            job = self.jobs.get(repository_id, {})
            if job.get("status") in {"queued", "running"}:
                raise RuntimeError("Wait for the current scan to finish before removing this repository.")
            self._find(repository_id)
            self.state["repositories"] = [
                item for item in self.state["repositories"] if item["id"] != repository_id
            ]
            self.jobs.pop(repository_id, None)
            self._save()

    def public_state(self) -> Dict[str, Any]:
        with self.lock:
            repositories = copy.deepcopy(self.state["repositories"])
            jobs = copy.deepcopy(self.jobs)
        for repository in repositories:
            repository["job"] = jobs.get(repository["id"], {"status": "idle"})
        scanner_status = {}
        for name, settings in self.config.get("scanners", {}).items():
            binary = str(settings.get("binary", name))
            scanner_status[name] = bool(shutil.which(binary) or (Path(binary).is_file() if os.path.isabs(binary) else False))
        return {
            "repositories": repositories,
            "frequencies": {
                name: {"label": label, "seconds": seconds}
                for name, (label, seconds) in FREQUENCIES.items()
            },
            "scanners": scanner_status,
        }

    def latest_report(self, repository_id: str) -> Dict[str, Any]:
        with self.lock:
            report = self._find(repository_id).get("latest_report")
            if not report:
                raise KeyError("No report is available yet.")
            return copy.deepcopy(report)

    def start_scan(self, repository_id: str, trigger: str = "manual") -> Dict[str, Any]:
        with self.lock:
            repository = copy.deepcopy(self._find(repository_id))
            existing = self.jobs.get(repository_id, {})
            if existing.get("status") in {"queued", "running"}:
                raise RuntimeError("A scan is already running for this repository.")
            job = {"status": "queued", "started_at": _utc_timestamp(), "trigger": trigger}
            self.jobs[repository_id] = job
        worker = threading.Thread(
            target=self._run_scan,
            args=(repository, trigger),
            name=f"forgewatch-scan-{repository_id}",
            daemon=True,
        )
        worker.start()
        return copy.deepcopy(job)

    def _run_scan(self, repository: Dict[str, Any], trigger: str) -> None:
        repository_id = repository["id"]
        with self.lock:
            self.jobs[repository_id]["status"] = "running"
        try:
            root = Path(repository["path"])
            config = copy.deepcopy(self.config)
            config.setdefault("repository", {})["slug"] = repository["slug"]
            config["repository"]["default_branch"] = repository["default_branch"]
            result = scan(root, config, trigger, repository["default_branch"])
            result.default_branch_verified = verified_default_branch(
                root, repository["default_branch"], repository["default_branch"], result.commit_sha
            )
            self.store.record_scan(result, result.default_branch_verified)
            report_dir = (
                Path(config["_config_dir"])
                / ".forgewatch"
                / "artifacts"
                / "dashboard"
                / repository_id
                / f"{time.strftime('%Y%m%d-%H%M%S', time.gmtime())}-{result.scan_id[:8]}"
            )
            write_reports(result, report_dir)
            simple = plain_language(result)
            report = {
                "scan_id": result.scan_id,
                "repository": result.repository,
                "commit_sha": result.commit_sha,
                "started_at": result.started_at,
                "finished_at": result.finished_at,
                "status": result.status,
                "headline": simple["headline"],
                "summary": simple["summary"],
                "next_step": simple["next_step"],
                "findings": [
                    simple["findings"][item.fingerprint]
                    for item in sorted(
                        result.findings,
                        key=lambda item: (-SEVERITY_ORDER[item.severity], item.fingerprint),
                    )
                ],
                "checks": [
                    {
                        "name": CHECK_NAMES.get(item.scanner, item.scanner),
                        "status": CHECK_STATUS.get(item.status, item.status),
                        "error": item.error,
                    }
                    for item in result.scanner_runs
                ],
                "report_directory": str(report_dir),
            }
            finished = time.time()
            with self.lock:
                current = self._find(repository_id)
                current["last_scan"] = {
                    "status": result.status,
                    "headline": simple["headline"],
                    "finding_count": len(result.findings),
                    "finished_at": result.finished_at,
                    "commit_sha": result.commit_sha,
                }
                current["latest_report"] = report
                interval = FREQUENCIES[current["frequency"]][1]
                current["next_scan_at"] = finished + interval if interval else None
                self.jobs[repository_id] = {
                    "status": "finished",
                    "finished_at": result.finished_at,
                    "result": result.status,
                }
                self._save()
        except Exception as error:  # Scanner failures are shown in the local dashboard.
            finished = time.time()
            with self.lock:
                try:
                    current = self._find(repository_id)
                    current["last_scan"] = {
                        "status": "error",
                        "headline": "The scan could not start or finish",
                        "finding_count": 0,
                        "finished_at": _utc_timestamp(finished),
                    }
                    interval = FREQUENCIES[current["frequency"]][1]
                    current["next_scan_at"] = finished + interval if interval else None
                    self._save()
                except KeyError:
                    pass
                self.jobs[repository_id] = {
                    "status": "error",
                    "finished_at": _utc_timestamp(finished),
                    "error": str(error),
                }

    def _schedule_loop(self) -> None:
        while not self.stop_event.wait(15):
            now = time.time()
            with self.lock:
                due = [
                    item["id"]
                    for item in self.state["repositories"]
                    if item.get("next_scan_at") and item["next_scan_at"] <= now
                ]
            for repository_id in due:
                try:
                    self.start_scan(repository_id, "schedule")
                except (KeyError, RuntimeError):
                    continue


def dashboard_handler(controller: DashboardController, token: str):
    template = (Path(__file__).with_name("dashboard.html")).read_text(encoding="utf-8")

    class DashboardHandler(BaseHTTPRequestHandler):
        server_version = "ForgewatchDashboard/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _allowed_host(self) -> bool:
            host = self.headers.get("Host", "").lower()
            return host.startswith("127.0.0.1:") or host.startswith("localhost:") or host.startswith("[::1]:")

        def _headers(self, status: int, content_type: str, length: int, nonce: str = "") -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("X-Frame-Options", "DENY")
            if nonce:
                self.send_header(
                    "Content-Security-Policy",
                    f"default-src 'none'; style-src 'nonce-{nonce}'; script-src 'nonce-{nonce}'; "
                    "connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'self'",
                )
            self.end_headers()

        def _json(self, status: int, value: Dict[str, Any]) -> None:
            body = json.dumps(value).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _body(self) -> Dict[str, Any]:
            if self.headers.get("X-Forgewatch-Token") != token:
                raise PermissionError("The dashboard request token is missing or invalid.")
            if self.headers.get("Content-Type", "").split(";", 1)[0].strip() != "application/json":
                raise ValueError("Requests must use JSON.")
            length = int(self.headers.get("Content-Length", "0"))
            if length < 2 or length > 32_000:
                raise ValueError("Request body size is invalid.")
            value = json.loads(self.rfile.read(length))
            if not isinstance(value, dict):
                raise ValueError("Request body must be a JSON object.")
            return value

        def _segments(self) -> list[str]:
            return [part for part in self.path.split("?", 1)[0].split("/") if part]

        def _error(self, error: Exception) -> None:
            if isinstance(error, PermissionError):
                status = 403
            elif isinstance(error, KeyError):
                status = 404
            elif isinstance(error, RuntimeError):
                status = 409
            else:
                status = 400
            self._json(status, {"error": str(error).strip("'")})

        def do_GET(self) -> None:
            if not self._allowed_host():
                self._json(403, {"error": "Dashboard access is limited to this computer."})
                return
            segments = self._segments()
            if not segments:
                nonce = secrets.token_hex(16)
                body = template.replace("{{NONCE}}", nonce).replace("{{TOKEN}}", token).encode("utf-8")
                self._headers(200, "text/html; charset=utf-8", len(body), nonce)
                self.wfile.write(body)
                return
            try:
                if segments == ["api", "state"]:
                    self._json(200, controller.public_state())
                    return
                if len(segments) == 4 and segments[:2] == ["api", "repositories"] and segments[3] == "report":
                    self._json(200, controller.latest_report(segments[2]))
                    return
                self._json(404, {"error": "Not found."})
            except Exception as error:
                self._error(error)

        def do_POST(self) -> None:
            if not self._allowed_host():
                self._json(403, {"error": "Dashboard access is limited to this computer."})
                return
            try:
                value = self._body()
                segments = self._segments()
                if segments == ["api", "repositories"]:
                    self._json(201, {"repository": controller.add_repository(value)})
                    return
                if len(segments) == 4 and segments[:2] == ["api", "repositories"] and segments[3] == "scan":
                    self._json(202, {"job": controller.start_scan(segments[2])})
                    return
                self._json(404, {"error": "Not found."})
            except (ValueError, KeyError, RuntimeError, PermissionError, json.JSONDecodeError) as error:
                self._error(error)

        def do_PATCH(self) -> None:
            if not self._allowed_host():
                self._json(403, {"error": "Dashboard access is limited to this computer."})
                return
            try:
                value = self._body()
                segments = self._segments()
                if len(segments) == 3 and segments[:2] == ["api", "repositories"]:
                    self._json(200, {"repository": controller.update_repository(segments[2], value)})
                    return
                self._json(404, {"error": "Not found."})
            except (ValueError, KeyError, RuntimeError, PermissionError, json.JSONDecodeError) as error:
                self._error(error)

        def do_DELETE(self) -> None:
            if not self._allowed_host():
                self._json(403, {"error": "Dashboard access is limited to this computer."})
                return
            try:
                self._body()
                segments = self._segments()
                if len(segments) == 3 and segments[:2] == ["api", "repositories"]:
                    controller.remove_repository(segments[2])
                    self._json(200, {"status": "removed"})
                    return
                self._json(404, {"error": "Not found."})
            except (ValueError, KeyError, RuntimeError, PermissionError, json.JSONDecodeError) as error:
                self._error(error)

    return DashboardHandler


def serve_dashboard(
    config: Dict[str, Any],
    store: Store,
    host: str,
    port: int,
    state_file: str,
    open_browser: bool,
) -> None:
    if host not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("the dashboard may only listen on this computer")
    path = Path(state_file)
    if not path.is_absolute():
        path = Path(config["_config_dir"]) / path
    controller = DashboardController(config, store, path)
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer((host, port), dashboard_handler(controller, token))
    display_host = "[::1]" if host == "::1" else host
    address = f"http://{display_host}:{server.server_port}"
    controller.start()
    print(f"Forgewatch dashboard: {address}")
    print("Keep this terminal open while using scheduled local scans. Press Control-C to stop.")
    if open_browser:
        threading.Timer(0.25, lambda: webbrowser.open(address)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nForgewatch dashboard stopped.")
    finally:
        server.server_close()
        controller.close()
