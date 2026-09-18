from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.response_plan_materialization import (
    D2DirectionPricePresentation,
    D2PartFailureAuthority,
    D2VolumeChoice,
    ResponsePlanMaterializationSources,
)
from contracts.response_plan import UiQuickReplyCandidate
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


def _envelope(situation: dict[str, object] | None):
    payload = production_envelope_template(
        commercial_intent="price",
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": None,
                "context": "general_information", "policy_ids": [],
                "payment_scheme": "unspecified", "payment_scheme_intent": "not_requested",
                "contact_fields": [], "content_text": None, "service_id": None,
                "topic_id": "implantation", "statement_mode": "question", "situation": situation,
            }],
        }, primary_price_request_id="r1",
    )
    return parse_production_envelope_json(
        json.dumps(payload), active_service_catalog=ActiveServiceCatalogSnapshot(canonical_json="{}"),
        service_reference_catalog=ServiceReferenceCatalogSnapshot(canonical_json="{}"),
        commercial_fact_catalog=CommercialFactCatalogSnapshot(canonical_json="{}"),
    )


def _sources_with_scope_metadata() -> ResponsePlanMaterializationSources:
    bundle_payload = _bundle().model_dump()
    for offer in bundle_payload["offers"]:
        if offer["offer_id"] == "generic_fixed":
            offer["applies_to_extents"] = ["one_tooth"]
        elif offer["offer_id"] == "option_a_from":
            offer["applies_to_extents"] = ["few_teeth"]
        elif offer["offer_id"] == "option_c_range":
            offer["applies_to_extents"] = ["full_arch"]
    base = _sources(_bundle().__class__.model_validate(bundle_payload))
    payload = base.model_dump()
    payload["d2_direction_price_presentations"] = [
        D2DirectionPricePresentation(
            source_client_id="demo", topic_id="implantation", introduction_text="Цены направления.",
            unknown_extent_text="Выберите объём, если он важен.",
            volume_choices=tuple(
                D2VolumeChoice(
                    extent=extent,
                    candidate=UiQuickReplyCandidate(source_client_id="demo", reply_id=f"scope_{extent}", label=label),
                )
                for extent, label in (
                    ("one_tooth", "Один зуб"), ("few_teeth", "Несколько зубов"),
                    ("full_arch", "Вся челюсть"), ("unknown", "Не знаю"),
                )
            ),
        ).model_dump()
    ]
    return ResponsePlanMaterializationSources.model_validate(payload)


def _situation(extent: str, commitment: str = "reported") -> dict[str, object]:
    return {"scope_commitment": commitment, "extent": extent, "tooth_count": None, "jaw": "unknown", "continuity": "unknown"}


def _with_scope_failure_authority(sources: ResponsePlanMaterializationSources) -> ResponsePlanMaterializationSources:
    payload = sources.model_dump()
    payload["d2_part_failures"] = [
        D2PartFailureAuthority(
            source_client_id="demo",
            message_id="price-scope",
            reason="d2_no_scope_price_candidates",
            display_text="Нет подходящей опубликованной цены.",
        ).model_dump()
    ]
    return ResponsePlanMaterializationSources.model_validate(payload)


def test_direction_overview_freezes_authority_text_and_choices() -> None:
    outcome = resolve_d2_envelope_response(_envelope(None), _sources_with_scope_metadata(), as_of=date(2026, 9, 18))
    decision = outcome.resolved.d2_price_scope_decision
    assert decision is not None and decision.reason == "overview"
    assert [item.reply_id for item in outcome.ui_projection.quick_replies] == [
        "scope_one_tooth", "scope_few_teeth", "scope_full_arch", "scope_unknown"
    ]
    assert "Цены направления." in outcome.rendered_text
    assert "Выберите объём" in outcome.rendered_text


@pytest.mark.parametrize("commitment", ["reported", "correction", "hypothetical"])
def test_known_situation_filters_before_top_three_and_keeps_money_unchanged(commitment: str) -> None:
    outcome = resolve_d2_envelope_response(
        _envelope(_situation("few_teeth", commitment)), _sources_with_scope_metadata(), as_of=date(2026, 9, 18)
    )
    assert outcome.resolved.d2_price_scope_decision is not None
    assert outcome.resolved.d2_price_scope_decision.applied_extent == "few_teeth"
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["option_a_from"]
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.situation_delta.action == "keep"


def test_known_scope_stays_strict_without_optional_presentation() -> None:
    bundle_payload = _bundle().model_dump()
    for offer in bundle_payload["offers"]:
        if offer["offer_id"] == "option_a_from":
            offer["applies_to_extents"] = ["few_teeth"]
    outcome = resolve_d2_envelope_response(
        _envelope(_situation("few_teeth")), _sources(_bundle().__class__.model_validate(bundle_payload)),
        as_of=date(2026, 9, 18),
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["option_a_from"]


def test_explicit_unknown_and_reset_do_not_repeat_volume_menu() -> None:
    for situation in (_situation("unknown"), _situation("unknown", "reset")):
        outcome = resolve_d2_envelope_response(
            _envelope(situation), _sources_with_scope_metadata(), as_of=date(2026, 9, 18)
        )
        assert outcome.resolved.d2_price_scope_decision is not None
        assert outcome.resolved.d2_price_scope_decision.reason == "overview"
        assert outcome.ui_projection.quick_replies == ()


def test_missing_scope_metadata_cannot_publish_known_scope_price() -> None:
    sources = _sources(_bundle()).model_copy(
        update={
            "d2_direction_price_presentations": (
                _sources_with_scope_metadata().d2_direction_price_presentations[0],
            )
        }
    )
    outcome = resolve_d2_envelope_response(
        _envelope(_situation("few_teeth")), _with_scope_failure_authority(sources), as_of=date(2026, 9, 18)
    )
    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_no_scope_price_candidates"


def test_missing_scope_metadata_is_strict_even_without_presentation() -> None:
    outcome = resolve_d2_envelope_response(
        _envelope(_situation("few_teeth")), _with_scope_failure_authority(_sources(_bundle())), as_of=date(2026, 9, 18)
    )
    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_price_block is None


def test_fourth_ranked_eligible_offer_is_not_lost_before_scope_filter() -> None:
    payload = _bundle(no_public_active=True).model_dump()
    for offer in payload["offers"]:
        offer["applies_to_extents"] = ["one_tooth"]
        if offer["offer_id"] == "generic_no_public":
            offer["applies_to_extents"] = ["few_teeth"]
    payload["strategy"]["default_offer_priorities"]["generic_no_public"] = 1
    source = _sources(_bundle().__class__.model_validate(payload))
    outcome = resolve_d2_envelope_response(
        _envelope(_situation("few_teeth")), source, as_of=date(2026, 9, 18)
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["generic_no_public"]
