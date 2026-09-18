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
from contracts.d2_session_context import D2CrossTopicSituationCarry, D2PlanFocusSeed
from contracts.response_plan_session import PersistedSituationState
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


def _envelope(
    situation: dict[str, object] | None,
    *,
    topic_id: str = "implantation",
    subject_id: str | None = None,
):
    subjects = [] if subject_id is None else [
        {"subject_id": subject_id, "relation": "self", "age_group": "adult"}
    ]
    payload = production_envelope_template(
        commercial_intent="price",
        request_understanding={
            "subjects": subjects,
            "requests": [{
                "request_id": "r1", "kind": "price", "subject_id": subject_id,
                "context": "general_information", "policy_ids": [],
                "payment_scheme": "unspecified", "payment_scheme_intent": "not_requested",
                "contact_fields": [], "content_text": None, "service_id": None,
                "topic_id": topic_id, "statement_mode": "question", "situation": situation,
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


def _cross_topic_seed(
    *,
    session_key=None,
    destination_topic_id: str = "prosthetics",
    source_topic_id: str = "implantation",
    owner_id: str | None = "owner-implant-1",
) -> D2PlanFocusSeed:
    source_session_key = session_key or _cross_topic_sources().session_key
    source = PersistedSituationState(
        session_key=source_session_key,
        topic_id=source_topic_id,
        extent="few_teeth",
        jaw="upper",
        stage="unknown",
        modifiers=(),
        set_at_turn=4,
        situation_owner_id=owner_id,
        tooth_count=3,
    )
    if owner_id is None or destination_topic_id == source_topic_id:
        carry = D2CrossTopicSituationCarry.model_construct(
            situation_owner_id="owner-implant-1",
            source_situation=source,
            destination_topic_id=destination_topic_id,
        )
    else:
        carry = D2CrossTopicSituationCarry(
            situation_owner_id=owner_id,
            source_situation=source,
            destination_topic_id=destination_topic_id,
        )
    return D2PlanFocusSeed.model_construct(
        source_session_key=source_session_key,
        source_revision=5,
        source_turn_index=4,
        action="resolve_topic",
        topic_id=destination_topic_id,
        carried_situation=None,
        cross_topic_carry=carry,
    )


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


def test_cross_topic_candidate_filters_destination_prices_without_replacing_current_situation() -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key)
    outcome = resolve_d2_envelope_response(
        _envelope({**_situation("unknown"), "continuity": "same"}, topic_id="prosthetics", subject_id="s1"),
        sources,
        as_of=date(2026, 9, 18),
        d2_plan_focus_seed=seed,
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["other_offer"]
    assert outcome.resolved.d2_price_scope_decision is None
    assert seed.cross_topic_carry is not None
    assert seed.cross_topic_carry.source_situation.topic_id == "implantation"
    assert seed.cross_topic_carry.source_situation.extent == "few_teeth"


def test_absent_cross_topic_candidate_preserves_destination_overview() -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key).model_copy(
        update={"cross_topic_carry": None}
    )
    outcome = resolve_d2_envelope_response(
        _envelope(None, topic_id="prosthetics"), sources, as_of=date(2026, 9, 18),
        d2_plan_focus_seed=seed,
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["other_offer", "generic_fixed"]
    assert outcome.resolved.d2_price_scope_decision is None


def test_current_typed_situation_keeps_precedence_over_cross_topic_candidate() -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key)
    outcome = resolve_d2_envelope_response(
        _envelope({**_situation("one_tooth"), "continuity": "same"}, topic_id="prosthetics", subject_id="s1"),
        sources,
        as_of=date(2026, 9, 18),
        d2_plan_focus_seed=seed,
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["generic_fixed"]


@pytest.mark.parametrize(
    "seed_update,situation,subject_id",
    [
        ({"source_session_key": _sources(_bundle()).session_key.model_copy(update={"sid": "other"})}, _situation("unknown"), "s1"),
        ({"topic_id": "implantation"}, _situation("unknown"), "s1"),
        ({}, _situation("unknown"), None),
        ({}, None, "s1"),
        ({}, {**_situation("unknown"), "continuity": "new"}, "s1"),
        ({}, _situation("unknown", "reset"), "s1"),
        ({"cross_topic_carry": _cross_topic_seed(destination_topic_id="implantation").cross_topic_carry}, _situation("unknown"), "s1"),
        ({"cross_topic_carry": _cross_topic_seed(owner_id=None).cross_topic_carry}, _situation("unknown"), "s1"),
        ({"cross_topic_carry": _cross_topic_seed(session_key=_sources(_bundle()).session_key.model_copy(update={"sid": "other"})).cross_topic_carry}, _situation("unknown"), "s1"),
        ({"cross_topic_carry": None}, _situation("unknown"), "s1"),
    ],
    ids=("wrong_session", "wrong_destination", "null_subject", "missing_situation", "not_same", "reset", "source_is_destination", "ownerless", "source_session_mismatch", "missing_candidate"),
)
def test_cross_topic_candidate_guards_fail_closed(
    seed_update: dict[str, object], situation: dict[str, object] | None, subject_id: str | None
) -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key).model_copy(update=seed_update)
    outcome = resolve_d2_envelope_response(
        _envelope(situation, topic_id="prosthetics", subject_id=subject_id),
        sources,
        as_of=date(2026, 9, 18),
        d2_plan_focus_seed=seed,
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["other_offer", "generic_fixed"]


def test_cross_topic_candidate_fails_closed_for_multiple_typed_price_topics() -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key)
    first = _envelope({**_situation("unknown"), "continuity": "same"}, topic_id="prosthetics", subject_id="s1")
    first_part = first.request_understanding.requests[0]
    second_part = first_part.model_copy(
        update={"request_id": "r2", "topic_id": "implantation", "subject_id": None, "situation": None}
    )
    multi_topic = first.model_copy(
        update={"request_understanding": first.request_understanding.model_copy(update={"requests": (first_part, second_part)})}
    )
    outcome = resolve_d2_envelope_response(
        multi_topic, sources, as_of=date(2026, 9, 18), d2_plan_focus_seed=seed
    )
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["other_offer", "generic_fixed"]


def test_cross_topic_selection_is_invariant_to_raw_text_mutation() -> None:
    sources = _cross_topic_sources()
    seed = _cross_topic_seed(session_key=sources.session_key)
    original = _envelope({**_situation("unknown"), "continuity": "same"}, topic_id="prosthetics", subject_id="s1")
    changed = original.model_copy(update={"patient_text": "Полностью другой неструктурированный текст."})
    first = resolve_d2_envelope_response(original, sources, as_of=date(2026, 9, 18), d2_plan_focus_seed=seed)
    second = resolve_d2_envelope_response(changed, sources, as_of=date(2026, 9, 18), d2_plan_focus_seed=seed)
    assert first.resolved.d2_price_block == second.resolved.d2_price_block
    assert seed.cross_topic_carry is not None
    assert seed.cross_topic_carry.source_situation.extent == "few_teeth"
