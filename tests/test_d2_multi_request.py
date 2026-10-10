from __future__ import annotations

import json
from datetime import date
from contracts.d2_dialogue_result import ServiceTarget, TopicTarget

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
from core.response_plan_materialization import resolve_d2_operations
from core.d2_published_offer_terms import build_d2_published_offer_terms
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_target_offer_projection import _bundle


def _envelope():
    from tests.test_d2_single_request import _parsed_envelope, _price_request, _content_request
    return _parsed_envelope(requests=[
        _price_request(service_id="service_one",topic_id="implantation"),
        _content_request(content_ref="pain.md",service_id="service_one",topic_id="implantation",request_id="r2"),
    ], commercial_intent="price")


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
    outcome = resolve_d2_operations(
        (_envelope()).blocks, _sources(_bundle()), as_of=date(2026, 9, 18)
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


def test_unknown_content_service_is_a_part_gap() -> None:
    from contracts.d2_dialogue_result import D2DialogueResult
    envelope = D2DialogueResult.model_validate({"outcome": "dialogue", "blocks": [
        {"kind": "price", "request_id": "r1", "target": {"type": "service", "id": "service_one"}},
        {"kind": "content", "request_id": "r2", "target": {"type": "service", "id": "other_service"},
         "content_ref": "pain.md", "content_text": "Неподтверждённый текст."},
    ]})

    outcome = resolve_d2_operations(envelope.blocks, _sources(_bundle()), as_of=date(2026, 9, 18))
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.finalized_commercial_ids.price_offer_ids == tuple(
        row.offer_id for row in outcome.resolved.d2_price_block.rows
    )
    part = outcome.resolved.d2_request_parts[1]
    assert (part.status, part.failure_reason) == ("unavailable", "d2_content_source_missing")
    assert part.service_id is None and part.discussion_scope is None
    assert not outcome.resolved.information_blocks
    assert outcome.resolved.d2_result_status == "degraded"
    assert "Одобренный текст клиники о боли." not in outcome.rendered_text


def test_model_content_text_cannot_replace_bound_authored_source() -> None:
    parsed = _envelope()
    understanding = parsed
    assert understanding is not None
    envelope = parsed.model_copy(
        update={'blocks': (understanding.blocks[0], understanding.blocks[1].model_copy(update={'content_text': '999 999 ₽ и неутверждённое обещание.'}))}
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _sources(_bundle()), as_of=date(2026, 9, 18)
    )

    assert "Одобренный текст клиники о боли." in outcome.rendered_text
    assert "999 999" not in outcome.rendered_text


def test_direction_price_uses_explicit_clinic_mapping_not_exact_service() -> None:
    parsed = _envelope()
    understanding = parsed
    assert understanding is not None
    envelope = parsed.model_copy(
        update={'blocks': (understanding.blocks[0].model_copy(update={'target': TopicTarget(type='topic', id='implantation')}), understanding.blocks[1].model_copy(update={'target': TopicTarget(type='topic', id='implantation')}))}
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _sources(_bundle()), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.response_scope == "topic"
    assert outcome.resolved.session_delta.active_topic_id == "implantation"
    assert outcome.trace.price_candidate_service_ids == ("service_one",)


def test_another_direction_uses_its_own_approved_service_map() -> None:
    parsed = _envelope()
    understanding = parsed
    assert understanding is not None
    envelope = parsed.model_copy(
        update={'blocks': (understanding.blocks[0].model_copy(update={'target': TopicTarget(type='topic', id='therapy')}), understanding.blocks[1].model_copy(update={'content_ref': 'therapy.md', 'target': TopicTarget(type='topic', id='therapy')}))}
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

    outcome = resolve_d2_operations((envelope).blocks, sources, as_of=date(2026, 9, 18))

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

    outcome = resolve_d2_operations((_envelope()).blocks, sources, as_of=date(2026, 9, 18))

    assert [item.button_id for item in outcome.ui_projection.buttons] == ["consult"]
    assert outcome.ui_projection.widget is None
    assert "Можно записаться на консультацию." in outcome.rendered_text
