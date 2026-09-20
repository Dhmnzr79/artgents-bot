"""Offline schema tests for request_understanding (D1R)."""

from __future__ import annotations

import pytest
import json
import uuid

from core.one_call_envelope_protocol import (
    ENVELOPE_NORMALIZED_DUPLICATE_PATIENT_TEXT,
    ENVELOPE_NORMALIZED_NESTED_PRIMARY_PRICE_REQUEST_ID,
    OneCallEnvelopeProtocolError,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)

_EMPTY_CATALOG = ActiveServiceCatalogSnapshot(canonical_json="{}")
_EMPTY_REF_CATALOG = ServiceReferenceCatalogSnapshot(canonical_json="{}")
_EMPTY_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot(canonical_json="{}")

from contracts.request_understanding import (
    RequestTreatmentSituation,
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


def test_ordered_d2_request_parts_preserve_per_part_refs() -> None:
    payload = production_envelope_template(
        patient_text="Служебный текст.",
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    **_price_understanding()["requests"][0],  # type: ignore[index]
                    "service_id": "service_one",
                    "topic_id": "implantation",
                    "statement_mode": "question",
                    "situation": {
                        "scope_commitment": "reported",
                        "extent": "one_tooth",
                        "tooth_count": 1,
                        "jaw": "unknown",
                        "continuity": "new",
                    },
                },
                {
                    "request_id": "r2",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": "Источник выбирается отдельно.",
                    "content_ref": "pain.md",
                    "service_id": "service_one",
                    "topic_id": "implantation",
                    "statement_mode": "hypothesis",
                },
            ],
        },
    )

    parsed = _parse(payload)
    assert [item.request_id for item in parsed.request_understanding.requests] == ["r1", "r2"]
    assert parsed.request_understanding.requests[0].service_id == "service_one"
    assert parsed.request_understanding.requests[0].situation == RequestTreatmentSituation(
        scope_commitment="reported", extent="one_tooth", tooth_count=1,
        jaw="unknown", continuity="new",
    )
    assert parsed.request_understanding.requests[1].content_ref == "pain.md"
    assert parsed.request_understanding.requests[1].statement_mode == "hypothesis"


def test_v19_prompt_contract_requires_a08_typed_request_fields() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 19
    assert "service_id, topic_id, statement_mode, situation" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    assert "situation: null or exactly {scope_commitment, extent, tooth_count, jaw, continuity}" in (
        ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    )
    assert "OMIT request_understanding.scope_commitment and request_understanding.tooth_count entirely" in (
        ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    )


def test_production_parser_rejects_malformed_raw_a08_treatment_situation() -> None:
    raw = production_envelope_template(
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": "s1",
                "context": "current_care", "policy_ids": [], "payment_scheme": "unspecified",
                "payment_scheme_intent": "unspecified", "contact_fields": [], "content_text": None,
                "service_id": None, "topic_id": "implantation", "statement_mode": "question",
                "situation": {
                    "scope_commitment": "reported", "extent": "one_tooth", "tooth_count": 1,
                    "jaw": "unknown", "continuity": "new",
                },
            }],
        },
    )
    parsed = _parse(raw)
    assert parsed.request_understanding.requests[0].situation is not None

    malformed = json.loads(json.dumps(raw))
    malformed["request_understanding"]["requests"][0]["situation"]["continuity"] = "later"
    with pytest.raises(OneCallEnvelopeProtocolError):
        _parse(malformed)


def test_production_parser_defaults_omitted_legacy_summaries_for_typed_situation() -> None:
    raw = production_envelope_template(
        request_understanding={
            "subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": "s1",
                "context": "current_care", "policy_ids": [], "payment_scheme": "unspecified",
                "payment_scheme_intent": "unspecified", "contact_fields": [], "content_text": None,
                "service_id": None, "topic_id": "implantation", "statement_mode": "question",
                "situation": {
                    "scope_commitment": "reported", "extent": "one_tooth", "tooth_count": 1,
                    "jaw": "unknown", "continuity": "new",
                },
            }],
        },
    )

    parsed = _parse(raw)
    assert parsed.request_understanding.scope_commitment == "unknown"
    assert parsed.request_understanding.tooth_count is None


def test_d2_section_refs_use_existing_envelope() -> None:
    request = {
        "request_id": "r1", "kind": "content", "subject_id": None,
        "context": "general_information", "policy_ids": [], "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": "Точный текст.",
        "content_ref": "pain.md", "content_section_refs": ["a:one", "h:2"],
        "service_id": None, "topic_id": None, "statement_mode": "question",
    }
    payload = production_envelope_template(request_understanding={"subjects": [], "requests": [request]})
    assert _parse(payload).request_understanding.requests[0].content_section_refs == ("a:one", "h:2")

    legacy = dict(request)
    legacy.pop("content_section_refs")
    assert _parse(production_envelope_template(request_understanding={"subjects": [], "requests": [legacy]})).request_understanding.requests[0].content_section_refs == ()
    for invalid in (["a:one", "a:one"], [""], "a:one"):
        broken = dict(request)
        broken["content_section_refs"] = invalid
        with pytest.raises(OneCallEnvelopeProtocolError):
            _parse(production_envelope_template(request_understanding={"subjects": [], "requests": [broken]}))


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


def test_duplicate_answer_and_ledger_text_is_normalized_to_one_ledger_copy() -> None:
    import app as app_module
    from core import turn_timing

    payload = production_envelope_template(
        patient_text="Краткое объяснение из материала.",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1",
                "kind": "content",
                "subject_id": None,
                "context": "general_information",
                "policy_ids": [],
                "payment_scheme": "unspecified",
                "payment_scheme_intent": "unspecified",
                "contact_fields": [],
                "content_text": "Краткое объяснение из материала.",
                "content_ref": None,
            }],
        },
    )
    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        parsed = _parse(payload)
        assert parsed.patient_text is None
        assert parsed.request_understanding is not None
        assert parsed.request_understanding.requests[0].content_text == "Краткое объяснение из материала."
        assert turn_timing.summary_for_turn_complete()["envelope_input_normalizations"] == [
            ENVELOPE_NORMALIZED_DUPLICATE_PATIENT_TEXT
        ]


def test_content_ref_is_limited_to_safe_content_requests() -> None:
    request = RequestUnderstandingRequest(
        request_id="r1",
        kind="content",
        subject_id=None,
        context="general_information",
        content_text="Ответ из материала.",
        content_ref="implantation__faq__pain.md",
    )
    assert request.content_ref == "implantation__faq__pain.md"
    with pytest.raises(ValueError, match="content_ref_forbidden"):
        RequestUnderstandingRequest(
            request_id="r1",
            kind="price",
            subject_id=None,
            context="current_care",
            content_ref="implantation__faq__pain.md",
        )
    with pytest.raises(ValueError, match="content_ref_invalid"):
        RequestUnderstandingRequest(
            request_id="r1",
            kind="content",
            subject_id=None,
            context="general_information",
            content_text="Ответ из материала.",
            content_ref="../outside.md",
        )


def test_model_prose_requires_grounded_sections_and_explicit_fallback() -> None:
    request = RequestUnderstandingRequest(
        request_id="r1", kind="content", subject_id=None, context="general_information",
        content_realization="model_prose", content_text="Человеческий текст.",
        content_ref="pain.md", content_section_refs=("a:pain",),
        content_fallback_section_ref="a:pain",
    )
    assert request.content_realization == "model_prose"
    with pytest.raises(ValueError, match="model_prose_grounding_required"):
        request.model_copy(update={"content_section_refs": ()}).__class__.model_validate({
            **request.model_dump(), "content_section_refs": []
        })
    with pytest.raises(ValueError, match="content_fallback_not_grounded"):
        request.__class__.model_validate({
            **request.model_dump(), "content_fallback_section_ref": "a:other"
        })
    with pytest.raises(ValueError, match="extra_forbidden"):
        request.__class__.model_validate({**request.model_dump(), "safe": True})
    assert request.__class__.model_validate({**request.model_dump(), "content_text": ""}).content_text == ""


def test_answered_pain_source_projects_its_video_and_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask

    _enable_demo_nikadent(monkeypatch)
    response, backend = _post_ask(
        monkeypatch,
        sid=f"d2-f2-pain-{uuid.uuid4().hex}",
        user_message="А я боюсь боли",
        envelope_json=json.dumps(production_envelope_template(
            patient_text=None,
            service_id="classic",
            requested_service_id="classic",
            service_reference_status="resolved",
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "unspecified",
                    "contact_fields": [],
                    "content_text": "Страх боли при имплантации — нормальная реакция.",
                    "content_ref": "implantation__faq__pain.md",
                }],
            },
        ), ensure_ascii=False),
        client_id="demo",
    )

    assert backend.call_count == 1
    assert "Страх боли" in str(response.get("answer") or "")
    video = response.get("video") or {}
    assert "pain-doctor-explains" in str(video.get("src") or "")
    refs = {
        str(item.get("ref") or "")
        for item in (response.get("quick_replies") or [])
    }
    assert "implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut" in refs


def test_answered_warranty_source_projects_its_followup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask

    _enable_demo_nikadent(monkeypatch)
    response, backend = _post_ask(
        monkeypatch,
        sid=f"d2-f2-warranty-{uuid.uuid4().hex}",
        user_message="А гарантия у вас есть?",
        envelope_json=json.dumps(production_envelope_template(
            patient_text=None,
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "unspecified",
                    "contact_fields": [],
                    "content_text": "Условия гарантии фиксируются документально.",
                    "content_ref": "clinic__info__warranty.md",
                }],
            },
        ), ensure_ascii=False),
        client_id="demo",
    )

    assert backend.call_count == 1
    assert "гарантии" in str(response.get("answer") or "").casefold()
    refs = {
        str(item.get("ref") or "")
        for item in (response.get("quick_replies") or [])
    }
    assert "clinic__info__warranty.md#chto-delat-esli-voznikla-problema" in refs


def test_unknown_content_ref_keeps_answer_but_projects_no_unrelated_ui(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask

    _enable_demo_nikadent(monkeypatch)
    response, backend = _post_ask(
        monkeypatch,
        sid=f"d2-f2-unknown-source-{uuid.uuid4().hex}",
        user_message="А я боюсь боли",
        envelope_json=json.dumps(production_envelope_template(
            patient_text=None,
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "unspecified",
                    "contact_fields": [],
                    "content_text": "Страх боли при имплантации — нормальная реакция.",
                    "content_ref": "not-in-document-index.md",
                }],
            },
        ), ensure_ascii=False),
        client_id="demo",
    )

    assert backend.call_count == 1
    assert "Страх боли" in str(response.get("answer") or "")
    assert response.get("video") is None
    assert not response.get("quick_replies")


def test_clarify_hides_missing_content_template_and_keeps_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tests.test_one_call_tenant_isolation_offline import _enable_demo_nikadent, _post_ask

    _enable_demo_nikadent(monkeypatch)
    response, backend = _post_ask(
        monkeypatch,
        sid=f"d2-f3-clarify-{uuid.uuid4().hex}",
        user_message="Сколько это стоит?",
        envelope_json=json.dumps(production_envelope_template(
            route="CLARIFY",
            patient_text="Какую услугу вы имеете в виду?",
            clarify_axis="service",
            clarify_service_options=["classic", "veneers"],
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "unspecified",
                    "contact_fields": [],
                    "content_text": None,
                }],
            },
        ), ensure_ascii=False),
        client_id="demo",
    )

    assert backend.call_count == 1
    answer = str(response.get("answer") or "")
    assert answer == "Какую услугу вы имеете в виду?"
    assert "Не могу надёжно ответить" not in answer


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
    payload["patient_text"] = "Стоимость виниров зависит от выбранного материала."
    payload["request_understanding"]["requests"].append({  # type: ignore[index]
        "request_id": "r2",
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "unspecified",
        "contact_fields": [],
        "content_text": "Стоимость виниров зависит от выбранного материала.",
        "content_ref": None,
    })
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
    assert response.get("quick_replies") == []
    assert response.get("video") is None


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


def test_request_treatment_situation_is_strict_and_reset_clears_facts() -> None:
    assert RequestTreatmentSituation(
        scope_commitment="reset",
        extent="unknown",
        tooth_count=None,
        jaw="unknown",
        continuity="new",
    ).scope_commitment == "reset"
    with pytest.raises(ValueError, match="treatment_reset_requires_unknown_facts"):
        RequestTreatmentSituation(
            scope_commitment="reset",
            extent="few_teeth",
            tooth_count=None,
            jaw="unknown",
            continuity="new",
        )


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
