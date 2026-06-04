"""Env-configurable rate limit strings (evaluated at import; override via RATE_LIMIT_* env)."""

from __future__ import annotations

import os

from dotenv import load_dotenv

load_dotenv()


def _limit(env_key: str, default: str) -> str:
    return (os.environ.get(env_key) or default).strip()


AGENT_STREAM = _limit("RATE_LIMIT_AGENT_STREAM", "8/minute")
AGENT_RUN = _limit("RATE_LIMIT_AGENT_RUN", "4/minute")
SCANNER = _limit("RATE_LIMIT_SCANNER", "20/minute")
ANALYZE = _limit("RATE_LIMIT_ANALYZE", "20/minute")
INTENT = _limit("RATE_LIMIT_INTENT", "30/minute")
EXPORT = _limit("RATE_LIMIT_EXPORT", "15/minute")
