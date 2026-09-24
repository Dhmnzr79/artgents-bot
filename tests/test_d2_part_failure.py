from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from contracts.response_plan import UiButtonCandidate, UiQuickReplyCandidate, UiVideoCandidate
from contracts.response_plan_materialization import (
    D2PartFailureAuthority,
    D2SourceUiAuthority,
    MaterializationContractError,
    MaterializationOwnershipError,
    OfferConditionEvidence,
)
from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_d2_independent_request_parts import _envelope, _part, _sources_ab
from tests.test_d2_price_scope_selection import _situation
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


_AS_OF = date(2026, 9, 18)
_COMPLETE = "d2_no_price_candidates"
_SCOPE = "d2_no_scope_price_candidates"


def _with_failure_authorities(sources, *reasons: str):
    payload = sources.model_dump()
    payload["d2_part_failures"] = [
        D2PartFailureAuthority(
            source_client_id="demo",
            message_id=f"price-{reason}",
            reason=reason,  # type: ignore[arg-type]
            display_text=f"Утверждённый отказ: {reason}.",
        ).model_dump()
        for reason in reasons
    ]
    return type(sources).model_validate(payload)


def _sources_with_incomplete_price_and_content():
    base = _sources_ab()
    payload = base.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["active"] = False
    prepared = type(base).model_validate(payload)
    return _with_failure_authorities(prepared, _COMPLETE)


def _price_and_content(*, reverse: bool = False):
    price = _part("r1", "price", service_id="service_one", topic_id="implantation")
    content = _part(
        "r2",
        "content",
        service_id="service_two",
        topic_id="therapy",
        content_ref="therapy.md",
    )
    return _envelope([content, price] if reverse else [price, content])


@pytest.mark.parametrize("reverse", [False, True])
def test_incomplete_price_degrades_without_losing_independent_content(reverse: bool) -> None:
    outcome = resolve_d2_envelope_response(
        _price_and_content(reverse=reverse),
        _sources_with_incomplete_price_and_content(),
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "degraded"
    expected_parts = [
        ("r2", "answered", None), ("r1", "unavailable", _COMPLETE)
    ] if reverse else [
        ("r1", "unavailable", _COMPLETE), ("r2", "answered", None)
    ]
    assert [
        (part.request_id, part.status, part.failure_reason)
        for part in outcome.resolved.d2_request_parts
    ] == expected_parts
    assert outcome.resolved.d2_price_block is None
    assert outcome.resolved.finalized_commercial_ids.price_offer_ids == ()
    assert len(outcome.resolved.d2_part_failure_blocks) == 1
    assert outcome.resolved.d2_part_failure_blocks[0].request_id == "r1"
    failure_text = f"Утверждённый отказ: {_COMPLETE}."
    assert outcome.rendered_text.count(failure_text) == 1
    assert outcome.rendered_text.count("Материал терапии.") == 1
    assert (outcome.rendered_text.index(failure_text) < outcome.rendered_text.index("Материал терапии.")) is not reverse
    assert "120 000" not in outcome.rendered_text


def test_known_scope_failure_keeps_other_direction_content_without_substitution() -> None:
    price = {
        **_part("r1", "price", service_id=None, topic_id="implantation"),
        "situation": _situation("few_teeth"),
    }
    content = _part(
        "r2", "content", service_id="service_two", topic_id="therapy", content_ref="therapy.md"
    )
    outcome = resolve_d2_envelope_response(
        _envelope([price, content]),
        _with_failure_authorities(_sources_ab(), _SCOPE),
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.resolved.response_scope == "mixed"
    assert outcome.resolved.d2_request_parts[0].failure_reason == _SCOPE
    assert outcome.resolved.d2_price_scope_decision is None
    assert outcome.resolved.ui_plan.quick_replies == ()
    assert "Материал терапии." in outcome.rendered_text
    assert "Exact package" not in outcome.rendered_text


def test_single_unavailable_price_is_failed_with_empty_ui() -> None:
    sources = _with_failure_authorities(
        _sources(_bundle()), _COMPLETE
    )
    payload = sources.model_dump()
    for offer in payload["material_authority"]["bundle"]["offers"]:
        offer["active"] = False
    sources = type(sources).model_validate(payload)
    outcome = resolve_d2_envelope_response(
        _envelope([_part("r1", "price", service_id="service_one", topic_id="implantation")]),
        sources,
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_price_block is None
    assert outcome.resolved.ui_plan.quick_replies == ()
    assert outcome.resolved.ui_plan.buttons == ()
    assert outcome.ui_projection.video is None
    assert outcome.rendered_text == f"Утверждённый отказ: {_COMPLETE}."


def test_no_public_price_remains_complete_answered() -> None:
    payload = _bundle(no_public_active=True).model_dump()
    for offer in payload["offers"]:
        offer["active"] = offer["offer_id"] == "generic_no_public"
    outcome = resolve_d2_envelope_response(
        _envelope([_part("r1", "price", service_id="service_one", topic_id="implantation")]),
        _sources(_bundle().__class__.model_validate(payload)),
        as_of=_AS_OF,
    )

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[0].status == "answered"
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.d2_price_block.rows[0].mode == "no_public_price"


def test_degraded_price_request_suppresses_secondary_but_keeps_authorized_cta() -> None:
    base = _sources_with_incomplete_price_and_content()
    payload = base.model_dump()
    payload["d2_source_ui"] = [
        D2SourceUiAuthority(
            source_client_id="demo",
            content_ref="therapy.md",
            quick_replies=(
                UiQuickReplyCandidate(
                    source_client_id="demo", reply_id="therapy-follow", label="О терапии"
                ),
            ),
            video=UiVideoCandidate(source_client_id="demo", video_id="therapy-video"),
            cta=UiButtonCandidate(
                source_client_id="demo", button_id="therapy-cta", label="Записаться", action_kind="cta"
            ),
        ).model_dump()
    ]
    sources = type(base).model_validate(payload)
    outcome = resolve_d2_envelope_response(_price_and_content(), sources, as_of=_AS_OF)

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert [button.button_id for button in outcome.ui_projection.buttons] == ["therapy-cta"]
    assert outcome.resolved.finalized_commercial_ids.price_offer_ids == ()


def test_missing_or_foreign_failure_authority_is_fatal_and_late_foreign_content_wins() -> None:
    with pytest.raises(MaterializationContractError, match="d2_part_failure_authority_missing"):
        resolve_d2_envelope_response(
            _price_and_content(), _sources_with_incomplete_price_and_content().model_copy(
                update={"d2_part_failures": ()}
            ), as_of=_AS_OF
        )

    foreign_authority = D2PartFailureAuthority(
        source_client_id="other",
        message_id="other-price-failure",
        reason=_COMPLETE,
        display_text="Чужой текст.",
    )
    with pytest.raises(MaterializationContractError, match="d2_part_failure_authority_missing"):
        resolve_d2_envelope_response(
            _price_and_content(), _sources_with_incomplete_price_and_content().model_copy(
                update={"d2_part_failures": (foreign_authority,)}
            ), as_of=_AS_OF
        )

    foreign_content = _part(
        "r2", "content", service_id="service_two", topic_id="therapy", content_ref="missing.md"
    )
    # An optional wrong source ref drops attribution, not the live answer.
    outcome = resolve_d2_envelope_response(
        _envelope([_part("r1", "price", service_id="service_one", topic_id="implantation"), foreign_content]),
        _sources_with_incomplete_price_and_content(),
        as_of=_AS_OF,
    )
    assert outcome.resolved.d2_request_parts[1].status == "answered"
    assert outcome.resolved.d2_request_parts[1].content_ref is None
    assert foreign_content["content_text"] in outcome.rendered_text


def test_unexpected_price_error_is_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.response_plan_materialization as materialization

    monkeypatch.setattr(
        materialization,
        "_d2_price_block",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("unexpected price failure")),
    )
    with pytest.raises(RuntimeError, match="unexpected price failure"):
        resolve_d2_envelope_response(
            _price_and_content(), _sources_with_incomplete_price_and_content(), as_of=_AS_OF
        )


def test_corrupted_failure_linkage_and_aggregate_are_rejected_and_frozen() -> None:
    sources = _sources_with_incomplete_price_and_content()
    outcome = resolve_d2_envelope_response(_price_and_content(), sources, as_of=_AS_OF)
    frozen_text, frozen_ui = outcome.rendered_text, outcome.ui_projection
    payload = outcome.resolved.model_dump()
    payload["d2_part_failure_blocks"] = []
    with pytest.raises(ValidationError, match="d2_part_failure_block_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_part_failure_blocks"] = (
        *payload["d2_part_failure_blocks"],
        payload["d2_part_failure_blocks"][0].copy(),
    )
    with pytest.raises(ValidationError, match="d2_part_failure_block_duplicate"):
        outcome.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_request_parts"][0].update(
        {"status": "answered", "failure_reason": None}
    )
    payload["d2_part_failure_blocks"] = []
    payload["d2_result_status"] = "complete"
    with pytest.raises(ValidationError, match="d2_request_part_price_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    successful = resolve_d2_envelope_response(
        _envelope([_part("r1", "price", service_id="service_one", topic_id="implantation")]),
        _sources(_bundle()),
        as_of=_AS_OF,
    )
    payload = successful.resolved.model_dump()
    payload["d2_request_parts"][0].update(
        {"status": "unavailable", "failure_reason": _COMPLETE}
    )
    payload["d2_part_failure_blocks"] = [
        {
            "request_id": "r1",
            "source_client_id": "demo",
            "message_id": "price-incomplete",
            "reason": _COMPLETE,
            "display_text": "Утверждённый отказ.",
        }
    ]
    payload["d2_result_status"] = "failed"
    with pytest.raises(ValidationError, match="d2_request_part_price_linkage_invalid"):
        successful.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_result_status"] = "complete"
    with pytest.raises(ValidationError, match="d2_part_result_status_mismatch"):
        outcome.resolved.__class__.model_validate(payload)

    sources.material_authority.bundle.offers.clear()
    assert render_response_text(outcome.resolved) == frozen_text
    assert project_response_ui(outcome.resolved) == frozen_ui


def test_unavailable_d2_path_bypasses_legacy_semantic_composer_and_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import core.response_plan_materialization as materialization
    import core.response_plan_composer_executor as composer_executor
    import core.sales_one_plus_live_backend as sales_live_backend
    import core.target_composer_executor as target_composer_executor
    import core.target_runtime_llm_backends as target_live_backends
    import socket

    def forbidden(*_args, **_kwargs):
        raise AssertionError("forbidden outside direct D2 path")

    monkeypatch.setattr(
        materialization,
        "resolve_materialized_response",
        forbidden,
    )
    monkeypatch.setattr(materialization, "materialize_pre_composer_payload", forbidden)
    monkeypatch.setattr(composer_executor, "execute_composer_decision", forbidden)
    monkeypatch.setattr(target_composer_executor, "execute_target_composer", forbidden)
    monkeypatch.setattr(sales_live_backend, "chat_completions_create", forbidden)
    monkeypatch.setattr(target_live_backends, "chat_completions_create", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)

    outcome = materialization.resolve_d2_envelope_response(
        _price_and_content(), _sources_with_incomplete_price_and_content(), as_of=_AS_OF
    )
    assert outcome.resolved.d2_result_status == "degraded"
