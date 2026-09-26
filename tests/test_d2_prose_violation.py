from __future__ import annotations

from datetime import date

import pytest

from contracts.response_plan import UiQuickReplyCandidate
from contracts.response_plan_materialization import D2SourceUiAuthority
from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError
from core.response_plan_materialization import resolve_d2_envelope_response
from tests.test_d2_prose_realization import _AS_OF, _content_authority, _prose_request, _resolve
from tests.test_d2_single_request import _parsed_envelope, _price_request, _sources


def test_money_does_not_replace_prose_or_verified_price() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    prose = _prose_request("r2", text="Это стоит 120 000 ₽, а дальше обычный текст.")
    outcome, _ = _resolve(price, prose)

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[1].status == "answered"
    assert outcome.resolved.d2_request_parts[1].failure_reason is None
    assert outcome.resolved.d2_price_block is not None
    assert "120 000 ₽, а дальше обычный текст." in outcome.rendered_text


def test_unbound_link_is_published_as_prose_not_as_source_ui() -> None:
    outcome, _ = _resolve(_prose_request(text="Подробнее [здесь](https://example.test/path)."))

    assert outcome.resolved.d2_result_status == "complete"
    assert "[здесь](https://example.test/path)" in outcome.rendered_text
    assert outcome.resolved.d2_request_parts[0].failure_reason is None


def test_non_http_uri_scheme_does_not_block_prose() -> None:
    outcome, _ = _resolve(_prose_request(text="Откройте javascript:alert(1)."))

    assert outcome.resolved.d2_result_status == "complete"
    assert "javascript:alert(1)" in outcome.rendered_text
    assert outcome.resolved.d2_request_parts[0].failure_reason is None


def test_empty_model_prose_remains_invalid_at_parser() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError, match="model_prose_text_required"):
        _resolve(_prose_request(text="", fallback="s:anesthesia"))


def test_valid_fallback_does_not_replace_nonempty_model_prose() -> None:
    outcome, _ = _resolve(
        _prose_request(text="Стоимость 12 000 руб.", fallback="s:preparation")
    )

    part = outcome.resolved.d2_request_parts[0]
    block = outcome.resolved.information_blocks[0]
    assert outcome.resolved.d2_result_status == "complete"
    assert part.status == "answered" and part.failure_reason is None
    assert block.display_text == "Стоимость 12 000 руб."
    assert block.source_section_refs == ("s:anesthesia", "s:preparation")
    assert block.publication == "model_prose"


def test_missing_fallback_preserves_independent_parts() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    outcome, _ = _resolve(price, _prose_request("r2", text="Цена 999 USD."))

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_price_block is not None
    assert outcome.resolved.d2_request_parts[1].status == "answered"
    assert "999 USD" in outcome.rendered_text


def test_no_implicit_generic_fallback() -> None:
    outcome, _ = _resolve(_prose_request(text="Цена 5 000 ₽."))

    assert outcome.resolved.information_blocks[0].display_text == "Цена 5 000 ₽."
    assert outcome.resolved.information_blocks[0].publication == "model_prose"
    assert "Общий утверждённый текст" not in outcome.rendered_text
    assert "Точная цитата" not in outcome.rendered_text


def test_result_status_is_answered_with_or_without_optional_fallback() -> None:
    without, _ = _resolve(_prose_request(text="Цена 5 000 ₽."))
    with_fallback, _ = _resolve(_prose_request(text="Цена 5 000 ₽.", fallback="s:anesthesia"))

    assert without.resolved.d2_result_status == "complete"
    assert with_fallback.resolved.d2_result_status == "complete"
    assert with_fallback.resolved.d2_request_parts[0].status == "answered"


def test_missing_source_does_not_authorize_citation_or_hide_prose() -> None:
    bad = _prose_request(fallback="s:anesthesia")
    bad["content_ref"] = "missing.md"
    envelope = _parsed_envelope(requests=[bad], commercial_intent="none")
    outcome = resolve_d2_envelope_response(
        envelope, _sources(content=(_content_authority(),)), as_of=_AS_OF
    )
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[0].status == "answered"
    assert outcome.resolved.d2_request_parts[0].content_ref is None
    assert outcome.resolved.information_blocks[0].content_ref is None
    assert outcome.resolved.ui_plan.source_content_ref is None
    assert outcome.rendered_text == bad["content_text"]


def test_unverified_primary_source_ui_is_not_transferred() -> None:
    bad = _prose_request("r1", text="Цена 5 000 ₽.")
    bad["content_ref"] = "missing.md"
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

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.ui_plan.source_content_ref is None
    assert outcome.ui_projection.quick_replies == ()
    assert "Цена 5 000 ₽." in outcome.rendered_text
    assert "Корректный второй ответ." in outcome.rendered_text
