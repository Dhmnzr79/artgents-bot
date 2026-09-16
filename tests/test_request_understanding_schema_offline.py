"""Offline schema tests for request_understanding (D1R)."""

from __future__ import annotations

import pytest
import json
import uuid

from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError, parse_production_envelope_json, production_envelope_template
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


def test_minimal_content_understanding_valid() -> None:
    u = minimal_content_understanding("Привет.")
    assert len(u.requests) == 1
    assert u.requests[0].kind == "content"
    assert u.requests[0].content_text == "Привет."


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
