from __future__ import annotations

from datetime import date

import pytest

from contracts.response_plan import UiButtonCandidate, UiQuickReplyCandidate, UiVideoCandidate
from contracts.response_plan_materialization import (
    D2AuthoredContentAuthority,
    D2SourceUiAuthority,
    ResponsePlanMaterializationSources,
)
from core.response_plan_materialization import resolve_d2_operations
from tests.test_d2_single_request import (
    _content_request,
    _parsed_envelope,
    _price_request,
    _sources,
)


MODEL_PROSE = "Смысловой текст модели не является источником ответа."


def _content_sources(*, shown: tuple[str, ...] = ()) -> ResponsePlanMaterializationSources:
    base = _sources(
        content=(
            D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="pain.md",
                display_text="Одобренный текст о боли.",
                allowed_service_ids=("service_one",),
            ),
            D2AuthoredContentAuthority(
                source_client_id="demo",
                content_ref="warranty.md",
                display_text="Одобренный текст о гарантии.",
                allowed_service_ids=("service_one",),
            ),
        )
    )
    payload = base.model_dump()
    payload.update(
        {
            "shown_d2_secondary_ref_ids": shown,
            "d2_source_ui": [
                D2SourceUiAuthority(
                    source_client_id="demo",
                    content_ref="pain.md",
                    quick_replies=(
                        UiQuickReplyCandidate(
                            source_client_id="demo", reply_id="pain_follow", label="О боли подробнее"
                        ),
                        UiQuickReplyCandidate(
                            source_client_id="demo", reply_id="pain_more", label="Ещё о боли"
                        ),
                        UiQuickReplyCandidate(
                            source_client_id="demo", reply_id="pain_last", label="Последний вопрос"
                        ),
                    ),
                    video=UiVideoCandidate(source_client_id="demo", video_id="pain_video"),
                    cta=UiButtonCandidate(
                        source_client_id="demo", button_id="pain_cta", label="Записаться", action_kind="cta"
                    ),
                ),
                D2SourceUiAuthority(
                    source_client_id="demo",
                    content_ref="warranty.md",
                    quick_replies=(
                        UiQuickReplyCandidate(
                            source_client_id="demo", reply_id="warranty_follow", label="О гарантии подробнее"
                        ),
                    ),
                    video=UiVideoCandidate(source_client_id="demo", video_id="warranty_video"),
                ),
            ],
        }
    )
    return ResponsePlanMaterializationSources.model_validate(payload)


def test_content_uses_only_the_selected_source_ui_and_keeps_source_cta() -> None:
    envelope = _parsed_envelope(
        requests=[_content_request(content_ref="pain.md", service_id="service_one", topic_id="implantation")],
        commercial_intent="none",
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _content_sources(), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.ui_plan.source_content_ref == "pain.md"
    assert outcome.ui_projection.video is not None
    assert outcome.ui_projection.video.video_id == "pain_video"
    assert [item.reply_id for item in outcome.ui_projection.quick_replies] == ["pain_follow"]
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["pain_cta"]
    assert "warranty" not in str(outcome.ui_projection).lower()


def test_two_clean_calls_do_not_repeat_selected_secondary_refs() -> None:
    envelope = _parsed_envelope(
        requests=[_content_request(content_ref="pain.md", service_id="service_one", topic_id="implantation")],
        commercial_intent="none",
    )

    first = resolve_d2_operations(
        (envelope).blocks, _content_sources(), as_of=date(2026, 9, 18)
    )
    shown = tuple(
        item.reply_id for item in first.ui_projection.quick_replies
    ) + ((first.ui_projection.video.video_id,) if first.ui_projection.video is not None else ())
    outcome = resolve_d2_operations(
        (envelope).blocks, _content_sources(shown=shown), as_of=date(2026, 9, 18)
    )

    assert outcome.ui_projection.video is None
    assert [item.reply_id for item in outcome.ui_projection.quick_replies] == [
        "pain_more",
        "pain_last",
    ]
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["pain_cta"]
    assert not set(shown) & {item.reply_id for item in outcome.ui_projection.quick_replies}


def test_warranty_does_not_inherit_pain_navigation() -> None:
    envelope = _parsed_envelope(
        requests=[_content_request(content_ref="warranty.md", service_id="service_one", topic_id="implantation")],
        commercial_intent="none",
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _content_sources(), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.ui_plan.source_content_ref == "warranty.md"
    assert outcome.ui_projection.video is not None
    assert outcome.ui_projection.video.video_id == "warranty_video"
    assert [item.reply_id for item in outcome.ui_projection.quick_replies] == ["warranty_follow"]
    assert outcome.ui_projection.buttons == ()


def test_missing_source_ui_keeps_the_approved_text_without_borrowing_navigation() -> None:
    envelope = _parsed_envelope(
        requests=[_content_request(content_ref="pain.md", service_id="service_one", topic_id="implantation")],
        commercial_intent="none",
    )
    payload = _content_sources().model_dump()
    payload["d2_source_ui"] = []
    source = ResponsePlanMaterializationSources.model_validate(payload)

    outcome = resolve_d2_operations((envelope).blocks, source, as_of=date(2026, 9, 18))

    assert outcome.rendered_text == MODEL_PROSE
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None
    assert outcome.ui_projection.buttons == ()


def test_price_plus_content_suppresses_source_secondary_but_keeps_source_cta() -> None:
    envelope = _parsed_envelope(
        requests=[
            _price_request(service_id="service_one", topic_id="implantation", request_id="r1"),
            _content_request(
                content_ref="pain.md",
                service_id="service_one",
                topic_id="implantation",
                request_id="r2",
            ),
        ],
        commercial_intent="price",
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _content_sources(), as_of=date(2026, 9, 18)
    )

    assert outcome.resolved.d2_price_block is not None
    assert outcome.rendered_text.endswith(MODEL_PROSE)
    assert outcome.ui_projection.video is None
    assert outcome.ui_projection.quick_replies == ()
    assert [item.button_id for item in outcome.ui_projection.buttons] == ["pain_cta"]


def test_two_independent_documents_do_not_borrow_first_document_cta() -> None:
    envelope = _parsed_envelope(
        requests=[
            _content_request(content_ref="pain.md", service_id="service_one",
                             topic_id="implantation", request_id="r1"),
            _content_request(content_ref="warranty.md", service_id="service_one",
                             topic_id="implantation", request_id="r2"),
        ],
        commercial_intent="none",
    )

    outcome = resolve_d2_operations(
        (envelope).blocks, _content_sources(), as_of=date(2026, 9, 18),
    )

    assert len(outcome.resolved.information_blocks) == 2
    assert outcome.resolved.ui_plan.source_content_ref == "pain.md"
    assert outcome.ui_projection.buttons == ()
    assert outcome.ui_projection.quick_replies == ()
    assert outcome.ui_projection.video is None


@pytest.mark.parametrize("second_ref", ["pain.md", "warranty.md", None, "missing.md"])
@pytest.mark.parametrize("reverse", [False, True])
def test_multiple_parts_share_ui_only_when_every_source_is_verified_and_the_same(second_ref, reverse):
    requests = [
        _content_request(content_ref="pain.md", service_id="service_one",
                         topic_id="implantation", request_id="r1"),
        _content_request(content_ref=second_ref, service_id="service_one",
                         topic_id="implantation", request_id="r2"),
    ]
    requests[0]["content_text"] = "Первое объяснение."
    requests[1]["content_text"] = "Независимое объяснение."
    if reverse:
        requests.reverse()
    result = resolve_d2_operations(
        _parsed_envelope(requests=requests, commercial_intent="none").blocks,
        _content_sources(), as_of=date(2026, 9, 18),
    )
    assert all(request["content_text"] in result.rendered_text for request in requests)
    if second_ref == "pain.md":
        assert result.ui_projection.video.video_id == "pain_video"
        assert [r.reply_id for r in result.ui_projection.quick_replies] == ["pain_follow"]
        assert [b.button_id for b in result.ui_projection.buttons] == ["pain_cta"]
    else:
        assert result.ui_projection.video is None
        assert result.ui_projection.quick_replies == ()
        assert result.ui_projection.buttons == ()


def test_foreign_source_ui_is_rejected_at_the_tenant_boundary() -> None:
    payload = _content_sources().model_dump()
    payload["d2_source_ui"] = [
        D2SourceUiAuthority(
            source_client_id="other",
            content_ref="pain.md",
        ).model_dump()
    ]
    with pytest.raises(ValueError, match="materialization_d2_source_ui_client_mismatch"):
        ResponsePlanMaterializationSources.model_validate(payload)


def test_invalid_optional_source_cta_is_omitted_with_a_diagnostic() -> None:
    envelope = _parsed_envelope(
        requests=[_content_request(content_ref="pain.md", service_id="service_one", topic_id="implantation")],
        commercial_intent="none",
    )
    payload = _content_sources().model_dump()
    payload["d2_source_ui"][0]["cta"]["action_kind"] = "contact"
    source = ResponsePlanMaterializationSources.model_validate(payload)

    outcome = resolve_d2_operations((envelope).blocks, source, as_of=date(2026, 9, 18))

    assert outcome.rendered_text == MODEL_PROSE
    assert outcome.ui_projection.buttons == ()
    assert [(item.code, item.detail) for item in outcome.materialization_diagnostics] == [
        ("materialization_optional_unavailable", ("d2_source_ui_cta_kind_invalid", "pain_cta")),
    ]
