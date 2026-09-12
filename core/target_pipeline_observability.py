"""Structured target pipeline failure events for operational observability."""

from __future__ import annotations

from typing import Any

from logging_setup import emit_bot_event, get_logger

_LOGGER = get_logger("target_runtime")


def _safe_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, tuple):
        return [_safe_value(item) for item in value]
    if isinstance(value, list):
        return [_safe_value(item) for item in value]
    return repr(value)


def pipeline_failure_code(exc: BaseException) -> tuple[str, str, object]:
    """Map a pipeline exception to (stage, code, value)."""

    code = getattr(exc, "code", None)
    if isinstance(code, str) and code:
        value = getattr(exc, "value", repr(exc))
        if code.startswith("target_verifier_"):
            return "verifier", code, value
        if code.startswith("spec_package_"):
            return "spec_package", code, value
        if code.startswith("composer_"):
            return "composer", code, value
        if code.startswith("offline_assembly_"):
            return "assembly", code, value
        return "pipeline", code, value
    return "pipeline", f"{type(exc).__name__}", repr(exc)


def emit_target_pipeline_failure(
    *,
    stage: str,
    code: str,
    value: object,
    extra: dict[str, Any] | None = None,
) -> None:
    details: dict[str, object] = {
        "stage": stage,
        "code": code,
        "value": _safe_value(value),
    }
    if extra:
        details.update(extra)
    emit_bot_event(
        _LOGGER,
        "target_pipeline_failure",
        status="error",
        details=details,
    )


def emit_target_pipeline_failure_from_exception(
    exc: BaseException,
    *,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, object]:
    stage, code, value = pipeline_failure_code(exc)
    emit_target_pipeline_failure(stage=stage, code=code, value=value, extra=extra)
    return stage, code, value
