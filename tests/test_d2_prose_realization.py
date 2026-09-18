from __future__ import annotations

from datetime import date
import socket

import pytest
from pydantic import ValidationError

from contracts.response_plan_materialization import (
    D2AuthoredContentAuthority,
    D2AuthoredContentSection,
    D2SourceUiAuthority,
)
from core.response_plan_materialization import resolve_d2_envelope_response
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui
from tests.test_d2_single_request import _parsed_envelope, _price_request, _sources


_AS_OF = date(2026, 9, 18)


def _prose_request(
    request_id: str = "r1",
    *,
    text: str = "Процедуру проводят с местным обезболиванием после осмотра.",
    fallback: str | None = None,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "policy_ids": [],
        "payment_scheme": "unspecified",
        "payment_scheme_intent": "not_requested",
        "contact_fields": [],
        "content_realization": "model_prose",
        "content_text": text,
        "content_ref": "pain.md",
        "content_section_refs": ["s:anesthesia", "s:preparation"],
        "content_fallback_section_ref": fallback,
        "service_id": "service_one",
        "topic_id": "implantation",
        "statement_mode": "question",
    }


def _content_authority() -> D2AuthoredContentAuthority:
    return D2AuthoredContentAuthority(
        source_client_id="demo",
        content_ref="pain.md",
        display_text="Общий утверждённый текст, не выбранный как fallback.",
        allowed_service_ids=("service_one",),
        sections=(
            D2AuthoredContentSection(
                section_ref="s:anesthesia", display_text="Точная цитата об анестезии."
            ),
            D2AuthoredContentSection(
                section_ref="s:preparation", display_text="Точная цитата о подготовке."
            ),
        ),
    )


def _resolve(*requests: dict[str, object]):
    price_ids = [item["request_id"] for item in requests if item["kind"] == "price"]
    envelope = _parsed_envelope(
        requests=list(requests), commercial_intent="price" if price_ids else "none"
    )
    source = _sources(content=(_content_authority(),)).model_copy(
        update={"d2_snapshot_fingerprint": "snapshot-c8"}
    )
    return resolve_d2_envelope_response(envelope, source, as_of=_AS_OF), source


def test_human_prose_is_rendered() -> None:
    outcome, _ = _resolve(_prose_request())

    block = outcome.resolved.information_blocks[0]
    assert outcome.rendered_text == "Процедуру проводят с местным обезболиванием после осмотра."
    assert "Служебный текст D1R." not in outcome.rendered_text
    assert block.publication == "model_prose"
    assert block.source_section_refs == ("s:anesthesia", "s:preparation")
    assert block.snapshot_fingerprint == "snapshot-c8"
    assert outcome.resolved.d2_request_parts[0].status == "answered"


def test_any_published_section_can_ground_prose() -> None:
    from tests.test_d2_demo_snapshot import _parsed_demo_envelope, _request

    raw = _request(
        "r1", "content", service_id="classic", topic_id="implantation",
        content_ref="implantation__faq__pain.md", section_refs=["a:sedatsiya-i-narkoz"],
    )
    raw.update({
        "content_realization": "model_prose",
        "content_text": "Обезболивание подбирают после оценки ситуации.",
    })
    snapshot, envelope, source = _parsed_demo_envelope(raw)
    outcome = resolve_d2_envelope_response(envelope, source, as_of=_AS_OF)

    assert snapshot.fingerprint == outcome.resolved.information_blocks[0].snapshot_fingerprint
    assert outcome.resolved.information_blocks[0].source_section_refs == ("a:sedatsiya-i-narkoz",)
    assert outcome.rendered_text == "Обезболивание подбирают после оценки ситуации."


def test_price_and_prose_preserve_request_order() -> None:
    price = _price_request(service_id="service_one", topic_id="implantation", request_id="r1")
    prose = _prose_request("r2")
    first, _ = _resolve(price, prose)
    second, _ = _resolve(prose, price)

    assert first.rendered_text.index("120 000") < first.rendered_text.index("Процедуру проводят")
    assert second.rendered_text.index("Процедуру проводят") < second.rendered_text.index("120 000")
    assert first.ui_projection.quick_replies == ()
    assert first.ui_projection.video is None


def test_two_content_parts_keep_distinct_sources() -> None:
    other = _prose_request("r2", text="Второй самостоятельный информационный ответ.")
    other["content_ref"] = "other.md"
    other["content_section_refs"] = ["s:other"]
    other["service_id"] = "service_two"
    other["topic_id"] = "therapy"
    authority = D2AuthoredContentAuthority(
        source_client_id="demo", content_ref="other.md", display_text="Другой материал.",
        allowed_service_ids=("service_two",),
        sections=(D2AuthoredContentSection(section_ref="s:other", display_text="Точная другая цитата."),),
    )
    envelope = _parsed_envelope(requests=[_prose_request(), other], commercial_intent="none")
    source = _sources(content=(_content_authority(), authority)).model_copy(
        update={"d2_snapshot_fingerprint": "snapshot-c8"}
    )
    outcome = resolve_d2_envelope_response(envelope, source, as_of=_AS_OF)

    assert [block.content_ref for block in outcome.resolved.information_blocks] == ["pain.md", "other.md"]
    assert [block.display_text for block in outcome.resolved.information_blocks] == [
        "Процедуру проводят с местным обезболиванием после осмотра.",
        "Второй самостоятельный информационный ответ.",
    ]


def test_authored_text_is_not_rewritten() -> None:
    authored = _prose_request()
    authored.update({"content_realization": "authored", "content_fallback_section_ref": None})
    outcome, _ = _resolve(authored)

    assert outcome.rendered_text == "Точная цитата об анестезии.\n\nТочная цитата о подготовке."
    assert outcome.resolved.information_blocks[0].publication == "authored"


def test_frozen_content_linkage_is_validated() -> None:
    outcome, _ = _resolve(_prose_request())
    frozen_text, frozen_ui = outcome.rendered_text, outcome.ui_projection
    payload = outcome.resolved.model_dump()
    payload["information_blocks"][0]["content_ref"] = "other.md"
    with pytest.raises(ValidationError, match="d2_request_part_content_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_request_parts"][0]["content_publication"] = "authored"
    with pytest.raises(ValidationError, match="d2_request_part_content_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    payload = outcome.resolved.model_dump()
    payload["d2_request_parts"][0]["status"] = "unavailable"
    payload["d2_request_parts"][0]["failure_reason"] = "d2_model_prose_money"
    payload["d2_request_parts"][0]["content_publication"] = None
    payload["d2_request_parts"][0]["snapshot_fingerprint"] = None
    with pytest.raises(ValidationError, match="d2_part_failure_block_linkage_invalid"):
        outcome.resolved.__class__.model_validate(payload)

    assert render_response_text(outcome.resolved) == frozen_text
    assert project_response_ui(outcome.resolved) == frozen_ui


def test_render_uses_only_frozen_content() -> None:
    outcome, _ = _resolve(_prose_request())
    frozen_text = outcome.rendered_text
    frozen_plan = outcome.resolved.model_copy(deep=True)

    assert render_response_text(frozen_plan) == frozen_text


def test_no_provider_or_legacy_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    import core.response_plan_materialization as materialization
    import core.response_plan_composer_executor as composer_executor
    import core.sales_one_plus_live_backend as live_backend

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("outside frozen D2 path")

    monkeypatch.setattr(materialization, "resolve_materialized_response", forbidden)
    monkeypatch.setattr(composer_executor, "execute_composer_decision", forbidden)
    monkeypatch.setattr(live_backend, "chat_completions_create", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    outcome, _ = _resolve(_prose_request())
    assert outcome.resolved.d2_result_status == "complete"
