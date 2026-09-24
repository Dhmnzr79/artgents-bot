from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from contracts.response_plan import (
    ComposerResult,
    RequiredOfferConditionBlock,
    ResolvedResponsePlan,
    SessionKey,
)
from contracts.response_plan_materialization import (
    D2AuthoredContentAuthority,
    D2DirectionAuthority,
    D2PartFailureAuthority,
    MaterializationContractError,
    OfferConditionEvidence,
    ResponsePlanMaterializationSources,
)
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.d2_published_offer_terms import build_d2_published_offer_terms
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_target_offer_projection import _bundle


def _parsed_envelope(*, requests: list[dict[str, object]], commercial_intent: str) -> object:
    payload = production_envelope_template(
        patient_text="Служебный текст D1R.",
        commercial_intent=commercial_intent,
        request_understanding={"subjects": [], "requests": requests},
        primary_price_request_id="r1" if commercial_intent == "price" else None,
    )
    return parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=ActiveServiceCatalogSnapshot(canonical_json="{}"),
        service_reference_catalog=ServiceReferenceCatalogSnapshot(canonical_json="{}"),
        commercial_fact_catalog=CommercialFactCatalogSnapshot(canonical_json="{}"),
    )


def _price_request(
    *, service_id: str | None, topic_id: str | None, request_id: str = "r1"
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": "price",
        "subject_id": None,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested",
        "contact_fields": [],
        "content_text": None,
        "service_id": service_id,
        "topic_id": topic_id,
        "statement_mode": "question",
    }


def _content_request(
    *, content_ref: str, service_id: str | None, topic_id: str | None, request_id: str = "r1"
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested",
        "contact_fields": [],
        "content_text": "Смысловой текст модели не является источником ответа.",
        "content_ref": content_ref,
        "service_id": service_id,
        "topic_id": topic_id,
        "statement_mode": "question",
    }


def _sources(*, content: tuple[D2AuthoredContentAuthority, ...] = ()) -> ResponsePlanMaterializationSources:
    bundle = _bundle()
    condition_evidence = {
        offer.offer_id: OfferConditionEvidence(
            source_client_id="demo",
            offer_id=offer.offer_id,
            completeness="complete",
            conditions=(
                RequiredOfferConditionBlock(
                    source_client_id="demo",
                    condition_id="package_includes",
                    completeness="complete",
                    display_text=f"Условие для {offer.offer_id}.",
                ),
            ),
        )
        for offer in bundle.offers
        if offer.active
    }
    return ResponsePlanMaterializationSources(
        session_key=SessionKey(client_id="demo", sid="d2-c2"),
        context_strategy="full_context",
        material_authority=PostComposerMaterialAuthority(
            source_client_id="demo", bundle=bundle
        ),
        condition_evidence_by_offer=condition_evidence,
        d2_published_terms_by_offer={
            offer.offer_id: build_d2_published_offer_terms(offer=offer, source_client_id="demo")
            for offer in bundle.offers
        },
        d2_authored_content=content,
        d2_directions=(
            D2DirectionAuthority(
                source_client_id="demo",
                topic_id="implantation",
                service_ids=("service_one",),
            ),
            D2DirectionAuthority(
                source_client_id="demo",
                topic_id="therapy",
                service_ids=("service_two",),
            ),
        ),
        d2_part_failures=(
            D2PartFailureAuthority(
                source_client_id="demo",
                message_id="price-incomplete",
                reason="d2_no_price_candidates",
                display_text="Стоимость сейчас недоступна.",
            ),
            D2PartFailureAuthority(
                source_client_id="demo",
                message_id="price-scope",
                reason="d2_no_scope_price_candidates",
                display_text="Нет подходящей опубликованной цены.",
            ),
        ),
    )


def test_standalone_direction_price_freezes_rows_and_real_conditions() -> None:
    envelope = _parsed_envelope(
        requests=[_price_request(service_id=None, topic_id="implantation")],
        commercial_intent="price",
    )

    outcome = resolve_d2_envelope_response(envelope, _sources(), as_of=date(2026, 9, 18))

    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.information_blocks == ()
    assert outcome.resolved.response_scope == "topic"
    assert outcome.resolved.session_delta.active_topic_id == "implantation"
    assert 1 <= len(outcome.resolved.d2_price_block.rows) <= 3
    assert all(row.condition_texts for row in outcome.resolved.d2_price_block.rows)
    assert "Exact include" in outcome.rendered_text
    assert outcome.trace.price_candidate_service_ids == ("service_one",)


def test_standalone_exact_service_price_uses_the_same_d1r_path() -> None:
    envelope = _parsed_envelope(
        requests=[_price_request(service_id="service_two", topic_id="therapy")],
        commercial_intent="price",
    )

    outcome = resolve_d2_envelope_response(envelope, _sources(), as_of=date(2026, 9, 18))

    assert outcome.resolved.response_scope == "service"
    assert outcome.resolved.session_delta.active_service_id == "service_two"
    assert outcome.trace.price_candidate_service_ids == ("service_two",)
    assert outcome.resolved.d2_price_block is not None
    assert {row.service_id for row in outcome.resolved.d2_price_block.rows} == {"service_two"}


def test_standalone_price_ignores_legacy_unknown_condition_evidence() -> None:
    envelope = _parsed_envelope(
        requests=[_price_request(service_id="service_one", topic_id="implantation")],
        commercial_intent="price",
    )
    source = _sources().model_copy(
        update={
            "condition_evidence_by_offer": {
                "generic_fixed": OfferConditionEvidence(
                    source_client_id="demo", offer_id="generic_fixed", completeness="unknown"
                )
            }
        }
    )

    outcome = resolve_d2_envelope_response(envelope, source, as_of=date(2026, 9, 18))
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[0].failure_reason is None
    assert outcome.resolved.d2_price_block is not None


def test_standalone_global_content_has_no_price_and_is_frozen() -> None:
    live_text = "Врач подбирает обезболивание индивидуально после осмотра."
    request = _content_request(content_ref="pain.md", service_id=None, topic_id=None)
    request["content_text"] = live_text
    envelope = _parsed_envelope(
        requests=[request],
        commercial_intent="none",
    )
    source = _sources(
        content=(
            D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="pain.md",
                display_text="Одобренный текст о боли.",
            ),
        )
    )

    outcome = resolve_d2_envelope_response(envelope, source, as_of=date(2026, 9, 18))

    assert outcome.resolved.d2_price_block is None
    assert outcome.resolved.price_block is None
    assert outcome.resolved.response_scope == "clinic"
    assert outcome.rendered_text == live_text
    assert outcome.trace.selected_offers == ()
    assert render_response_text(outcome.resolved) == outcome.rendered_text
    assert project_response_ui(outcome.resolved) == outcome.ui_projection


def test_frozen_d2_plan_does_not_reread_mutated_source_snapshots() -> None:
    envelope = _parsed_envelope(
        requests=[_price_request(service_id="service_one", topic_id="implantation")],
        commercial_intent="price",
    )
    source = _sources()
    outcome = resolve_d2_envelope_response(envelope, source, as_of=date(2026, 9, 18))
    rendered = outcome.rendered_text
    projection = outcome.ui_projection

    source.material_authority.bundle.services.clear()
    source.material_authority.bundle.offers.clear()
    source.condition_evidence_by_offer.clear()

    assert render_response_text(outcome.resolved) == rendered
    assert project_response_ui(outcome.resolved) == projection


def test_empty_final_answer_stays_invalid_while_standalone_price_is_valid() -> None:
    envelope = _parsed_envelope(
        requests=[_price_request(service_id="service_one", topic_id="implantation")],
        commercial_intent="price",
    )
    outcome = resolve_d2_envelope_response(envelope, _sources(), as_of=date(2026, 9, 18))
    assert outcome.resolved.d2_price_block is not None

    empty_payload = outcome.resolved.model_dump()
    empty_payload.update(
        {
            "patient_text": None,
            "information_blocks": [],
            "price_block": None,
            "d2_price_block": None,
        }
    )
    with pytest.raises(ValidationError, match="answer_requires_patient_text"):
        ResolvedResponsePlan.model_validate(empty_payload)


@pytest.mark.parametrize(
    ("route", "mode", "patient_text"),
    (
        ("ANSWER", "contacts", None),
        ("ADMIN", "standard", None),
        ("CLARIFY", "standard", "Уточните."),
    ),
)
def test_visible_price_cannot_weaken_terminal_or_clarify_invariants(
    route: str,
    mode: str,
    patient_text: str | None,
) -> None:
    with pytest.raises(ValidationError):
        ComposerResult(
            route=route,  # type: ignore[arg-type]
            mode=mode,  # type: ignore[arg-type]
            patient_text=patient_text,
            visible_price_block=True,
        )


def test_restricted_content_without_a_service_or_topic_is_rejected() -> None:
    authored_request = _content_request(content_ref="warranty.md", service_id=None, topic_id=None)
    authored_request["content_realization"] = "authored"
    envelope = _parsed_envelope(
        requests=[authored_request],
        commercial_intent="none",
    )
    source = _sources(
        content=(
            D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="warranty.md",
                display_text="Одобренный текст о гарантии.",
                allowed_service_ids=("service_one",),
            ),
        )
    )

    with pytest.raises(MaterializationContractError, match="d2_content_scope_required"):
        resolve_d2_envelope_response(envelope, source, as_of=date(2026, 9, 18))


def test_direct_d2_path_does_not_call_the_legacy_materialization_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.response_plan_materialization as materialization

    envelope = _parsed_envelope(
        requests=[_price_request(service_id="service_one", topic_id="implantation")],
        commercial_intent="price",
    )

    def _legacy_called(*_args, **_kwargs):
        raise AssertionError("legacy materialization entry must stay unreachable")

    monkeypatch.setattr(materialization, "resolve_materialized_response", _legacy_called)
    outcome = materialization.resolve_d2_envelope_response(
        envelope, _sources(), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.d2_price_block is not None
