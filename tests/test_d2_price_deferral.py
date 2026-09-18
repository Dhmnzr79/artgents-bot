from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from contracts.response_plan import D2_PRICE_DEFERRAL_TEXT
from contracts.response_plan_materialization import (
    D2PartFailureAuthority,
    MaterializationOwnershipError,
)
from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_d2_independent_request_parts import _envelope, _part, _sources_ab


_AS_OF = date(2026, 9, 18)


def _price(request_id: str, service_id: str) -> dict[str, object]:
    return _part(request_id, "price", service_id=service_id, topic_id=None)


@pytest.mark.parametrize(
    ("requests", "selected_service_id", "deferred_request_id"),
    [
        ([_price("r1", "service_one"), _price("r2", "service_two")], "service_one", "r2"),
        ([_price("r2", "service_two"), _price("r1", "service_one")], "service_two", "r1"),
    ],
)
def test_first_price_request_in_request_order_is_the_only_materialized_price(
    requests, selected_service_id: str, deferred_request_id: str
) -> None:
    outcome = resolve_d2_envelope_response(_envelope(requests), _sources_ab(), as_of=_AS_OF)

    assert outcome.resolved.d2_result_status == "degraded"
    assert [part.status for part in outcome.resolved.d2_request_parts] == ["answered", "deferred"]
    assert {row.service_id for row in outcome.resolved.d2_price_block.rows} == {selected_service_id}
    assert [block.request_id for block in outcome.resolved.d2_part_deferred_blocks] == [deferred_request_id]
    assert outcome.rendered_text.count(D2_PRICE_DEFERRAL_TEXT) == 1
    assert outcome.resolved.session_delta.shown_price_offer_ids == tuple(
        row.offer_id for row in outcome.resolved.d2_price_block.rows
    )
    assert outcome.resolved.session_delta.terminal_state == "none"
    assert outcome.resolved.session_delta.clarify_pending is False


def test_three_price_requests_freeze_one_price_and_two_linked_deferrals() -> None:
    outcome = resolve_d2_envelope_response(
        _envelope([
            _price("r1", "service_one"),
            _price("r2", "service_two"),
            _price("r3", "service_one"),
        ]),
        _sources_ab(),
        as_of=_AS_OF,
    )

    assert len(outcome.resolved.d2_price_block.rows) == 3
    assert {row.service_id for row in outcome.resolved.d2_price_block.rows} == {"service_one"}
    assert [(part.request_id, part.status) for part in outcome.resolved.d2_request_parts] == [
        ("r1", "answered"), ("r2", "deferred"), ("r3", "deferred"),
    ]
    assert [block.request_id for block in outcome.resolved.d2_part_deferred_blocks] == ["r2", "r3"]
    assert outcome.rendered_text.count(D2_PRICE_DEFERRAL_TEXT) == 2


def test_price_content_price_preserves_independent_content_and_request_order() -> None:
    outcome = resolve_d2_envelope_response(
        _envelope([
            _price("r1", "service_one"),
            _part("r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"),
            _price("r3", "service_two"),
        ]),
        _sources_ab(),
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.rendered_text.count("Материал терапии.") == 1
    assert outcome.rendered_text.index("Exact package") < outcome.rendered_text.index("Материал терапии.")
    assert outcome.rendered_text.index("Материал терапии.") < outcome.rendered_text.index(D2_PRICE_DEFERRAL_TEXT)
    assert [row.service_id for row in outcome.resolved.d2_price_block.rows] == ["service_one"] * 3


def test_unavailable_first_price_never_falls_through_to_deferred_second_price() -> None:
    base = _sources_ab()
    payload = base.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["active"] = False
    payload["d2_part_failures"] = [
        D2PartFailureAuthority(
            source_client_id="demo",
            message_id="no-price",
            reason="d2_no_price_candidates",
            display_text="Нет опубликованной цены для первого вопроса.",
        ).model_dump()
    ]
    sources = type(base).model_validate(payload)

    outcome = resolve_d2_envelope_response(
        _envelope([_price("r1", "service_one"), _price("r2", "service_two")]),
        sources,
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.resolved.d2_price_block is None
    assert [(part.request_id, part.status) for part in outcome.resolved.d2_request_parts] == [
        ("r1", "unavailable"), ("r2", "deferred"),
    ]
    assert outcome.resolved.finalized_commercial_ids.price_offer_ids == ()
    assert "Нет опубликованной цены для первого вопроса." in outcome.rendered_text
    assert D2_PRICE_DEFERRAL_TEXT in outcome.rendered_text
    assert "Exact package other_offer" not in outcome.rendered_text


def test_deferred_price_is_frozen_linked_and_does_not_rerender_or_change_ui() -> None:
    sources = _sources_ab()
    outcome = resolve_d2_envelope_response(
        _envelope([_price("r1", "service_one"), _price("r2", "service_two")]),
        sources,
        as_of=_AS_OF,
    )
    frozen_text, frozen_ui = outcome.rendered_text, outcome.ui_projection

    assert "Exact package other_offer" not in frozen_text
    assert frozen_text.count(D2_PRICE_DEFERRAL_TEXT) == 1
    assert render_response_text(outcome.resolved) == frozen_text
    assert project_response_ui(outcome.resolved) == frozen_ui
    sources.material_authority.bundle.offers.clear()
    assert render_response_text(outcome.resolved) == frozen_text
    assert project_response_ui(outcome.resolved) == frozen_ui

    payload = outcome.resolved.model_dump()
    payload["d2_part_deferred_blocks"] = []
    with pytest.raises(ValidationError, match="d2_part_deferred_block_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_result_status"] = "complete"
    with pytest.raises(ValidationError, match="d2_part_result_status_mismatch"):
        outcome.resolved.__class__.model_validate(payload)


@pytest.mark.parametrize(
    "deferred",
    [
        _price("r2", "foreign_service"),
        _part("r2", "price", service_id=None, topic_id="foreign_topic"),
    ],
)
def test_deferred_price_foreign_tenant_reference_fails_closed(deferred) -> None:
    with pytest.raises(MaterializationOwnershipError, match="materialization_foreign_material"):
        resolve_d2_envelope_response(
            _envelope([_price("r1", "service_one"), deferred]),
            _sources_ab(),
            as_of=_AS_OF,
        )
