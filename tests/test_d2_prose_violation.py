from __future__ import annotations

from datetime import date

import pytest

from contracts.response_plan import UiQuickReplyCandidate
from contracts.response_plan_materialization import D2SourceUiAuthority
from core.response_plan_materialization import resolve_d2_envelope_response
from tests.test_d2_prose_realization import _AS_OF, _content_authority, _prose_request, _resolve
from tests.test_d2_single_request import _parsed_envelope, _price_request, _sources


def test_money_in_base_answer_does_not_hide_prose_or_verified_price() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    prose = _prose_request("r2", text="Это стоит 120 000 ₽, а дальше обычный текст.")
    outcome, _ = _resolve(price, prose)

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[1].status == "answered"
    assert "120 000 ₽, а дальше" in outcome.rendered_text
    assert "Exact package" in outcome.rendered_text


def test_link_in_base_answer_is_published() -> None:
    outcome, _ = _resolve(_prose_request(text="Подробнее [здесь](https://example.test/path)."))

    assert outcome.resolved.d2_result_status == "complete"
    assert "example.test" in outcome.rendered_text
    assert outcome.resolved.d2_request_parts[0].status == "answered"


def test_uri_pattern_does_not_drop_base_answer() -> None:
    outcome, _ = _resolve(_prose_request(text="Откройте javascript:alert(1)."))

    assert outcome.resolved.d2_result_status == "complete"
    assert "javascript:" in outcome.rendered_text


def test_empty_content_cannot_publish_verbatim_section() -> None:
    request = _prose_request(text="")
    request["content_realization"] = "authored"
    outcome, _ = _resolve(request)

    assert outcome.resolved.d2_request_parts[0].status == "unavailable"
    assert outcome.resolved.d2_request_parts[0].failure_reason == "d2_model_prose_empty"
    assert "Точная цитата" not in outcome.rendered_text


def test_selected_section_publishes_live_text_with_number() -> None:
    outcome, _ = _resolve(
        _prose_request(text="Стоимость 12 000 руб.", fallback="s:preparation")
    )

    part = outcome.resolved.d2_request_parts[0]
    assert outcome.resolved.d2_result_status == "complete"
    assert part.status == "answered"
    assert outcome.resolved.information_blocks[0].display_text == "Стоимость 12 000 руб."
    assert "Точная цитата" not in outcome.rendered_text
    assert "12 000" in outcome.rendered_text


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
    assert "Общий утверждённый текст" not in outcome.rendered_text
    assert "Точная цитата" not in outcome.rendered_text


def test_result_status_truth_table() -> None:
    unavailable, _ = _resolve(_prose_request(text="Цена 5 000 ₽."))
    invalid_with_fallback, _ = _resolve(_prose_request(text="Цена 5 000 ₽.", fallback="s:anesthesia"))

    assert unavailable.resolved.d2_result_status == "complete"
    assert invalid_with_fallback.resolved.d2_result_status == "complete"
    assert invalid_with_fallback.resolved.d2_request_parts[0].status == "answered"


@pytest.mark.parametrize(
    ("source_ref", "section_ref"),
    [("missing.md", "s:anesthesia"), ("pain.md", "s:not-in-document")],
)
def test_wrong_optional_source_keeps_live_answer_without_false_attribution(
    source_ref: str, section_ref: str,
) -> None:
    bad = _prose_request(fallback=section_ref)
    bad["content_ref"] = source_ref
    bad["content_section_refs"] = [section_ref]
    envelope = _parsed_envelope(requests=[bad], commercial_intent="none")
    outcome = resolve_d2_envelope_response(
        envelope, _sources(content=(_content_authority(),)), as_of=_AS_OF
    )
    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.d2_request_parts[0].status == "answered"
    assert outcome.resolved.d2_request_parts[0].content_ref is None
    assert outcome.resolved.information_blocks[0].content_ref is None
    assert "Процедуру проводят с местным обезболиванием" in outcome.rendered_text
    assert outcome.resolved.ui_plan.source_content_ref is None


def test_primary_source_ui_remains_linked_when_prose_contains_a_number() -> None:
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

    assert outcome.resolved.d2_result_status == "complete"
    assert outcome.resolved.ui_plan.source_content_ref == "pain.md"
    # Multipart answers intentionally suppress source quick replies.
    assert outcome.ui_projection.quick_replies == ()
    assert "Корректный второй ответ." in outcome.rendered_text
