from __future__ import annotations

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Tuple

from .github_app import GitHubAppClient
from .store import Store
from .webhooks import accept_delivery


SHA = re.compile(r"^[0-9a-f]{40}$")


def event_target(event: str, payload: Dict[str, Any]) -> Tuple[str, str, str, str, str]:
    repository_data = payload.get("repository", {})
    repository = repository_data.get("full_name", "")
    default_branch = repository_data.get("default_branch", "")
    if event == "push":
        return repository, payload.get("after", ""), payload.get("ref", ""), "push", default_branch
    if event == "pull_request" and payload.get("action") in {"opened", "reopened", "synchronize"}:
        pull_request = payload.get("pull_request", {})
        head = pull_request.get("head", {})
        return repository, head.get("sha", ""), head.get("ref", ""), "pull_request", default_branch
    raise ValueError("webhook event does not require a scan")


def handler(config: Dict[str, Any], store: Store, client: GitHubAppClient):
    github = config.get("github", {})
    allowed = set(github.get("target_repositories", []))
    webhook_secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")

    class WebhookHandler(BaseHTTPRequestHandler):
        server_version = "Forgewatch/0.1"

        def log_message(self, format: str, *args: Any) -> None:
            return

        def respond(self, status: int, value: Dict[str, Any]) -> None:
            body = json.dumps(value).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self) -> None:
            if self.path != "/github/webhook":
                self.respond(404, {"error": "not found"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 1 or length > 5_000_000:
                    raise ValueError("webhook payload size is invalid")
                body = self.rfile.read(length)
                signature = self.headers.get("X-Hub-Signature-256", "")
                delivery_id = self.headers.get("X-GitHub-Delivery", "")
                event = self.headers.get("X-GitHub-Event", "")
                accept_delivery(store, body, signature, webhook_secret, delivery_id, event)
                payload = json.loads(body)
                repository, commit_sha, ref, trigger, default_branch = event_target(event, payload)
                if repository not in allowed:
                    raise ValueError("repository is not in the configured target allow-list")
                if not SHA.fullmatch(commit_sha):
                    raise ValueError("webhook commit SHA is invalid")
                if not default_branch or len(default_branch) > 255:
                    raise ValueError("webhook default branch is invalid")
                client.dispatch_scan(
                    github["automation_repository"],
                    github.get("dispatch_event", "forgewatch_scan"),
                    repository,
                    commit_sha,
                    ref[:255],
                    trigger,
                    delivery_id,
                    default_branch,
                )
                self.respond(202, {"status": "queued", "delivery_id": delivery_id})
            except (ValueError, KeyError, json.JSONDecodeError) as error:
                self.respond(400, {"error": str(error)})
            except RuntimeError as error:
                self.respond(502, {"error": str(error)})

    return WebhookHandler


def serve(config: Dict[str, Any], store: Store, host: str, port: int) -> None:
    client = GitHubAppClient.from_environment()
    server = ThreadingHTTPServer((host, port), handler(config, store, client))
    server.serve_forever()
