"""Security helpers: safe client errors and secret redaction."""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("thetalens.security")

# Patterns that may appear in URLs, logs, or exception strings.
_REDACT_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(apiKey=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"([?&]key=)[^&\s\"']+", re.IGNORECASE),
    re.compile(r"(x-goog-api-key:\s*)[^\s\"']+", re.IGNORECASE),
    re.compile(r"(Authorization:\s*(?:Bearer|Basic)\s*)[^\s\"']+", re.IGNORECASE),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\b(sk-[a-zA-Z0-9]{20,})\b"),
)

GENERIC_ERROR = "Something went wrong. Please try again."
SERVICE_UNAVAILABLE = "Service temporarily unavailable. Please try again later."
UPSTREAM_UNAVAILABLE = "Market data service is temporarily unavailable."
LLM_UNAVAILABLE = "Research agent is temporarily unavailable. Please try again."


def redact_secrets(text: str) -> str:
    """Remove API keys and tokens from arbitrary text (logs, errors)."""
    if not text:
        return text
    redacted = text
    for pattern in _REDACT_PATTERNS:
        if pattern.groups:
            redacted = pattern.sub(r"\1[REDACTED]", redacted)
        else:
            redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


def safe_client_message(
    exc: BaseException,
    *,
    default: str = GENERIC_ERROR,
    dev_detail: bool = False,
) -> str:
    """Return a user-safe error string; log full details server-side."""
    import httpx

    if isinstance(exc, httpx.HTTPError):
        logger.warning(
            "Upstream HTTP error: %s",
            type(exc).__name__,
            exc_info=exc,
        )
        return default

    raw = redact_secrets(str(exc).strip())
    if raw and dev_detail:
        return raw
    if raw:
        logger.error("Internal error: %s", raw, exc_info=exc)
    else:
        logger.error("Internal error (%s)", type(exc).__name__, exc_info=exc)
    return default


def sanitize_tool_result(result: dict[str, Any]) -> dict[str, Any]:
    """Strip internal fields before streaming tool results to clients."""
    cleaned = dict(result)
    cleaned.pop("traceback", None)
    if "error" in cleaned and isinstance(cleaned["error"], str):
        cleaned["error"] = redact_secrets(cleaned["error"])
        if len(cleaned["error"]) > 200:
            cleaned["error"] = "Tool execution failed"
    return cleaned
