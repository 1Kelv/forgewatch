from __future__ import annotations

import re
from typing import Any


REDACTED = "[REDACTED]"

PATTERNS = [
    re.compile(r"(?i)(authorization\s*:\s*(?:bearer|token)\s+)[^\s,;]+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret|password)\s*[=:]\s*)['\"]?[^\s,'\"]+"),
    re.compile(r"\b(?:gh[opusr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
]


def redact_text(value: str) -> str:
    redacted = value
    for index, pattern in enumerate(PATTERNS):
        if index < 2:
            redacted = pattern.sub(lambda match: match.group(1) + REDACTED, redacted)
        else:
            redacted = pattern.sub(REDACTED, redacted)
    return redacted


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        output = {}
        for key, item in value.items():
            if key.lower() in {"secret", "match", "token", "password", "api_key", "apikey"}:
                output[key] = REDACTED
            else:
                output[key] = redact(item)
        return output
    return value
