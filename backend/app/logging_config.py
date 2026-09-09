"""
Structured JSON logging configuration for Lambda and local environments.

Lambda captures stdout/stderr. Using JSON-formatted logs ensures that
CloudWatch Logs Insights can query structured fields such as:
- correlation_id
- incident_id
- stage (simulation -> detection -> event -> recovery -> notification)
- resource_id
- failure_type
"""

from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# Context variables for tracing across execution contexts
_correlation_id_ctx: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_incident_id_ctx: ContextVar[str | None] = ContextVar("incident_id", default=None)
_stage_ctx: ContextVar[str | None] = ContextVar("stage", default=None)

# Standard LogRecord attributes that should not be treated as custom extra fields
_STANDARD_RECORD_ATTRS: frozenset[str] = frozenset({
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
    "taskName",
    "extra",
})


def set_correlation_id(correlation_id: str | None) -> None:
    """Set the correlation ID for the current async/thread execution context."""
    _correlation_id_ctx.set(correlation_id)


def get_correlation_id() -> str | None:
    """Retrieve current context correlation ID."""
    return _correlation_id_ctx.get()


def set_incident_id(incident_id: str | None) -> None:
    """Set the incident ID for the current execution context."""
    _incident_id_ctx.set(incident_id)


def get_incident_id() -> str | None:
    """Retrieve current context incident ID."""
    return _incident_id_ctx.get()


def set_trace_stage(stage: str | None) -> None:
    """
    Set current observability lifecycle stage.
    Allowed stages: 'simulation', 'detection', 'event', 'recovery', 'notification'.
    """
    _stage_ctx.set(stage)


def get_trace_stage() -> str | None:
    """Retrieve current observability lifecycle stage."""
    return _stage_ctx.get()


def clear_trace_context() -> None:
    """Reset all trace context variables."""
    _correlation_id_ctx.set(None)
    _incident_id_ctx.set(None)
    _stage_ctx.set(None)


class JsonFormatter(logging.Formatter):
    """Emit log records as single-line JSON objects with correlation fields."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include correlation context if available
        correlation_id = getattr(record, "correlation_id", None) or get_correlation_id()
        if correlation_id:
            log_obj["correlation_id"] = correlation_id

        incident_id = getattr(record, "incident_id", None) or get_incident_id()
        if incident_id:
            log_obj["incident_id"] = incident_id

        stage = getattr(record, "stage", None) or get_trace_stage()
        if stage:
            log_obj["stage"] = stage

        # Exception formatting
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)

        # Include any custom fields passed via extra={...}
        for key, value in record.__dict__.items():
            if key not in _STANDARD_RECORD_ATTRS and not key.startswith("_") and key not in log_obj:
                try:
                    # Verify json serializable
                    json.dumps(value)
                    log_obj[key] = value
                except (TypeError, OverflowError):
                    log_obj[key] = str(value)

        # Legacy extra support
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_obj.update(record.extra)

        return json.dumps(log_obj)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logger with JSON output. Call once at startup / cold start."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
