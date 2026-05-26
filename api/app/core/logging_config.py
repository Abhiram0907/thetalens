"""Logging configuration with automatic secret redaction."""

from __future__ import annotations

import logging

from app.core.security import redact_secrets


class SecretRedactingFilter(logging.Filter):
    """Redact secrets from log record messages and args."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = redact_secrets(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: redact_secrets(str(v)) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    redact_secrets(str(a)) if isinstance(a, str) else a
                    for a in record.args
                )
        return True


def configure_logging(level: int = logging.INFO) -> None:
    root = logging.getLogger()
    if any(isinstance(f, SecretRedactingFilter) for f in root.filters):
        return
    root.setLevel(level)
    redactor = SecretRedactingFilter()
    root.addFilter(redactor)
    for handler in root.handlers:
        handler.addFilter(redactor)
