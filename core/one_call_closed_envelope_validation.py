"""Closed control-envelope validation for ONE_CALL JSON mode capability probes."""

from __future__ import annotations

import json
from typing import Any

_ALLOWED_ROUTES = frozenset({"ANSWER", "ADMIN", "CLARIFY"})
_ALLOWED_EXTENT = frozenset({"one_tooth", "few_teeth", "full_arch"})
_ALLOWED_JAW = frozenset({"upper", "lower", "both"})
_ALLOWED_SCENARIO = frozenset(
    {"pain_fear", "cost", "time", "doctor_trust", "result_reliability", "none"}
)
_ALLOWED_CLARIFY_AXIS = frozenset({"service", "extent", "jaw", "stage"})
_REQUIRED_TOP_LEVEL = frozenset(
    {
        "route",
        "service_id",
        "extent",
        "jaw",
        "stage",
        "scenario",
        "clarify_axis",
        "clarify_service_options",
        "patient_text",
    }
)


class ClosedEnvelopeValidationError(ValueError):
    """Typed closed-envelope validation failure."""


def _require_exact_key_set(payload: dict[str, Any]) -> None:
    keys = set(payload.keys())
    missing = _REQUIRED_TOP_LEVEL - keys
    if missing:
        raise ClosedEnvelopeValidationError(f"missing_fields:{sorted(missing)}")
    extra = keys - _REQUIRED_TOP_LEVEL
    if extra:
        raise ClosedEnvelopeValidationError(f"unknown_fields:{sorted(extra)}")


def _validate_service_clarify_options(options: object) -> None:
    if not isinstance(options, list):
        raise ClosedEnvelopeValidationError("clarify_service_options_invalid")
    if len(options) < 2 or len(options) > 3:
        raise ClosedEnvelopeValidationError("clarify_service_options_invalid")
    normalized: list[str] = []
    for item in options:
        if not isinstance(item, str) or not item.strip():
            raise ClosedEnvelopeValidationError("clarify_service_options_invalid")
        token = item.strip()
        if token in normalized:
            raise ClosedEnvelopeValidationError("clarify_service_options_invalid")
        normalized.append(token)


def validate_closed_envelope_object(payload: object) -> dict[str, Any]:
    """Validate provider JSON object against ONE_CALL closed envelope."""

    if not isinstance(payload, dict):
        raise ClosedEnvelopeValidationError("envelope_not_object")
    _require_exact_key_set(payload)

    route = payload["route"]
    if route not in _ALLOWED_ROUTES:
        raise ClosedEnvelopeValidationError("route_invalid")

    service_id = payload["service_id"]
    if service_id is not None and not isinstance(service_id, str):
        raise ClosedEnvelopeValidationError("service_id_invalid")

    extent = payload["extent"]
    if extent is not None and extent not in _ALLOWED_EXTENT:
        raise ClosedEnvelopeValidationError("extent_invalid")

    jaw = payload["jaw"]
    if jaw is not None and jaw not in _ALLOWED_JAW:
        raise ClosedEnvelopeValidationError("jaw_invalid")

    stage = payload["stage"]
    if stage is not None and not isinstance(stage, str):
        raise ClosedEnvelopeValidationError("stage_invalid")

    scenario = payload["scenario"]
    if scenario not in _ALLOWED_SCENARIO:
        raise ClosedEnvelopeValidationError("scenario_invalid")

    clarify_axis = payload["clarify_axis"]
    if clarify_axis is not None and clarify_axis not in _ALLOWED_CLARIFY_AXIS:
        raise ClosedEnvelopeValidationError("clarify_axis_invalid")

    options = payload["clarify_service_options"]
    if options is not None and not isinstance(options, list):
        raise ClosedEnvelopeValidationError("clarify_service_options_invalid")

    patient_text = payload["patient_text"]

    if route == "ANSWER":
        if not isinstance(patient_text, str) or not patient_text.strip():
            raise ClosedEnvelopeValidationError("patient_text_required")
        if clarify_axis is not None:
            raise ClosedEnvelopeValidationError("clarify_axis_forbidden_for_answer")
        if options is not None:
            raise ClosedEnvelopeValidationError("clarify_service_options_forbidden_for_answer")
    elif route == "ADMIN":
        if patient_text is not None:
            raise ClosedEnvelopeValidationError("patient_text_forbidden_for_admin")
        if clarify_axis is not None:
            raise ClosedEnvelopeValidationError("clarify_axis_forbidden_for_admin")
        if options is not None:
            raise ClosedEnvelopeValidationError("clarify_service_options_forbidden_for_admin")
    elif route == "CLARIFY":
        if not isinstance(patient_text, str) or not patient_text.strip():
            raise ClosedEnvelopeValidationError("patient_text_required")
        if clarify_axis is None:
            raise ClosedEnvelopeValidationError("clarify_axis_required_for_clarify")
        if clarify_axis == "service":
            _validate_service_clarify_options(options)
        elif options is not None:
            raise ClosedEnvelopeValidationError("clarify_service_options_forbidden_for_axis")

    return payload


def parse_and_validate_closed_envelope_json(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ClosedEnvelopeValidationError("json_invalid") from exc
    return validate_closed_envelope_object(payload)


def sample_valid_json_mode_envelope() -> str:
    return json.dumps(
        {
            "route": "ANSWER",
            "service_id": None,
            "extent": None,
            "jaw": None,
            "stage": None,
            "scenario": "none",
            "clarify_axis": None,
            "clarify_service_options": None,
            "patient_text": "Capability JSON envelope ok.",
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def closed_envelope_template(**overrides: object) -> dict[str, Any]:
    base: dict[str, Any] = {
        "route": "ANSWER",
        "service_id": None,
        "extent": None,
        "jaw": None,
        "stage": None,
        "scenario": "none",
        "clarify_axis": None,
        "clarify_service_options": None,
        "patient_text": "Probe text.",
    }
    base.update(overrides)
    return base
