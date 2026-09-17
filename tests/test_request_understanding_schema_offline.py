"""Offline schema tests for request_understanding (D1R)."""

from __future__ import annotations

import pytest
import json
import uuid

from core.one_call_envelope_protocol import (
    ENVELOPE_NORMALIZED_NESTED_PRIMARY_PRICE_REQUEST_ID,
    OneCallEnvelopeProtocolError,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot

_EMPTY_CATALOG = ActiveServiceCatalogSnapshot(canonical_json="{}")
_EMPTY_REF_CATALOG = ServiceReferenceCatalogSnapshot(canonical_json="{}")
_EMPTY_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot(canonical_json="{}")

from contracts.request_understanding import (
    RequestUnderstanding,
    RequestUnderstandingRequest,
    RequestUnderstandingSubject,
    minimal_content_understanding,
)


def _parse(payload: dict[str, object]):
    return parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )


def _price_understanding() -> dict[str, object]:
    return {
        "subjects": [],
        "requests": [
            {
                "request_id": "r1",
                "kind": "price",
                "subject_id": None,
                "context": "current_care",
                "policy_ids": [],
                "payment_scheme": "unspecified",
                "payment_scheme_intent": "unspecified",
                "contact_fields": [],
                "content_text": None,
            }
        ],
    }


def test_nested_primary_price_request_id_is_repaired_before_understanding_validation() -> None:
    payload = production_envelope_template(request_understanding=_price_understanding())
    payload.pop("primary_price_request_id")
    payload["request_understanding"]["primary_price_request_id"] = "r1"  # type: ignore[index]
    assert _parse(payload).primary_price_request_id == "r1"


def test_nested_null_primary_price_request_id_is_repaired_before_understanding_validation() -> None:
    payload = production_envelope_template(request_understanding=_price_understanding())
    payload.pop("primary_price_request_id")
    payload["request_understanding"]["primary_price_request_id"] = None  # type: ignore[index]
    assert _parse(payload).primary_price_request_id is None


def test_nested_primary_price_request_id_records_only_its_known_normalization() -> None:
    import app as app_module
    from core import turn_timing

    payload = production_envelope_template(request_understanding=_price_understanding())
    payload.pop("primary_price_request_id")
    payload["request_understanding"]["primary_price_request_id"] = "r1"  # type: ignore[index]
    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        parsed = _parse(payload)
        assert parsed.primary_price_request_id == "r1"
        assert turn_timing.summary_for_turn_complete()["envelope_input_normalizations"] == [
            ENVELOPE_NORMALIZED_NESTED_PRIMARY_PRICE_REQUEST_ID
        ]


@pytest.mark.parametrize(
    ("top_level", "nested"),
    ((None, "r1"), ("r1", None), ("r1", "r2")),
)
def test_conflicting_nested_primary_price_request_id_is_rejected(
    top_level: str | None, nested: str | None,
) -> None:
    payload = production_envelope_template(
        primary_price_request_id=top_level,
        request_understanding=_price_understanding(),
    )
    payload["request_understanding"]["primary_price_request_id"] = nested  # type: ignore[index]
    with pytest.raises(OneCallEnvelopeProtocolError, match="primary_price_request_id_location_conflict"):
        _parse(payload)


def test_matching_nested_primary_price_request_id_is_deduplicated() -> None:
    payload = production_envelope_template(
        primary_price_request_id="r1",
        request_understanding=_price_understanding(),
    )
    payload["request_understanding"]["primary_price_request_id"] = " r1 "  # type: ignore[index]
    assert _parse(payload).primary_price_request_id == "r1"


def test_nested_primary_price_request_id_still_requires_a_price_request() -> None:
    payload = production_envelope_template()
    payload.pop("primary_price_request_id")
    payload["request_understanding"]["primary_price_request_id"] = "r1"  # type: ignore[index]
    with pytest.raises(OneCallEnvelopeProtocolError, match="primary_price_request_id_invalid"):
        _parse(payload)


def test_unknown_nested_understanding_field_is_still_rejected() -> None:
    payload = production_envelope_template()
    payload["request_understanding"]["unknown"] = "x"  # type: ignore[index]
    with pytest.raises(OneCallEnvelopeProtocolError, match="extra_forbidden"):
        _parse(payload)


def test_nested_price_id_keeps_vinirs_price_scenario_on_the_normal_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A misplaced known field must not turn a valid price reply into a technical failure."""
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask

    _enable_demo_nikadent(monkeypatch)
    payload = production_envelope_template(
        patient_text=None,
        service_id="veneers",
        requested_service_id="veneers",
        service_reference_status="resolved",
        commercial_intent="price",
        request_understanding=_price_understanding(),
    )
    payload.pop("primary_price_request_id")
    payload["request_understanding"]["primary_price_request_id"] = "r1"  # type: ignore[index]
    response, backend = _post_ask(
        monkeypatch,
        sid=f"d2-f1-vinirs-{uuid.uuid4().hex}",
        user_message="Сколько стоят виниры?",
        envelope_json=json.dumps(payload, ensure_ascii=False),
        client_id="demo",
    )

    assert backend.call_count == 1
    answer = str(response.get("answer") or "")
    assert "35" in answer.replace("\u00a0", "").replace(" ", "")
    assert "Сейчас не удалось подготовить ответ" not in answer


def test_minimal_content_understanding_valid() -> None:
    u = minimal_content_understanding("Привет.")
    assert len(u.requests) == 1
    assert u.requests[0].kind == "content"
    assert u.requests[0].content_text == "Привет."
    assert u.scope_commitment == "unknown"


@pytest.mark.parametrize("status", ["none", "reported", "correction", "hypothetical"])
def test_scope_commitment_is_typed(status: str) -> None:
    payload = minimal_content_understanding("Ответ.").model_dump()
    payload["scope_commitment"] = status
    assert RequestUnderstanding.model_validate(payload).scope_commitment == status
    payload["scope_commitment"] = "guessed"
    with pytest.raises(ValueError):
        RequestUnderstanding.model_validate(payload)


def test_tooth_count_accepts_only_explicit_positive_integer() -> None:
    payload = minimal_content_understanding("Ответ.").model_dump()
    payload["tooth_count"] = 3
    assert RequestUnderstanding.model_validate(payload).tooth_count == 3
    for invalid in (0, -1, True, 2.5, "3"):
        payload["tooth_count"] = invalid
        with pytest.raises(ValueError):
            RequestUnderstanding.model_validate(payload)


@pytest.mark.parametrize("count,extent", [(2, "one_tooth"), (1, "few_teeth")])
def test_tooth_count_conflicting_with_extent_is_rejected(count: int, extent: str) -> None:
    understanding = minimal_content_understanding("Ответ.").model_dump()
    understanding["tooth_count"] = count
    payload = production_envelope_template(
        extent=extent, request_understanding=understanding,
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="scope_count_extent_conflict"):
        parse_production_envelope_json(
            json.dumps(payload, ensure_ascii=False),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


@pytest.mark.parametrize("count,expected_extent", [(1, "one_tooth"), (3, "few_teeth")])
def test_tooth_count_fills_missing_extent(count: int, expected_extent: str) -> None:
    understanding = minimal_content_understanding("Ответ.").model_dump()
    understanding["tooth_count"] = count
    payload = production_envelope_template(request_understanding=understanding)
    parsed = parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    assert parsed.extent == expected_extent


def test_subject_id_pattern() -> None:
    with pytest.raises(ValueError):
        RequestUnderstandingSubject(subject_id="x1", relation="unknown", age_group="unknown")


def test_unresolved_subject_ref_rejected() -> None:
    with pytest.raises(ValueError, match="subject_id_unresolved"):
        RequestUnderstanding(
            subjects=(),
            requests=(
                RequestUnderstandingRequest(
                    request_id="r1",
                    kind="price",
                    subject_id="s1",
                    context="current_care",
                ),
            ),
        )


def test_empty_subjects_allowed_for_policy() -> None:
    u = RequestUnderstanding(
        subjects=(),
        requests=(
            RequestUnderstandingRequest(
                request_id="r1",
                kind="clinic_policy",
                subject_id=None,
                context="general_information",
                policy_ids=("no_oms",),
            ),
        ),
    )
    assert u.subjects == ()


@pytest.mark.parametrize("route,patient_text,understanding", [
    ("ANSWER", "Да, лечим детей.", None),
    ("ANSWER", "Да, лечим детей.", {"subjects": [], "requests": []}),
    ("CLARIFY", "Уточните услугу.", None),
    ("CLARIFY", "Уточните услугу.", {"subjects": [], "requests": []}),
])
def test_raw_substantive_envelope_requires_requests(route, patient_text, understanding) -> None:
    payload = production_envelope_template(route=route, patient_text=patient_text,
        request_understanding=understanding)
    if route == "CLARIFY":
        payload.update(clarify_axis="extent")
    with pytest.raises(OneCallEnvelopeProtocolError, match="request_understanding_required"):
        parse_production_envelope_json(json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG)


@pytest.mark.parametrize("stream", [False, True])
@pytest.mark.parametrize("understanding", [None, {"subjects": [], "requests": []}, "omitted"])
def test_http_invalid_understanding_fails_closed(monkeypatch, stream, understanding) -> None:
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask, _post_stream
    from session import mem_get, session_client_scope

    _enable_demo_nikadent(monkeypatch)
    sid = f"d1r-r6-{uuid.uuid4().hex}"
    hostile = "Да, лечим детей. Запишем вас."
    payload = production_envelope_template(patient_text=hostile, request_understanding=understanding)
    if understanding == "omitted":
        payload.pop("request_understanding")
    post = _post_stream if stream else _post_ask
    response, backend = post(monkeypatch, sid=sid, user_message="Лечите детей?",
        envelope_json=json.dumps(payload, ensure_ascii=False), client_id="demo")
    assert backend.call_count == 1
    assert hostile not in str(response)
    assert (response.get("meta") or {}).get("lead_step") != "name"
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") != "collecting_name"
