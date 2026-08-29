"""Production v5 JSON envelope parser and validator (Stage 4.2 / B1)."""

from __future__ import annotations

import json
from typing import Any

from contracts.one_call_envelope import (
    ENVELOPE_NORMALIZED_DIRECT_FACT_ID_DEDUPED,
    ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS,
    OneCallClarifyAxis,
    OneCallCommercialIntent,
    OneCallEnvelope,
    OneCallEnvelopeReferences,
    OneCallExtent,
    OneCallJaw,
    OneCallPromotionScope,
    OneCallRoute,
    OneCallScenario,
    required_envelope_field_names,
    required_reference_field_names,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot

MAX_ENVELOPE_UTF8_BYTES = 64 * 1024

_ALLOWED_ROUTES = frozenset({"ANSWER", "ADMIN", "CLARIFY"})
_ALLOWED_EXTENT = frozenset({"one_tooth", "few_teeth", "full_arch"})
_ALLOWED_JAW = frozenset({"upper", "lower", "both"})
_ALLOWED_SCENARIO = frozenset(
    {"pain_fear", "cost", "time", "doctor_trust", "result_reliability", "none"}
)
_ALLOWED_COMMERCIAL_INTENT = frozenset({"none", "price", "payment", "included", "promotion"})
_ALLOWED_PROMOTION_SCOPE = frozenset({"none", "general", "service", "shown"})
_ALLOWED_CLARIFY_AXIS = frozenset({"service", "extent", "jaw", "stage"})
_ALLOWED_SERVICE_REFERENCE_STATUS = frozenset({"none", "resolved", "unresolved"})


class OneCallEnvelopeProtocolError(ValueError):
    """Typed production envelope failure — reason code only, no raw payload."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)



def _clear_envelope_input_normalizations() -> None:
    try:
        from core import turn_timing

        turn_timing.set_flag("envelope_input_normalizations", [])
    except Exception:
        pass


def _record_envelope_input_normalizations(codes: tuple[str, ...]) -> None:
    try:
        from core import turn_timing

        turn_timing.set_flag("envelope_input_normalizations", list(codes))
    except Exception:
        pass


def _normalize_direct_fact_ids_list(
    direct_fact_ids: list[object],
) -> tuple[list[str], tuple[str, ...]]:
    """Validate every element, then dedupe identical correct IDs in order."""

    codes: list[str] = []
    normalized: list[str] = []
    for item in direct_fact_ids:
        if isinstance(item, bool) or not isinstance(item, str):
            raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
        token = item.strip()
        if not token:
            raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
        if token in normalized:
            if ENVELOPE_NORMALIZED_DIRECT_FACT_ID_DEDUPED not in codes:
                codes.append(ENVELOPE_NORMALIZED_DIRECT_FACT_ID_DEDUPED)
            continue
        normalized.append(token)
    return normalized, tuple(codes)


def _normalize_production_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], tuple[str, ...]]:
    codes: list[str] = []
    required = required_envelope_field_names()
    keys = set(payload.keys())
    missing = required - keys
    if missing:
        raise OneCallEnvelopeProtocolError(f"missing_fields:{sorted(missing)}")
    extra = keys - required
    if extra:
        payload = {key: payload[key] for key in required if key in payload}
        codes.append(ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS)
    references = payload.get("references")
    if isinstance(references, dict):
        direct_fact_ids = references.get("direct_fact_ids")
        if isinstance(direct_fact_ids, list):
            deduped, dedupe_codes = _normalize_direct_fact_ids_list(direct_fact_ids)
            codes.extend(dedupe_codes)
            if deduped != direct_fact_ids:
                payload = dict(payload)
                payload["references"] = {
                    **references,
                    "direct_fact_ids": deduped,
                }
        elif direct_fact_ids is not None:
            raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
    return payload, tuple(codes)


def _require_exact_key_set(payload: dict[str, Any]) -> None:
    keys = set(payload.keys())
    required = required_envelope_field_names()
    missing = required - keys
    if missing:
        raise OneCallEnvelopeProtocolError(f"missing_fields:{sorted(missing)}")
    extra = keys - required
    if extra:
        raise OneCallEnvelopeProtocolError(f"unknown_fields:{sorted(extra)}")


def _reject_bool(value: object, *, code: str) -> None:
    if isinstance(value, bool):
        raise OneCallEnvelopeProtocolError(code)


def _optional_nonblank_string(value: object, *, code: str) -> str | None:
    if value is None:
        return None
    _reject_bool(value, code=code)
    if not isinstance(value, str):
        raise OneCallEnvelopeProtocolError(code)
    token = value.strip()
    if not token:
        raise OneCallEnvelopeProtocolError(code)
    return token


def _validate_service_clarify_options(options: object) -> tuple[str, ...]:
    if not isinstance(options, list):
        raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")
    if len(options) < 2 or len(options) > 3:
        raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")
    normalized: list[str] = []
    for item in options:
        _reject_bool(item, code="clarify_service_options_invalid")
        if not isinstance(item, str) or not item.strip():
            raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")
        token = item.strip()
        if token in normalized:
            raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")
        normalized.append(token)
    return tuple(normalized)


def _validate_direct_fact_ids(
    value: object,
    *,
    route: str,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> tuple[str, ...]:
    if value is None:
        raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
    if not isinstance(value, list):
        raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
    normalized: list[str] = []
    for item in value:
        _reject_bool(item, code="direct_fact_ids_invalid")
        if not isinstance(item, str) or not item.strip():
            raise OneCallEnvelopeProtocolError("direct_fact_ids_invalid")
        token = item.strip()
        if token in normalized:
            continue
        normalized.append(token)
    direct_fact_ids = tuple(normalized)
    if route in {"CLARIFY", "ADMIN"} and direct_fact_ids:
        raise OneCallEnvelopeProtocolError("direct_fact_ids_forbidden_for_route")
    return direct_fact_ids


def _validate_references(
    value: object,
    *,
    route: str,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> OneCallEnvelopeReferences:
    if not isinstance(value, dict):
        raise OneCallEnvelopeProtocolError("references_invalid")
    keys = set(value.keys())
    required = required_reference_field_names()
    missing = required - keys
    if missing:
        raise OneCallEnvelopeProtocolError(f"missing_reference_fields:{sorted(missing)}")
    extra = keys - required
    if extra:
        raise OneCallEnvelopeProtocolError(f"unknown_reference_fields:{sorted(extra)}")
    direct_fact_ids = _validate_direct_fact_ids(
        value["direct_fact_ids"],
        route=route,
        commercial_fact_catalog=commercial_fact_catalog,
    )
    return OneCallEnvelopeReferences(direct_fact_ids=direct_fact_ids)


def _validate_structure(
    payload: dict[str, Any],
    *,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> OneCallEnvelope:
    _require_exact_key_set(payload)

    route = payload["route"]
    _reject_bool(route, code="route_invalid")
    if not isinstance(route, str) or route not in _ALLOWED_ROUTES:
        raise OneCallEnvelopeProtocolError("route_invalid")

    service_id = _optional_nonblank_string(payload["service_id"], code="service_id_invalid")

    extent = payload["extent"]
    if extent is not None:
        _reject_bool(extent, code="extent_invalid")
        if not isinstance(extent, str) or extent not in _ALLOWED_EXTENT:
            raise OneCallEnvelopeProtocolError("extent_invalid")

    jaw = payload["jaw"]
    if jaw is not None:
        _reject_bool(jaw, code="jaw_invalid")
        if not isinstance(jaw, str) or jaw not in _ALLOWED_JAW:
            raise OneCallEnvelopeProtocolError("jaw_invalid")

    stage = _optional_nonblank_string(payload["stage"], code="stage_invalid")

    scenario = payload["scenario"]
    _reject_bool(scenario, code="scenario_invalid")
    if not isinstance(scenario, str) or scenario not in _ALLOWED_SCENARIO:
        raise OneCallEnvelopeProtocolError("scenario_invalid")

    commercial_intent = payload["commercial_intent"]
    _reject_bool(commercial_intent, code="commercial_intent_invalid")
    if not isinstance(commercial_intent, str) or commercial_intent not in _ALLOWED_COMMERCIAL_INTENT:
        raise OneCallEnvelopeProtocolError("commercial_intent_invalid")

    promotion_scope = payload["promotion_scope"]
    _reject_bool(promotion_scope, code="promotion_scope_invalid")
    if not isinstance(promotion_scope, str) or promotion_scope not in _ALLOWED_PROMOTION_SCOPE:
        raise OneCallEnvelopeProtocolError("promotion_scope_invalid")
    if commercial_intent != "promotion" and promotion_scope != "none":
        raise OneCallEnvelopeProtocolError("promotion_scope_forbidden")
    if commercial_intent == "promotion" and promotion_scope not in {"general", "service", "shown"}:
        raise OneCallEnvelopeProtocolError("promotion_scope_invalid")

    clarify_axis = payload["clarify_axis"]
    if clarify_axis is not None:
        _reject_bool(clarify_axis, code="clarify_axis_invalid")
        if not isinstance(clarify_axis, str) or clarify_axis not in _ALLOWED_CLARIFY_AXIS:
            raise OneCallEnvelopeProtocolError("clarify_axis_invalid")

    options_raw = payload["clarify_service_options"]
    clarify_service_options: tuple[str, ...] | None
    if options_raw is None:
        clarify_service_options = None
    elif route == "CLARIFY" and clarify_axis != "service":
        raise OneCallEnvelopeProtocolError("clarify_service_options_forbidden_for_axis")
    else:
        clarify_service_options = _validate_service_clarify_options(options_raw)

    patient_text_raw = payload["patient_text"]
    patient_text: str | None
    if patient_text_raw is None:
        patient_text = None
    else:
        _reject_bool(patient_text_raw, code="patient_text_invalid")
        if not isinstance(patient_text_raw, str):
            raise OneCallEnvelopeProtocolError("patient_text_invalid")
        patient_text = patient_text_raw
        if route in {"ANSWER", "CLARIFY"} and not patient_text.strip():
            raise OneCallEnvelopeProtocolError("patient_text_required")

    service_reference_status = payload["service_reference_status"]
    _reject_bool(service_reference_status, code="service_reference_status_invalid")
    if (
        not isinstance(service_reference_status, str)
        or service_reference_status not in _ALLOWED_SERVICE_REFERENCE_STATUS
    ):
        raise OneCallEnvelopeProtocolError("service_reference_status_invalid")

    requested_service_id = _optional_nonblank_string(
        payload["requested_service_id"],
        code="requested_service_id_invalid",
    )

    references = _validate_references(
        payload["references"],
        route=route,
        commercial_fact_catalog=commercial_fact_catalog,
    )

    if service_reference_status == "none" and requested_service_id is not None:
        raise OneCallEnvelopeProtocolError("requested_service_id_forbidden_for_none")
    if service_reference_status == "unresolved" and requested_service_id is not None:
        raise OneCallEnvelopeProtocolError("requested_service_id_forbidden_for_unresolved")
    if service_reference_status == "resolved" and requested_service_id is None:
        raise OneCallEnvelopeProtocolError("requested_service_id_required_for_resolved")

    if route == "CLARIFY" and clarify_axis == "service":
        if clarify_service_options is None:
            raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")

    if route == "ANSWER":
        if patient_text is None or not patient_text.strip():
            raise OneCallEnvelopeProtocolError("patient_text_required")
        if clarify_axis is not None:
            raise OneCallEnvelopeProtocolError("clarify_axis_forbidden_for_answer")
        if clarify_service_options is not None:
            raise OneCallEnvelopeProtocolError("clarify_service_options_forbidden_for_answer")
    elif route == "ADMIN":
        if patient_text is not None:
            raise OneCallEnvelopeProtocolError("patient_text_forbidden_for_admin")
        if clarify_axis is not None:
            raise OneCallEnvelopeProtocolError("clarify_axis_forbidden_for_admin")
        if clarify_service_options is not None:
            raise OneCallEnvelopeProtocolError("clarify_service_options_forbidden_for_admin")
    elif route == "CLARIFY":
        if patient_text is None or not patient_text.strip():
            raise OneCallEnvelopeProtocolError("patient_text_required")
        if clarify_axis is None:
            raise OneCallEnvelopeProtocolError("clarify_axis_required_for_clarify")

    try:
        return OneCallEnvelope(
            route=route,  # type: ignore[arg-type]
            service_id=service_id,
            extent=extent,  # type: ignore[arg-type]
            jaw=jaw,  # type: ignore[arg-type]
            stage=stage,
            scenario=scenario,  # type: ignore[arg-type]
            commercial_intent=commercial_intent,  # type: ignore[arg-type]
            promotion_scope=promotion_scope,  # type: ignore[arg-type]
            clarify_axis=clarify_axis,  # type: ignore[arg-type]
            clarify_service_options=clarify_service_options,
            patient_text=patient_text,
            service_reference_status=service_reference_status,  # type: ignore[arg-type]
            requested_service_id=requested_service_id,
            references=references,
        )
    except ValueError as exc:
        message = str(exc)
        if message in {
            "patient_text_required",
            "patient_text_forbidden_for_admin",
            "clarify_axis_forbidden_for_answer",
            "clarify_service_options_forbidden_for_answer",
            "clarify_axis_forbidden_for_admin",
            "clarify_service_options_forbidden_for_admin",
            "clarify_axis_required_for_clarify",
            "clarify_service_options_forbidden_for_axis",
            "service_id_invalid",
            "stage_invalid",
            "clarify_service_options_invalid",
            "promotion_scope_forbidden",
            "promotion_scope_invalid",
            "direct_fact_ids_forbidden_for_route",
        }:
            raise OneCallEnvelopeProtocolError(message) from exc
        raise OneCallEnvelopeProtocolError("envelope_invariant_violation") from exc
    except Exception as exc:
        from pydantic import ValidationError

        if isinstance(exc, ValidationError):
            for error in exc.errors():
                message = str(error.get("msg", ""))
                if "Value error, " in message:
                    message = message.split("Value error, ", 1)[1]
                if message in {
                    "patient_text_required",
                    "patient_text_forbidden_for_admin",
                    "clarify_axis_forbidden_for_answer",
                    "clarify_service_options_forbidden_for_answer",
                    "clarify_axis_forbidden_for_admin",
                    "clarify_service_options_forbidden_for_admin",
                    "clarify_axis_required_for_clarify",
                    "clarify_service_options_forbidden_for_axis",
                    "service_id_invalid",
                    "stage_invalid",
                    "clarify_service_options_invalid",
                    "promotion_scope_forbidden",
                    "promotion_scope_invalid",
                    "service_reference_status_invalid",
                    "requested_service_id_invalid",
                    "requested_service_id_forbidden_for_none",
                    "requested_service_id_forbidden_for_unresolved",
                    "requested_service_id_required_for_resolved",
                    "direct_fact_ids_forbidden_for_route",
                }:
                    raise OneCallEnvelopeProtocolError(message) from exc
        raise OneCallEnvelopeProtocolError("envelope_invariant_violation") from exc


def _validate_reference_context(
    envelope: OneCallEnvelope,
    *,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
) -> None:
    if envelope.service_reference_status != "resolved":
        return
    requested = envelope.requested_service_id
    if requested is None:
        raise OneCallEnvelopeProtocolError("requested_service_id_required_for_resolved")
    if requested not in service_reference_catalog.service_ids:
        raise OneCallEnvelopeProtocolError("requested_service_id_invalid")
    if not service_reference_catalog.is_active(requested):
        if envelope.service_id is not None:
            raise OneCallEnvelopeProtocolError("service_id_conflict_inactive_reference")


def _validate_pack_context(
    envelope: OneCallEnvelope,
    *,
    active_service_catalog: ActiveServiceCatalogSnapshot,
) -> None:
    active_ids = active_service_catalog.active_service_ids
    allowed_stages = active_service_catalog.allowed_patient_stages

    if envelope.service_id is not None and envelope.service_id not in active_ids:
        raise OneCallEnvelopeProtocolError("service_id_inactive")

    if envelope.stage is not None and envelope.stage not in allowed_stages:
        raise OneCallEnvelopeProtocolError("stage_not_allowed")

    if envelope.clarify_service_options is not None:
        for option_id in envelope.clarify_service_options:
            if option_id not in active_ids:
                raise OneCallEnvelopeProtocolError("clarify_service_options_invalid")


def envelope_utf8_byte_length(raw: str) -> int:
    try:
        return len(raw.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise OneCallEnvelopeProtocolError("envelope_encoding_invalid") from exc


def _raw_size_exceeded(raw: str) -> bool:
    return envelope_utf8_byte_length(raw) > MAX_ENVELOPE_UTF8_BYTES


def _loads_strict_json_object(raw: str) -> dict[str, Any]:
    seen: set[str] = set()

    def pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        obj: dict[str, Any] = {}
        for key, value in pairs:
            if not isinstance(key, str):
                raise OneCallEnvelopeProtocolError("json_invalid")
            if key in seen:
                raise OneCallEnvelopeProtocolError("json_duplicate_keys")
            seen.add(key)
            obj[key] = value
        return obj

    try:
        payload = json.loads(raw, object_pairs_hook=pairs_hook)
    except json.JSONDecodeError as exc:
        raise OneCallEnvelopeProtocolError("json_invalid") from exc
    if not isinstance(payload, dict):
        raise OneCallEnvelopeProtocolError("envelope_not_object")
    return payload


def parse_production_envelope_json(
    raw: object,
    *,
    active_service_catalog: ActiveServiceCatalogSnapshot,
    service_reference_catalog: ServiceReferenceCatalogSnapshot,
    commercial_fact_catalog: CommercialFactCatalogSnapshot,
) -> OneCallEnvelope:
    """Parse and validate a production v5 envelope from provider raw text."""

    _clear_envelope_input_normalizations()

    if not isinstance(raw, str):
        raise OneCallEnvelopeProtocolError("envelope_output_invalid")
    if not raw.strip():
        raise OneCallEnvelopeProtocolError("envelope_empty")
    if _raw_size_exceeded(raw):
        raise OneCallEnvelopeProtocolError("envelope_oversized")

    payload = _loads_strict_json_object(raw)
    payload, normalization_codes = _normalize_production_payload(payload)
    _record_envelope_input_normalizations(normalization_codes)
    envelope = _validate_structure(payload, commercial_fact_catalog=commercial_fact_catalog)
    _validate_reference_context(
        envelope,
        service_reference_catalog=service_reference_catalog,
    )
    _validate_pack_context(envelope, active_service_catalog=active_service_catalog)
    return envelope


def production_envelope_template(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "route": "ANSWER",
        "service_id": None,
        "extent": None,
        "jaw": None,
        "stage": None,
        "scenario": "none",
        "commercial_intent": "none",
        "promotion_scope": "none",
        "clarify_axis": None,
        "clarify_service_options": None,
        "patient_text": "Probe text.",
        "service_reference_status": "none",
        "requested_service_id": None,
        "references": {"direct_fact_ids": []},
    }
    base.update(overrides)
    return base


def dumps_production_envelope(**overrides: object) -> str:
    return json.dumps(
        production_envelope_template(**overrides),
        ensure_ascii=False,
        separators=(",", ":"),
    )
