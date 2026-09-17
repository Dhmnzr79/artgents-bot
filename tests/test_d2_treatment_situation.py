"""D2-C3 typed treatment situation stays inside the validated D1R response plan."""

from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.response_plan_materialization import MaterializationContractError
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError, parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_d2_single_request import _sources


_EMPTY_CATALOG = ActiveServiceCatalogSnapshot(canonical_json="{}")
_EMPTY_REF_CATALOG = ServiceReferenceCatalogSnapshot(canonical_json="{}")
_EMPTY_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot(canonical_json="{}")


def _request(*, situation: dict[str, object] | None, subject_id: str | None = "s1", service_id: str | None = None, topic_id: str | None = "implantation") -> dict[str, object]:
    return {
        "request_id": "r1",
        "kind": "price",
        "subject_id": subject_id,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested",
        "contact_fields": [],
        "content_text": None,
        "service_id": service_id,
        "topic_id": topic_id,
        "statement_mode": "question",
        "situation": situation,
    }


def _parse(
    situation: dict[str, object] | None,
    *,
    subject_id: str | None = "s1",
    service_id: str | None = None,
    topic_id: str | None = "implantation",
    patient_text: str = "Любой prose модели.",
    legacy_extent: str | None = None,
    legacy_jaw: str | None = None,
    legacy_scope_commitment: str = "unknown",
    legacy_tooth_count: int | None = None,
):
    subjects: list[dict[str, str]] = []
    if subject_id is not None:
        subjects.append({"subject_id": subject_id, "relation": "other", "age_group": "child"})
    payload = production_envelope_template(
        patient_text=patient_text,
        commercial_intent="price",
        extent=legacy_extent,
        jaw=legacy_jaw,
        request_understanding={
            "subjects": subjects,
            "requests": [_request(situation=situation, subject_id=subject_id, service_id=service_id, topic_id=topic_id)],
            "scope_commitment": legacy_scope_commitment,
            "tooth_count": legacy_tooth_count,
        },
        primary_price_request_id="r1",
    )
    return parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )


def _resolve(envelope):
    return resolve_d2_envelope_response(envelope, _sources(), as_of=date(2026, 9, 18))


def _situation(**overrides: object) -> dict[str, object]:
    return {
        "scope_commitment": "reported",
        "extent": "few_teeth",
        "tooth_count": 3,
        "jaw": "upper",
        "continuity": "unknown",
        **overrides,
    }


def test_plain_price_question_does_not_create_treatment_situation() -> None:
    outcome = _resolve(_parse(None))
    assert outcome.resolved.d2_treatment_situation is None
    assert outcome.situation_delta.action == "keep"


@pytest.mark.parametrize(
    "situation,expected",
    [
        (_situation(extent="one_tooth", tooth_count=1), ("reported", "one_tooth", 1, "upper")),
        (_situation(extent="few_teeth", tooth_count=None), ("reported", "few_teeth", None, "upper")),
        (_situation(), ("reported", "few_teeth", 3, "upper")),
        (_situation(extent="full_arch", tooth_count=None, jaw="upper"), ("reported", "full_arch", None, "upper")),
        (_situation(extent="full_arch", tooth_count=None, jaw="lower"), ("reported", "full_arch", None, "lower")),
        (_situation(extent="full_arch", tooth_count=None, jaw="both"), ("reported", "full_arch", None, "both")),
    ],
)
def test_typed_situation_is_frozen_on_owning_price_request(situation, expected) -> None:
    outcome = _resolve(_parse(situation))
    decision = outcome.resolved.d2_treatment_situation
    assert decision is not None
    assert (decision.scope_commitment, decision.extent, decision.tooth_count, decision.jaw) == expected
    assert decision.source_request_id == "r1"
    assert (decision.subject_relation, decision.subject_age_group) == ("other", "child")
    assert decision.topic_id == "implantation"


@pytest.mark.parametrize("commitment", ["reported", "correction", "hypothetical", "reset"])
def test_commitments_are_distinct_frozen_decisions(commitment: str) -> None:
    situation = _situation(scope_commitment=commitment)
    if commitment == "reset":
        situation.update(extent="unknown", tooth_count=None, jaw="unknown")
    decision = _resolve(_parse(situation)).resolved.d2_treatment_situation
    assert decision is not None
    assert decision.scope_commitment == commitment


def test_question_mode_can_report_treatment_facts() -> None:
    outcome = _resolve(_parse(_situation(extent="one_tooth", tooth_count=1)))
    assert outcome.resolved.d2_treatment_situation is not None
    assert outcome.resolved.d2_treatment_situation.scope_commitment == "reported"


def test_all_unknown_null_situation_stays_explicit_and_does_not_infer_scope() -> None:
    decision = _resolve(
        _parse(
            _situation(
                scope_commitment="unknown",
                extent="unknown",
                tooth_count=None,
                jaw="unknown",
            )
        )
    ).resolved.d2_treatment_situation
    assert decision is not None
    assert (decision.scope_commitment, decision.extent, decision.tooth_count, decision.jaw) == (
        "unknown",
        "unknown",
        None,
        "unknown",
    )


def test_full_arch_with_explicit_count_remains_full_arch() -> None:
    decision = _resolve(
        _parse(_situation(extent="full_arch", tooth_count=12, jaw="both"))
    ).resolved.d2_treatment_situation
    assert decision is not None
    assert (decision.extent, decision.tooth_count, decision.jaw) == ("full_arch", 12, "both")


@pytest.mark.parametrize(
    "situation,subject_id",
    [
        (_situation(extent="one_tooth", tooth_count=2), "s1"),
        (_situation(extent="few_teeth", tooth_count=1), "s1"),
        (_situation(extent="unknown", tooth_count=3), "s1"),
        (_situation(scope_commitment="reset"), "s1"),
        (_situation(continuity="same"), None),
    ],
)
def test_invalid_typed_situation_is_rejected_at_d1r_boundary(situation, subject_id) -> None:
    with pytest.raises(OneCallEnvelopeProtocolError):
        _parse(situation, subject_id=subject_id)


@pytest.mark.parametrize("count", [True, 2.5, "3", 0])
def test_nested_tooth_count_requires_positive_strict_integer(count: object) -> None:
    with pytest.raises(OneCallEnvelopeProtocolError):
        _parse(_situation(tooth_count=count))


def test_legacy_request_understanding_fields_conflict_with_nested_situation() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError, match="treatment_situation_legacy_conflict"):
        _parse(_situation(), legacy_scope_commitment="reported")
    with pytest.raises(OneCallEnvelopeProtocolError, match="treatment_situation_legacy_conflict"):
        _parse(_situation(), legacy_tooth_count=3)


def test_two_nested_situations_are_rejected() -> None:
    payload = production_envelope_template(
        commercial_intent="price",
        request_understanding={
            "subjects": [],
            "requests": [
                _request(situation=_situation(), subject_id=None),
                {**_request(situation=_situation(), subject_id=None), "request_id": "r2"},
            ],
        },
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="treatment_situation_multiple"):
        parse_production_envelope_json(json.dumps(payload), active_service_catalog=_EMPTY_CATALOG, service_reference_catalog=_EMPTY_REF_CATALOG, commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG)


def test_situation_refs_use_current_d2_resolver_snapshot() -> None:
    with pytest.raises(MaterializationContractError, match="d2_treatment_service_topic_mismatch"):
        _resolve(_parse(_situation(), service_id="service_two", topic_id="implantation"))


def test_legacy_envelope_axes_and_model_prose_do_not_change_frozen_decision() -> None:
    first = _resolve(_parse(_situation(), legacy_extent="one_tooth", legacy_jaw="lower", patient_text="Первый prose."))
    second = _resolve(_parse(_situation(), legacy_extent="full_arch", legacy_jaw="both", patient_text="Совсем другой prose."))
    assert first.resolved.d2_treatment_situation == second.resolved.d2_treatment_situation


def test_situation_decision_and_rendering_stay_frozen_after_snapshot_mutation() -> None:
    sources = _sources()
    outcome = resolve_d2_envelope_response(_parse(_situation()), sources, as_of=date(2026, 9, 18))
    rendered, ui = outcome.rendered_text, outcome.ui_projection
    sources.material_authority.bundle.services.clear()
    sources.material_authority.bundle.offers.clear()
    assert render_response_text(outcome.resolved) == rendered
    assert project_response_ui(outcome.resolved) == ui
    assert outcome.resolved.d2_treatment_situation is not None
