"""Rate limiting — in-memory locally; Redis when REDIS_URL is set (multi-instance)."""

from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)


def _storage_uri() -> str:
    url = os.environ.get("REDIS_URL", "").strip()
    if url:
        return url
    return "memory://"


_storage = _storage_uri()
if _storage != "memory://":
    logger.info("Rate limiter using Redis backend")
else:
    logger.info("Rate limiter using in-memory backend (set REDIS_URL for multi-instance)")

limiter = Limiter(key_func=get_remote_address, storage_uri=_storage, default_limits=[])
