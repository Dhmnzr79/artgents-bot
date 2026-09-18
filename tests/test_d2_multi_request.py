from __future__ import annotations

import json
from datetime import date

from contracts.response_plan import SessionKey
from contracts.response_plan_adapter import (
    ResponsePlanAdapterTextualCtaAuthority,
    ResponsePlanAdapterUiAuthority,
    ResponsePlanAdapterUiButtonAuthority,
    ResponsePlanAdapterUiWidgetAuthority,
)
from contracts.response_plan_materialization import (
    D2AuthoredContentAuthority,
    D2DirectionAuthority,
    OfferConditionEvidence,
    ResponsePlanMaterializationSources,
)
from contracts.response_plan_post_composer import PostComposerMaterialAuthority
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.response_plan_materialization import resolve_d2_envelope_response
from core.d2_published_offer_terms import build_d2_published_offer_terms
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_target_offer_projection import _bundle


def _envelope():
    payload = production_envelope_template(
        patient_text="Служебный текст D1R.",
        commercial_intent="price",
        request_understanding={
            "subjects": [],
            "requests": [
                {
                    "request_id": "r1",
                    "kind": "price",
                    "subject_id": None,
                    "context": "general_information",
                    "policy_ids": [],
                    "payment_scheme": "unspecified",
                    "payment_scheme_intent": "not_requested",
                    "contact_fields": [],
                    "content_text": None,
                    "service_id": "service_one",
                    "topic_id": "implantation",
                    "statement_mode": "question",
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
                    "content_text": "Текст выбирается из утверждённого материала.",
                    "content_ref": "pain.md",
                    "service_id": "service_one",
                    "topic_id": "implantation",
                    "statement_mode": "question",
                },
            ],
        },
        primary_price_request_id="r1",
    )
    return parse_production_envelope_json(
        json.dumps(payload, ensure_ascii=False),
        active_service_catalog=ActiveServiceCatalogSnapshot(canonical_json="{}"),
        service_reference_catalog=ServiceReferenceCatalogSnapshot(canonical_json="{}"),
        commercial_fact_catalog=CommercialFactCatalogSnapshot(canonical_json="{}"),
    )


def _sources(bundle):
    return ResponsePlanMaterializationSources(
        session_key=SessionKey(client_id="demo", sid="d2-s1"),
        context_strategy="full_context",
        material_authority=PostComposerMaterialAuthority(
            source_client_id="demo", bundle=bundle
        ),
        condition_evidence_by_offer={
            offer.offer_id: OfferConditionEvidence(
                source_client_id="demo",
                offer_id=offer.offer_id,
                completeness="complete",
                conditions=(),
            )
            for offer in bundle.offers
            if offer.active
        },
        d2_published_terms_by_offer={
            offer.offer_id: build_d2_published_offer_terms(offer=offer, source_client_id="demo")
            for offer in bundle.offers
        },
        d2_authored_content=(
            D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="pain.md",
                display_text="Одобренный текст клиники о боли.",
                allowed_service_ids=("service_one",),
            ),
        ),
        d2_directions=(
            D2DirectionAuthority(
                source_client_id="demo",
                topic_id="implantation",
                service_ids=("service_one",),
            ),
        ),
    )


def test_price_plus_content_uses_one_d1r_envelope_and_frozen_plan() -> None:
    outcome = resolve_d2_envelope_response(
        _envelope(), _sources(_bundle()), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.price_block is None
    assert outcome.resolved.d2_price_block is not None
    assert 1 <= len(outcome.resolved.d2_price_block.rows) <= 3
    assert outcome.resolved.information_blocks[0].content_ref == "pain.md"
    assert outcome.rendered_text.endswith("Одобренный текст клиники о боли.")
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert outcome.resolved.session_delta.shown_price_offer_ids == tuple(
        row.offer_id for row in outcome.resolved.d2_price_block.rows
    )


def test_content_for_another_service_is_rejected() -> None:
    envelope = _envelope().model_copy(
        update={
            "request_understanding": _envelope().request_understanding.model_copy(
                update={
                    "requests": (
                        _envelope().request_understanding.requests[0],
                        _envelope().request_understanding.requests[1].model_copy(
                            update={"service_id": "other_service"}
                        ),
                    )
                }
            )
        }
    )

    from contracts.response_plan_materialization import MaterializationContractError

    try:
        resolve_d2_envelope_response(envelope, _sources(_bundle()), as_of=date(2026, 9, 18))
    except MaterializationContractError as error:
        assert str(error) == "d2_content_service_mismatch"
    else:  # pragma: no cover - assertion helper
        raise AssertionError("foreign content service was accepted")


def test_model_content_text_cannot_replace_bound_authored_source() -> None:
    parsed = _envelope()
    understanding = parsed.request_understanding
    assert understanding is not None
    envelope = parsed.model_copy(
        update={
            "request_understanding": understanding.model_copy(
                update={
                    "requests": (
                        understanding.requests[0],
                        understanding.requests[1].model_copy(
                            update={"content_text": "999 999 ₽ и неутверждённое обещание."}
                        ),
                    )
                }
            )
        }
    )

    outcome = resolve_d2_envelope_response(
        envelope, _sources(_bundle()), as_of=date(2026, 9, 18)
    )

    assert "Одобренный текст клиники о боли." in outcome.rendered_text
    assert "999 999" not in outcome.rendered_text


def test_direction_price_uses_explicit_clinic_mapping_not_exact_service() -> None:
    parsed = _envelope()
    understanding = parsed.request_understanding
    assert understanding is not None
    envelope = parsed.model_copy(
        update={
            "request_understanding": understanding.model_copy(
                update={
                    "requests": (
                        understanding.requests[0].model_copy(update={"service_id": None}),
                        understanding.requests[1].model_copy(update={"service_id": None}),
                    )
                }
            )
        }
    )

    outcome = resolve_d2_envelope_response(
        envelope, _sources(_bundle()), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.response_scope == "topic"
    assert outcome.resolved.session_delta.active_topic_id == "implantation"
    assert outcome.trace.price_candidate_service_ids == ("service_one",)


def test_another_direction_uses_its_own_approved_service_map() -> None:
    parsed = _envelope()
    understanding = parsed.request_understanding
    assert understanding is not None
    envelope = parsed.model_copy(
        update={
            "request_understanding": understanding.model_copy(
                update={
                    "requests": (
                        understanding.requests[0].model_copy(
                            update={"service_id": None, "topic_id": "therapy"}
                        ),
                        understanding.requests[1].model_copy(
                            update={
                                "service_id": None,
                                "topic_id": "therapy",
                                "content_ref": "therapy.md",
                            }
                        ),
                    )
                }
            )
        }
    )
    base = _sources(_bundle())
    sources = base.model_copy(
        update={
            "d2_authored_content": (*base.d2_authored_content, D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="therapy.md",
                display_text="Одобренный текст второго направления.",
                allowed_service_ids=("service_two",),
            )),
            "d2_directions": (*base.d2_directions, D2DirectionAuthority(
                source_client_id="demo", topic_id="therapy", service_ids=("service_two",)
            )),
        }
    )

    outcome = resolve_d2_envelope_response(envelope, sources, as_of=date(2026, 9, 18))

    assert outcome.resolved.session_delta.active_topic_id == "therapy"
    assert outcome.trace.price_candidate_service_ids == ("service_two",)
    assert "Одобренный текст второго направления." in outcome.rendered_text


def test_price_suppresses_available_secondary_ui_but_keeps_selected_cta() -> None:
    sources = _sources(_bundle()).model_copy(
        update={
            "ui_authority": ResponsePlanAdapterUiAuthority(
                source_client_id="demo",
                buttons=(
                    ResponsePlanAdapterUiButtonAuthority(
                        source_client_id="demo",
                        button_id="consult",
                        label="Записаться",
                        action_kind="cta",
                    ),
                    ResponsePlanAdapterUiButtonAuthority(
                        source_client_id="demo",
                        button_id="watch",
                        label="Видео",
                        action_kind="video",
                    ),
                ),
                widget=ResponsePlanAdapterUiWidgetAuthority(
                    source_client_id="demo", widget_offer_id="secondary_widget"
                ),
            ),
            "textual_cta_authority": ResponsePlanAdapterTextualCtaAuthority(
                source_client_id="demo", text="Можно записаться на консультацию."
            ),
        }
    )

    outcome = resolve_d2_envelope_response(_envelope(), sources, as_of=date(2026, 9, 18))

    assert [item.button_id for item in outcome.ui_projection.buttons] == ["consult"]
    assert outcome.ui_projection.widget is None
    assert "Можно записаться на консультацию." in outcome.rendered_text
