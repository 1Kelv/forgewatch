from __future__ import annotations

import base64
import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

from .redaction import redact_text


def _b64(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


class GitHubAppClient:
    def __init__(self, app_id: str, installation_id: str, private_key_path: Path):
        if not app_id or not installation_id:
            raise ValueError("GITHUB_APP_ID and GITHUB_APP_INSTALLATION_ID are required")
        if not private_key_path.is_file():
            raise ValueError("GITHUB_APP_PRIVATE_KEY_PATH must point to the GitHub App private key")
        self.app_id = app_id
        self.installation_id = installation_id
        self.private_key_path = private_key_path

    @classmethod
    def from_environment(cls) -> "GitHubAppClient":
        return cls(
            os.environ.get("GITHUB_APP_ID", ""),
            os.environ.get("GITHUB_APP_INSTALLATION_ID", ""),
            Path(os.environ.get("GITHUB_APP_PRIVATE_KEY_PATH", "")),
        )

    def app_jwt(self) -> str:
        now = int(time.time())
        header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
        payload = _b64(
            json.dumps(
                {"iat": now - 30, "exp": now + 540, "iss": self.app_id},
                separators=(",", ":"),
            ).encode()
        )
        signing_input = f"{header}.{payload}".encode("ascii")
        process = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(self.private_key_path)],
            input=signing_input,
            capture_output=True,
            check=False,
        )
        if process.returncode != 0:
            raise RuntimeError(f"could not sign GitHub App JWT: {redact_text(process.stderr.decode(errors='replace'))}")
        return f"{header}.{payload}.{_b64(process.stdout)}"

    def _request(self, method: str, path: str, token: str, payload: Optional[Dict[str, Any]] = None) -> Any:
        request = urllib.request.Request(
            f"https://api.github.com{path}",
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "User-Agent": "pervigil-forgewatch/0.1",
                "Content-Type": "application/json",
            },
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                content = response.read()
                return json.loads(content) if content else None
        except urllib.error.HTTPError as error:
            detail = redact_text(error.read().decode("utf-8", errors="replace"))[:1000]
            raise RuntimeError(f"GitHub API returned HTTP {error.code}: {detail}") from error

    def installation_token(self) -> str:
        response = self._request(
            "POST",
            f"/app/installations/{self.installation_id}/access_tokens",
            self.app_jwt(),
            {},
        )
        token = response.get("token") if isinstance(response, dict) else None
        if not token:
            raise RuntimeError("GitHub did not return an installation token")
        return token

    def dispatch_scan(
        self,
        automation_repository: str,
        event_type: str,
        target_repository: str,
        commit_sha: str,
        ref: str,
        trigger: str,
        delivery_id: str,
        default_branch: str,
    ) -> None:
        parts = target_repository.split("/", 1)
        if len(parts) != 2 or not all(parts):
            raise ValueError("target repository must use owner/name format")
        target_owner, target_name = parts
        token = self.installation_token()
        self._request(
            "POST",
            f"/repos/{automation_repository}/dispatches",
            token,
            {
                "event_type": event_type,
                "client_payload": {
                    "repository": target_repository,
                    "target_owner": target_owner,
                    "target_name": target_name,
                    "commit": commit_sha,
                    "ref": ref,
                    "trigger": trigger,
                    "delivery_id": delivery_id,
                    "default_branch": default_branch,
                },
            },
        )
