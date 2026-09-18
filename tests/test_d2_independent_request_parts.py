from __future__ import annotations

import json
from datetime import date

import pytest
from pydantic import ValidationError

from contracts.response_plan import UiButtonCandidate, UiQuickReplyCandidate, UiVideoCandidate
from contracts.response_plan_materialization import (
    D2AuthoredContentAuthority,
    D2DirectionAuthority,
    D2SourceUiAuthority,
    MaterializationContractError,
    MaterializationOwnershipError,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import parse_production_envelope_json, production_envelope_template
from core.response_plan_materialization import resolve_d2_envelope_response
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


def _envelope(requests):
    payload = production_envelope_template(
        commercial_intent="price", request_understanding={"subjects": [], "requests": requests},
        primary_price_request_id="r1" if any(item["kind"] == "price" for item in requests) else None,
    )
    return parse_production_envelope_json(
        json.dumps(payload), active_service_catalog=ActiveServiceCatalogSnapshot(canonical_json="{}"),
        service_reference_catalog=ServiceReferenceCatalogSnapshot(canonical_json="{}"),
        commercial_fact_catalog=CommercialFactCatalogSnapshot(canonical_json="{}"),
    )


def _part(request_id, kind, *, service_id, topic_id, content_ref=None):
    return {"request_id": request_id, "kind": kind, "subject_id": None, "context": "general_information", "policy_ids": [], "payment_scheme": "unspecified", "payment_scheme_intent": "not_requested", "contact_fields": [], "content_text": "approved meaning" if kind == "content" else None, "content_ref": content_ref, "service_id": service_id, "topic_id": topic_id, "statement_mode": "question"}


def _sources_ab(base=None):
    base = base if base is not None else _sources(_bundle())
    payload = base.model_dump()
    payload["d2_authored_content"] = (*payload["d2_authored_content"], D2AuthoredContentAuthority(source_client_id="demo", content_ref="therapy.md", display_text="Материал терапии.", allowed_service_ids=("service_two",)).model_dump())
    payload["d2_directions"] = (*payload["d2_directions"], D2DirectionAuthority(source_client_id="demo", topic_id="therapy", service_ids=("service_two",)).model_dump())
    return type(base).model_validate(payload)


def test_price_and_other_service_content_remain_independent_and_mixed() -> None:
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id=None, topic_id="implantation"),
        _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
    ]), _sources_ab(), as_of=date(2026, 9, 18))
    assert outcome.resolved.response_scope == "mixed"
    assert outcome.resolved.session_delta.active_service_id is None
    assert [(item.request_id, item.scope) for item in outcome.resolved.d2_request_parts] == [("r1", "topic"), ("r2", "service")]
    assert outcome.rendered_text.index("Exact package") < outcome.rendered_text.index("Материал терапии.")


def test_request_order_controls_frozen_render_order() -> None:
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
    ]), _sources_ab(), as_of=date(2026, 9, 18))
    assert outcome.rendered_text.index("Материал терапии.") < outcome.rendered_text.index("Exact package")


def test_two_content_services_are_mixed_and_render_each_source_once() -> None:
    base = _sources_ab()
    source_payload = base.model_dump()
    source_payload["d2_authored_content"] = (*source_payload["d2_authored_content"], D2AuthoredContentAuthority(source_client_id="demo", content_ref="pain-two.md", display_text="Второй материал имплантации.", allowed_service_ids=("service_one",)).model_dump())
    sources = type(base).model_validate(source_payload)
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
        _part("r2", "content", service_id="service_one", topic_id="implantation", content_ref="pain-two.md"),
    ]), sources, as_of=date(2026, 9, 18))
    assert outcome.resolved.response_scope == "mixed"
    assert outcome.resolved.session_delta.active_service_id is None
    assert outcome.rendered_text.count("Материал терапии.") == 1
    assert outcome.rendered_text.count("Второй материал имплантации.") == 1
    assert outcome.rendered_text.index("Материал терапии.") < outcome.rendered_text.index("Второй материал")


@pytest.mark.parametrize(
    ("request_refs", "expected_first_reply", "expected_first_video"),
    [
        (("therapy.md", "pain-two.md"), "therapy_follow", "therapy_video"),
        (("pain-two.md", "therapy.md"), "implant_follow", "implant_video"),
    ],
)
def test_two_content_sources_use_only_first_source_secondary_ui(
    request_refs: tuple[str, str], expected_first_reply: str, expected_first_video: str,
) -> None:
    base = _sources_ab()
    payload = base.model_dump()
    payload["d2_authored_content"] = [
        *payload["d2_authored_content"],
        D2AuthoredContentAuthority(
            source_client_id="demo", content_ref="pain-two.md",
            display_text="Материал имплантации.", allowed_service_ids=("service_one",),
        ).model_dump(),
    ]
    payload["d2_source_ui"] = [
        D2SourceUiAuthority(
            source_client_id="demo", content_ref=ref,
            quick_replies=(UiQuickReplyCandidate(source_client_id="demo", reply_id=reply, label=label),),
            video=UiVideoCandidate(source_client_id="demo", video_id=video),
        ).model_dump()
        for ref, reply, label, video in (
            ("therapy.md", "therapy_follow", "О терапии", "therapy_video"),
            ("pain-two.md", "implant_follow", "Об имплантации", "implant_video"),
        )
    ]
    sources = type(base).model_validate(payload)
    parts_by_ref = {
        "therapy.md": _part("r1", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
        "pain-two.md": _part("r2", "content", service_id="service_one", topic_id="implantation", content_ref="pain-two.md"),
    }
    outcome = resolve_d2_envelope_response(
        _envelope([parts_by_ref[ref] for ref in request_refs]), sources,
        as_of=date(2026, 9, 18),
    )
    texts_by_ref = {"therapy.md": "Материал терапии.", "pain-two.md": "Материал имплантации."}
    assert [part.content_ref for part in outcome.resolved.d2_request_parts] == list(request_refs)
    assert outcome.rendered_text.index(texts_by_ref[request_refs[0]]) < outcome.rendered_text.index(texts_by_ref[request_refs[1]])
    assert outcome.rendered_text.count("Материал терапии.") == 1
    assert outcome.rendered_text.count("Материал имплантации.") == 1
    assert outcome.resolved.ui_plan.source_content_ref == request_refs[0]
    assert [reply.reply_id for reply in outcome.ui_projection.quick_replies] == [expected_first_reply]
    assert outcome.ui_projection.video is not None
    assert outcome.ui_projection.video.video_id == expected_first_video


def test_same_confirmed_service_keeps_unambiguous_focus_despite_missing_topic() -> None:
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
        _part("r2", "content", service_id="service_one", topic_id=None, content_ref="pain.md"),
    ]), _sources_ab(), as_of=date(2026, 9, 18))
    assert outcome.resolved.response_scope == "service"
    assert outcome.resolved.session_delta.active_service_id == "service_one"


def test_clinic_wide_content_is_independent_beside_price() -> None:
    base = _sources_ab()
    payload = base.model_dump()
    payload["d2_authored_content"] = (*payload["d2_authored_content"], D2AuthoredContentAuthority(source_client_id="demo", content_ref="warranty.md", display_text="Общая гарантия.").model_dump())
    sources = type(base).model_validate(payload)
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
        _part("r2", "content", service_id=None, topic_id=None, content_ref="warranty.md"),
    ]), sources, as_of=date(2026, 9, 18))
    assert outcome.resolved.response_scope == "mixed"
    assert "Общая гарантия." in outcome.rendered_text


def test_foreign_content_source_fails_closed_without_neighbor_substitution() -> None:
    with pytest.raises(MaterializationOwnershipError):
        resolve_d2_envelope_response(_envelope([
            _part("r1", "price", service_id="service_one", topic_id="implantation"),
            _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="missing.md"),
        ]), _sources_ab(), as_of=date(2026, 9, 18))


def test_direct_d2_path_does_not_call_legacy_materializer(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.response_plan_materialization as materialization
    monkeypatch.setattr(materialization, "resolve_materialized_response", lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("legacy")))
    outcome = materialization.resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
        _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
    ]), _sources_ab(), as_of=date(2026, 9, 18))
    assert outcome.resolved.d2_price_block is not None


def test_frozen_mixed_plan_does_not_reread_mutated_snapshot() -> None:
    sources = _sources_ab()
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
        _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
    ]), sources, as_of=date(2026, 9, 18))
    rendered, projected = outcome.rendered_text, outcome.ui_projection
    sources.material_authority.bundle.offers.clear()
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui
    assert render_response_text(outcome.resolved) == rendered
    assert project_response_ui(outcome.resolved) == projected


def test_corrupted_frozen_content_linkage_is_rejected() -> None:
    outcome = resolve_d2_envelope_response(_envelope([
        _part("r1", "price", service_id="service_one", topic_id="implantation"),
        _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
    ]), _sources_ab(), as_of=date(2026, 9, 18))
    payload = outcome.resolved.model_dump()
    payload["d2_request_parts"][1]["content_ref"] = "other.md"
    with pytest.raises(ValidationError, match="d2_request_part_content_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)


def test_c4_strict_scope_remains_owned_by_price_part_with_other_content() -> None:
    from tests.test_d2_price_scope_selection import _sources_with_scope_metadata, _situation

    price = {**_part("r1", "price", service_id=None, topic_id="implantation"), "situation": _situation("few_teeth")}
    content = _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md")
    outcome = resolve_d2_envelope_response(
        _envelope([price, content]), _sources_ab(_sources_with_scope_metadata()), as_of=date(2026, 9, 18)
    )
    assert outcome.resolved.d2_price_scope_decision.applied_extent == "few_teeth"
    assert [row.offer_id for row in outcome.resolved.d2_price_block.rows] == ["option_a_from"]
    assert [(part.request_id, part.topic_id, part.content_ref) for part in outcome.resolved.d2_request_parts] == [
        ("r1", "implantation", None), ("r2", "therapy", "therapy.md")
    ]
    assert "Материал терапии." in outcome.rendered_text
    assert "Exact package option_a_from" in outcome.rendered_text
    assert "Exact package generic_fixed" not in outcome.rendered_text


def test_other_direction_content_cannot_supply_missing_known_scope_price() -> None:
    from tests.test_d2_price_scope_selection import _situation

    price = {**_part("r1", "price", service_id=None, topic_id="implantation"), "situation": _situation("few_teeth")}
    content = _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md")
    with pytest.raises(MaterializationContractError, match="d2_no_scope_price_candidates"):
        resolve_d2_envelope_response(
            _envelope([price, content]), _sources_ab(), as_of=date(2026, 9, 18)
        )


def test_other_direction_situation_does_not_filter_price_part() -> None:
    from tests.test_d2_price_scope_selection import _sources_with_scope_metadata, _situation

    content = {
        **_part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
        "situation": _situation("few_teeth"),
    }
    outcome = resolve_d2_envelope_response(
        _envelope([_part("r1", "price", service_id=None, topic_id="implantation"), content]),
        _sources_ab(_sources_with_scope_metadata()), as_of=date(2026, 9, 18),
    )
    assert outcome.resolved.d2_treatment_situation.source_request_id == "r2"
    assert outcome.resolved.d2_price_scope_decision.applied_extent is None
    assert "generic_fixed" in [row.offer_id for row in outcome.resolved.d2_price_block.rows]
    assert "Материал терапии." in outcome.rendered_text


def test_price_suppresses_other_source_secondary_ui_but_keeps_volume_choices_and_cta() -> None:
    from tests.test_d2_price_scope_selection import _sources_with_scope_metadata

    base = _sources_ab(_sources_with_scope_metadata())
    payload = base.model_dump()
    payload["d2_source_ui"] = [
        D2SourceUiAuthority(
            source_client_id="demo",
            content_ref="therapy.md",
            quick_replies=(UiQuickReplyCandidate(source_client_id="demo", reply_id="therapy_follow", label="О терапии"),),
            video=UiVideoCandidate(source_client_id="demo", video_id="therapy_video"),
            cta=UiButtonCandidate(source_client_id="demo", button_id="therapy_cta", label="Записаться", action_kind="cta"),
        ).model_dump()
    ]
    sources = type(base).model_validate(payload)
    outcome = resolve_d2_envelope_response(
        _envelope([
            _part("r1", "price", service_id=None, topic_id="implantation"),
            _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
        ]), sources, as_of=date(2026, 9, 18)
    )
    decision = outcome.resolved.d2_price_scope_decision
    assert decision is not None
    assert [choice.extent for choice in decision.volume_choices] == ["one_tooth", "few_teeth", "full_arch", "unknown"]
    assert [reply.reply_id for reply in outcome.ui_projection.quick_replies] == [
        choice.candidate.reply_id for choice in decision.volume_choices
    ]
    assert "therapy_follow" not in [reply.reply_id for reply in outcome.ui_projection.quick_replies]
    assert outcome.ui_projection.video is None
    assert [button.button_id for button in outcome.ui_projection.buttons] == ["therapy_cta"]
    from core.response_text_renderer import render_response_text
    from core.response_ui_projection import project_response_ui
    frozen_text, frozen_ui = outcome.rendered_text, outcome.ui_projection
    sources.material_authority.bundle.offers.clear()
    assert render_response_text(outcome.resolved) == frozen_text
    assert project_response_ui(outcome.resolved) == frozen_ui
