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
from core.response_plan_materialization import resolve_d2_operations
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


def _envelope(volume, *, topic_id="implantation", subject_id=None):
    from contracts.d2_dialogue_result import D2DialogueResult
    return D2DialogueResult.model_validate({"outcome":"dialogue","blocks":[{
        "request_id":"r1","kind":"price","target":{"type":"topic","id":topic_id},"volume":volume,
    }]})


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


def _volume(extent):
    return {"extent":extent,"tooth_count":None,"jaw":"unknown"}


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


def _cross_topic_sources() -> ResponsePlanMaterializationSources:
    payload = _sources_with_scope_metadata().model_dump()
    payload["d2_directions"] = [*payload["d2_directions"], {
        "source_client_id": "demo", "topic_id": "prosthetics", "service_ids": ["service_two"],
    }]
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["applies_to_extents"] = ["one_tooth"]
        if offer["offer_id"] == "generic_fixed":
            offer["service_id"] = "service_two"
        if offer["offer_id"] == "other_offer":
            offer["applies_to_extents"] = ["few_teeth"]
    return ResponsePlanMaterializationSources.model_validate(payload)


def test_direction_overview_freezes_authority_text_and_choices() -> None:
    outcome = resolve_d2_operations((_envelope(None)).blocks, _sources_with_scope_metadata(), as_of=date(2026, 9, 18))
    decision = outcome.resolved.d2_price_scope_decision
    assert decision is not None and decision.reason == "overview"
    assert [item.reply_id for item in outcome.ui_projection.quick_replies] == [
        "scope_one_tooth", "scope_few_teeth", "scope_full_arch", "scope_unknown"
    ]
    assert "Цены направления." in outcome.rendered_text
    assert "Выберите объём" in outcome.rendered_text


def test_known_volume_filters_before_top_three_and_keeps_money_unchanged() -> None:
    outcome = resolve_d2_operations(
        (_envelope(_volume("few_teeth"))).blocks, _sources_with_scope_metadata(), as_of=date(2026, 9, 18)
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
    outcome = resolve_d2_operations(
        (_envelope(_volume("few_teeth"))).blocks, _sources(_bundle().__class__.model_validate(bundle_payload)),
        as_of=date(2026, 9, 18),
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["option_a_from"]


def test_explicit_unknown_and_reset_do_not_repeat_volume_menu() -> None:
    for situation in (_volume("unknown"), _volume("unknown")):
        outcome = resolve_d2_operations(
            (_envelope(situation)).blocks, _sources_with_scope_metadata(), as_of=date(2026, 9, 18)
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
    outcome = resolve_d2_operations(
        (_envelope(_volume("few_teeth"))).blocks, _with_scope_failure_authority(sources), as_of=date(2026, 9, 18)
    )
    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_no_scope_price_candidates"


def test_missing_scope_metadata_is_strict_even_without_presentation() -> None:
    outcome = resolve_d2_operations(
        (_envelope(_volume("few_teeth"))).blocks, _with_scope_failure_authority(_sources(_bundle())), as_of=date(2026, 9, 18)
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
    outcome = resolve_d2_operations(
        (_envelope(_volume("few_teeth"))).blocks, source, as_of=date(2026, 9, 18)
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["generic_no_public"]


@pytest.mark.parametrize("extent", ["one_tooth", "few_teeth", "unknown"])
def test_destination_price_uses_only_volume_on_current_operation(extent):
    task = _envelope(_volume(extent),topic_id="prosthetics")
    sources = _cross_topic_sources()
    # Synthetic destination catalog explicitly lists its approved offer order.
    sources = sources.model_copy(update={"d2_directions": tuple(
        d.model_copy(update={"ordered_offer_ids": tuple(o.offer_id for o in sources.material_authority.bundle.offers if o.service_id in d.service_ids and o.active)})
        for d in sources.d2_directions)})
    result = resolve_d2_operations(task.blocks,sources,as_of=date(2026,9,18)).resolved
    assert result.d2_request_parts[0].discussion_scope.volume.extent == extent
    ids={row.offer_id for row in result.d2_price_block.rows}
    if extent == "one_tooth": assert ids == {"generic_fixed"}
    if extent == "few_teeth": assert ids == {"other_offer"}
    assert all(row.service_id == "service_two" for row in result.d2_price_block.rows)


def test_no_patient_focus_seed_parameter_exists():
    import inspect
    assert "d2_plan_focus_seed" not in inspect.signature(resolve_d2_operations).parameters
    assert "subjects" not in inspect.signature(resolve_d2_operations).parameters
