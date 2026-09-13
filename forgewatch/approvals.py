from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any, Dict

from .store import Store


ACTION_GENERATE_FIX = "generate_fix"


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def _key(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) < 32:
        raise ValueError("SECURITY_APPROVAL_KEY must contain at least 32 bytes")
    return raw


def issue(
    store: Store,
    signing_key: str,
    repository: str,
    fingerprint: str,
    commit_sha: str,
    actor: str,
    ttl_seconds: int = 900,
    action: str = ACTION_GENERATE_FIX,
) -> str:
    if ttl_seconds < 1 or ttl_seconds > 3600:
        raise ValueError("approval lifetime must be between 1 and 3600 seconds")
    now = int(time.time())
    payload: Dict[str, Any] = {
        "v": 1,
        "nonce": secrets.token_urlsafe(18),
        "repository": repository,
        "finding": fingerprint,
        "commit": commit_sha,
        "action": action,
        "actor": actor,
        "iat": now,
        "exp": now + ttl_seconds,
    }
    encoded = _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signature = _b64encode(hmac.new(_key(signing_key), encoded.encode("ascii"), hashlib.sha256).digest())
    store.register_approval(
        payload["nonce"], repository, fingerprint, commit_sha, action, actor, payload["exp"]
    )
    return f"{encoded}.{signature}"


def verify_and_consume(
    store: Store,
    token: str,
    signing_key: str,
    repository: str,
    fingerprint: str,
    commit_sha: str,
    current_sha: str,
    action: str = ACTION_GENERATE_FIX,
) -> Dict[str, Any]:
    try:
        encoded, signature = token.split(".", 1)
        supplied_signature = _b64decode(signature)
        payload = json.loads(_b64decode(encoded))
    except (ValueError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("approval token is malformed") from error
    expected_signature = hmac.new(_key(signing_key), encoded.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise ValueError("approval signature is invalid")
    expected = (repository, fingerprint, commit_sha, action)
    actual = (payload.get("repository"), payload.get("finding"), payload.get("commit"), payload.get("action"))
    if actual != expected:
        raise ValueError("approval is bound to a different repository, finding, commit, or action")
    if commit_sha != current_sha:
        raise ValueError("approval is stale because the target commit changed")
    now = int(time.time())
    if int(payload.get("exp", 0)) < now:
        raise ValueError("approval has expired")
    store.consume_approval(payload["nonce"], repository, fingerprint, commit_sha, action, now)
    return payload
