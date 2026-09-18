from __future__ import annotations

from datetime import date

import pytest

from contracts.response_plan import UiQuickReplyCandidate
from contracts.response_plan_materialization import D2SourceUiAuthority, MaterializationOwnershipError
from core.response_plan_materialization import resolve_d2_envelope_response
from tests.test_d2_prose_realization import _AS_OF, _content_authority, _prose_request, _resolve
from tests.test_d2_single_request import _parsed_envelope, _price_request, _sources


def test_money_replaces_entire_prose_block() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    prose = _prose_request("r2", text="Это стоит 120 000 ₽, а дальше обычный текст.")
    outcome, _ = _resolve(price, prose)

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.resolved.d2_request_parts[1].status == "unavailable"
    assert "120 000 ₽, а дальше" not in outcome.rendered_text
    assert "120 000" in outcome.rendered_text  # only the verified price row survives
    assert "недостаточно информации" in outcome.rendered_text


def test_unbound_link_is_not_published() -> None:
    outcome, _ = _resolve(_prose_request(text="Подробнее [здесь](https://example.test/path)."))

    assert outcome.resolved.d2_result_status == "failed"
    assert "example.test" not in outcome.rendered_text
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_model_prose_link"


def test_non_http_uri_scheme_is_not_published() -> None:
    outcome, _ = _resolve(_prose_request(text="Откройте javascript:alert(1)."))

    assert outcome.resolved.d2_result_status == "failed"
    assert "javascript:" not in outcome.rendered_text
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_model_prose_link"


def test_empty_prose_replaces_entire_block() -> None:
    outcome, _ = _resolve(_prose_request(text="", fallback="s:anesthesia"))

    assert outcome.resolved.d2_request_parts[0].status == "recovered"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_model_prose_empty"
    assert outcome.rendered_text == "Точная цитата об анестезии."


def test_exact_same_source_fallback() -> None:
    outcome, _ = _resolve(
        _prose_request(text="Стоимость 12 000 руб.", fallback="s:preparation")
    )

    part = outcome.resolved.d2_request_parts[0]
    block = outcome.resolved.information_blocks[0]
    assert outcome.resolved.d2_result_status == "degraded"
    assert part.status == "recovered"
    assert part.failure_reason == "d2_model_prose_money"
    assert block.display_text == "Точная цитата о подготовке."
    assert block.source_section_refs == ("s:preparation",)
    assert block.publication == "fallback"
    assert "12 000" not in outcome.rendered_text


def test_missing_fallback_preserves_independent_parts() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    outcome, _ = _resolve(price, _prose_request("r2", text="Цена 999 USD."))

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.d2_request_parts[1].status == "unavailable"
    assert "999 USD" not in outcome.rendered_text


def test_no_implicit_generic_fallback() -> None:
    outcome, _ = _resolve(_prose_request(text="Цена 5 000 ₽."))

    assert outcome.resolved.information_blocks == ()
    assert "Общий утверждённый текст" not in outcome.rendered_text
    assert "Точная цитата" not in outcome.rendered_text


def test_result_status_truth_table() -> None:
    unavailable, _ = _resolve(_prose_request(text="Цена 5 000 ₽."))
    recovered, _ = _resolve(_prose_request(text="Цена 5 000 ₽.", fallback="s:anesthesia"))

    assert unavailable.resolved.d2_result_status == "failed"
    assert recovered.resolved.d2_result_status == "degraded"
    assert recovered.resolved.d2_request_parts[0].status == "recovered"


def test_integrity_errors_are_not_recovered() -> None:
    bad = _prose_request(fallback="s:anesthesia")
    bad["content_ref"] = "missing.md"
    envelope = _parsed_envelope(requests=[bad], commercial_intent="none")
    with pytest.raises(MaterializationOwnershipError):
        resolve_d2_envelope_response(
            envelope, _sources(content=(_content_authority(),)), as_of=_AS_OF
        )


def test_unavailable_primary_source_ui_is_not_transferred() -> None:
    bad = _prose_request("r1", text="Цена 5 000 ₽.")
    good = _prose_request("r2", text="Корректный второй ответ.")
    source = _sources(content=(_content_authority(),)).model_copy(
        update={
            "d2_source_ui": (
                D2SourceUiAuthority(
                    source_client_id="demo", content_ref="pain.md",
                    quick_replies=(UiQuickReplyCandidate(source_client_id="demo", reply_id="next", label="Далее"),),
                ),
            )
        }
    )
    envelope = _parsed_envelope(requests=[bad, good], commercial_intent="none")
    outcome = resolve_d2_envelope_response(envelope, source, as_of=_AS_OF)

    assert outcome.resolved.d2_result_status == "degraded"
    assert outcome.resolved.ui_plan.source_content_ref is None
    assert outcome.ui_projection.quick_replies == ()
    assert "Корректный второй ответ." in outcome.rendered_text
