from __future__ import annotations

import hashlib
import hmac
import re
import time

from .store import Store


DELIVERY_ID = re.compile(r"^[A-Za-z0-9._:-]{1,200}$")


def verify_signature(body: bytes, signature_header: str, webhook_secret: str) -> None:
    if not webhook_secret:
        raise ValueError("a webhook secret is required")
    if not signature_header.startswith("sha256="):
        raise ValueError("webhook signature must use sha256")
    supplied = signature_header.removeprefix("sha256=")
    expected = hmac.new(webhook_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied, expected):
        raise ValueError("webhook signature is invalid")


def accept_delivery(
    store: Store,
    body: bytes,
    signature_header: str,
    webhook_secret: str,
    delivery_id: str,
    event: str,
) -> None:
    verify_signature(body, signature_header, webhook_secret)
    if not DELIVERY_ID.fullmatch(delivery_id):
        raise ValueError("webhook delivery id is invalid")
    if not store.record_webhook_delivery(delivery_id, event[:100], int(time.time())):
        raise ValueError("duplicate webhook delivery")
