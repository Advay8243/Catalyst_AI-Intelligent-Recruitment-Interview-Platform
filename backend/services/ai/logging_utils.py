from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


logger = logging.getLogger("catalyst.ai")


@contextmanager
def log_ai_operation(
    *,
    provider: str,
    operation: str,
    request_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    """Log provider/operation/latency/success without secrets or full resume text."""
    rid = request_id or str(uuid.uuid4())
    started = time.perf_counter()
    context: dict[str, Any] = {
        "provider": provider,
        "operation": operation,
        "request_id": rid,
        "success": False,
    }
    if metadata:
        # Only allow non-sensitive counters/labels.
        for key in ("model", "attempt", "status_code", "schema"):
            if key in metadata:
                context[key] = metadata[key]
    try:
        yield context
        context["success"] = True
    except Exception as exc:
        context["success"] = False
        context["error_type"] = type(exc).__name__
        raise
    finally:
        context["latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
        level = logging.INFO if context["success"] else logging.WARNING
        logger.log(
            level,
            "ai_operation provider=%s operation=%s request_id=%s success=%s latency_ms=%s",
            context["provider"],
            context["operation"],
            context["request_id"],
            context["success"],
            context["latency_ms"],
            extra={"ai": context},
        )
