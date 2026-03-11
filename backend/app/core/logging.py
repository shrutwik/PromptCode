from __future__ import annotations

import contextvars
import json
import logging
from contextvars import ContextVar
from datetime import datetime, timezone

_STANDARD_LOG_RECORD_KEYS = set(logging.makeLogRecord({}).__dict__.keys())

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def set_request_id(request_id: str) -> contextvars.Token[str]:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: contextvars.Token[str]) -> None:
    _request_id_ctx.reset(token)


class RequestIdFilter(logging.Filter):
    """Injects the current request_id ContextVar into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = _request_id_ctx.get()
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STANDARD_LOG_RECORD_KEYS or key.startswith("_"):
                continue
            payload[key] = value if isinstance(value, (str, int, float, bool)) or value is None else str(value)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, sort_keys=True)


def configure_logging(level: int = logging.INFO) -> None:
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    _filter = RequestIdFilter()
    formatter = JsonFormatter()
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
        handler.setLevel(level)
        handler.addFilter(_filter)

    if not root_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(level)
        handler.setFormatter(formatter)
        handler.addFilter(_filter)
        root_logger.addHandler(handler)

    _init_sentry()


def _init_sentry() -> None:
    from app.core.config import get_settings

    dsn = get_settings().sentry_dsn.strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration

        sentry_sdk.init(
            dsn=dsn,
            integrations=[
                FastApiIntegration(),
                LoggingIntegration(level=logging.WARNING, event_level=logging.ERROR),
            ],
            traces_sample_rate=0.1,
            send_default_pii=False,
        )
        logging.getLogger(__name__).info("Sentry initialised")
    except ImportError:
        logging.getLogger(__name__).warning("sentry-sdk not installed; skipping Sentry init")
