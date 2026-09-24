"""R3-A: FullContext prose is the ordinary D2 answer, not a content route."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 24, tzinfo=timezone.utc)
INFO_GAP = "К сожалению, у меня пока недостаточно информации"
GUIDED_MENU = "Могу коротко подсказать и помочь выбрать направление"
TERM_CLARIFY = "Уточните, пожалуйста, что вы имеете в виду"


class RawProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.calls = 0

    def generate(self, _request) -> str:
        self.calls += 1
        return self.raw


def _raw(*, kind: str, text: str, service_id: str | None = None,
         topic_id: str | None = None, service_reference_status: str = "none",
         requested_service_id: str | None = None, brand_id: str | None = None, route: str = "ANSWER",
         clarify_axis: str | None = None) -> str:
    return json.dumps(production_envelope_template(
        route=route,
        clarify_axis=clarify_axis,
        commercial_intent="none",
        promotion_scope="none",
        service_reference_status=service_reference_status,
        requested_service_id=requested_service_id,
        request_understanding={
            "subjects": [],
            "requests": [{
                "request_id": "r1",
                "kind": kind,
                "subject_id": None,
                "context": "general_information",
                "policy_ids": [],
                "payment_scheme": "unspecified",
                "payment_scheme_intent": "unspecified",
                "contact_fields": [],
                "content_text": text,
                "content_realization": "model_prose" if kind == "content" else "authored",
                "content_ref": None,
                "content_section_refs": [],
                "content_fallback_section_ref": None,
                "service_id": service_id,
                "topic_id": topic_id,
                "brand_id": brand_id,
                "statement_mode": "question",
                "situation": None,
            }],
        },
    ), ensure_ascii=False)


def _run(tmp_path: Path, raw: str, question: str) -> str:
    provider = RawProvider(raw)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        turn = run_d2_dialogue_turn(
            session_key=SessionKey(client_id="demo", sid="r3-free"),
            user_message=question,
            provider=provider,
            clients_root=Path("clients"),
            store=store,
            now=NOW,
        )
    assert provider.calls == 1
    return turn.response.rendered_text


def test_service_question_without_content_ref_keeps_model_prose(tmp_path: Path) -> None:
    text = "All-on-4 — способ восстановить зубы на одной челюсти с опорой на четыре импланта."
    answer = _run(
        tmp_path,
        _raw(kind="content", text=text, service_id="all_on_4", topic_id="implantation"),
        "Вы делаете All-on-4?",
    )
    assert text in answer
    assert INFO_GAP not in answer


def test_greeting_prose_is_not_replaced_by_guided_menu(tmp_path: Path) -> None:
    text = "Здравствуйте! Расскажу о лечении, услугах и организации приёма."
    answer = _run(tmp_path, _raw(kind="other", text=text), "Привет")
    assert text in answer
    assert GUIDED_MENU not in answer


def test_clearly_unresolved_term_gets_honest_gap_not_model_prose(tmp_path: Path) -> None:
    answer = _run(
        tmp_path,
        _raw(
            kind="content",
            text="This prose must not be published for a clearly unresolved term.",
            service_reference_status="unresolved",
        ),
        "What is flumbodontia?",
    )
    assert "У меня нет информации" in answer
    assert "must not be published" not in answer


def test_inactive_service_uses_authored_alternative(tmp_path: Path) -> None:
    answer = _run(
        tmp_path,
        _raw(
            kind="content",
            text="This prose must not replace the clinic policy.",
            service_reference_status="resolved",
            requested_service_id="braces",
        ),
        "Do you offer braces?",
    )
    assert "Брекеты мы не устанавливаем" in answer
    assert "элайнеры" in answer.casefold()
    assert "must not replace" not in answer


def test_ambiguous_name_uses_code_owned_term_clarification(tmp_path: Path) -> None:
    answer = _run(
        tmp_path,
        _raw(
            kind="content",
            text="Model wording must not be used for the strict clarification.",
            route="CLARIFY",
            clarify_axis="term",
        ),
        "Can you tell me about that thing?",
    )
    assert "Уточните" in answer
    assert "Model wording" not in answer


def test_typed_brand_policy_uses_approved_osstem_text(tmp_path: Path) -> None:
    answer = _run(
        tmp_path,
        _raw(kind="content", text="Model prose must not replace the brand policy.", brand_id="osstem"),
        "Do you use Osstem?",
    )
    assert "Osstem в ассортименте нет" in answer
    assert "Model prose" not in answer


def test_valid_content_ref_does_not_replace_default_fullcontext_prose(tmp_path: Path) -> None:
    text = "FullContext reply must survive a provenance reference."
    payload = json.loads(_raw(kind="content", text=text, service_id="all_on_4", topic_id="implantation"))
    request = payload["request_understanding"]["requests"][0]
    request.pop("content_realization")
    request["content_ref"] = "implantation__service__all_on_4.md"
    request["content_section_refs"] = []
    answer = _run(tmp_path, json.dumps(payload), "Tell me about All-on-4")
    assert text in answer


def test_optional_provenance_without_typed_scope_keeps_fullcontext_prose(tmp_path: Path) -> None:
    text = "Понимаю, что лечение может тревожить. Врач заранее обсудит обезболивание."
    payload = json.loads(_raw(kind="content", text=text))
    request = payload["request_understanding"]["requests"][0]
    request["content_ref"] = "implantation__service__all_on_4.md"
    answer = _run(tmp_path, json.dumps(payload, ensure_ascii=False), "Я боюсь боли")
    assert text in answer


def test_direct_question_keeps_live_prose_when_optional_ref_is_wrong(tmp_path: Path) -> None:
    text = "После установки врач объяснит уход на ближайшие дни."
    payload = json.loads(_raw(kind="content", text=text,
                              service_id="classic", topic_id="implantation"))
    part = payload["request_understanding"]["requests"][0]
    part["content_ref"] = "missing.md"
    part["content_section_refs"] = ["a:missing"]
    answer = _run(tmp_path, json.dumps(payload, ensure_ascii=False),
                  "Как ухаживать после установки импланта?")
    assert text in answer
    assert INFO_GAP not in answer


def test_section_click_keeps_verified_source_and_gets_live_prose(tmp_path: Path) -> None:
    content_ref = "implantation__faq__pain.md"
    first = json.loads(_raw(kind="content", text="Врач обсудит обезболивание заранее.",
                            service_id="classic", topic_id="implantation"))
    first_part = first["request_understanding"]["requests"][0]
    first_part.update({"content_ref": content_ref, "content_section_refs": ["a:korotko"]})
    follow = json.loads(_raw(kind="content", text="Первые 2–3 дня после установки возможен умеренный дискомфорт.",
                             service_id="classic", topic_id="implantation"))
    follow_part = follow["request_understanding"]["requests"][0]
    follow_part.update({"content_ref": content_ref,
                        "content_section_refs": ["a:kakuyu-anesteziyu-ispolzuyut"]})

    class SequenceProvider:
        def __init__(self, raws) -> None:
            self.raws = list(raws)
            self.inputs = []

        def generate(self, request):
            self.inputs.append(request)
            return self.raws.pop(0)

    provider = SequenceProvider((json.dumps(first, ensure_ascii=False),
                                 json.dumps(follow, ensure_ascii=False)))
    key = SessionKey(client_id="demo", sid="r3-section-click")
    with D2DialogueStore(tmp_path / "click.sqlite") as store:
        first_turn = run_d2_dialogue_turn(
            session_key=key, user_message="Я боюсь боли при имплантации",
            provider=provider, clients_root=Path("clients"), store=store,
            now=NOW, request_id="first",
        )
        reply = next(item for item in first_turn.response.ui_projection.quick_replies
                     if "Какую анестезию" in item.label)
        assert "{#" not in reply.label
        second_turn = run_d2_dialogue_turn(
            session_key=key, user_message="", lead_ui_ref=reply.reply_id,
            ui_revision=first_turn.committed_revision, provider=provider,
            clients_root=Path("clients"), store=store,
            now=NOW, request_id="follow",
        )

    assert provider.inputs[1].selected_content_ref == content_ref
    assert provider.inputs[1].selected_section_ref == "a:kakuyu-anesteziyu-ispolzuyut"
    assert provider.inputs[1].user_message != reply.label
    assert "Первые 2–3 дня после установки возможен умеренный дискомфорт." in second_turn.response.rendered_text
    assert "{#" not in second_turn.response.rendered_text
    assert second_turn.response.resolved.information_blocks[0].publication == "model_prose"

    wrong = json.loads(json.dumps(follow, ensure_ascii=False))
    wrong_part = wrong["request_understanding"]["requests"][0]
    wrong_part["content_ref"] = "clinic__info__warranty.md"
    wrong_part["content_section_refs"] = []
    wrong_provider = SequenceProvider((json.dumps(first, ensure_ascii=False),
                                       json.dumps(wrong, ensure_ascii=False)))
    wrong_key = SessionKey(client_id="demo", sid="r3-section-wrong-source")
    with D2DialogueStore(tmp_path / "click.sqlite") as store:
        wrong_first = run_d2_dialogue_turn(
            session_key=wrong_key, user_message="Я боюсь боли при имплантации",
            provider=wrong_provider, clients_root=Path("clients"), store=store,
            now=NOW, request_id="wrong-first",
        )
        wrong_reply = next(item for item in wrong_first.response.ui_projection.quick_replies
                           if "Какую анестезию" in item.label)
        recovered_click = run_d2_dialogue_turn(
            session_key=wrong_key, user_message="", lead_ui_ref=wrong_reply.reply_id,
            ui_revision=wrong_first.committed_revision, provider=wrong_provider,
            clients_root=Path("clients"), store=store,
            now=NOW, request_id="wrong-follow",
        )
    recovered_part = recovered_click.response.resolved.d2_request_parts[0]
    assert recovered_part.status == "answered"
    assert recovered_part.content_ref == content_ref
    assert recovered_part.content_section_refs == ("a:kakuyu-anesteziyu-ispolzuyut",)
    assert "Первые 2–3 дня" in recovered_click.response.rendered_text

    omitted = json.loads(json.dumps(follow, ensure_ascii=False))
    omitted_part = omitted["request_understanding"]["requests"][0]
    omitted_part["content_ref"] = None
    omitted_part["content_section_refs"] = []
    omitted_provider = SequenceProvider((json.dumps(first, ensure_ascii=False),
                                         json.dumps(omitted, ensure_ascii=False)))
    omitted_key = SessionKey(client_id="demo", sid="r3-section-omitted-source")
    with D2DialogueStore(tmp_path / "click.sqlite") as store:
        omitted_first = run_d2_dialogue_turn(
            session_key=omitted_key, user_message="Я боюсь боли при имплантации",
            provider=omitted_provider, clients_root=Path("clients"), store=store,
            now=NOW, request_id="omitted-first",
        )
        omitted_reply = next(item for item in omitted_first.response.ui_projection.quick_replies
                             if "Какую анестезию" in item.label)
        omitted_click = run_d2_dialogue_turn(
            session_key=omitted_key, user_message="", lead_ui_ref=omitted_reply.reply_id,
            ui_revision=omitted_first.committed_revision, provider=omitted_provider,
            clients_root=Path("clients"), store=store,
            now=NOW, request_id="omitted-follow",
        )
    assert omitted_click.response.resolved.d2_request_parts[0].content_ref == content_ref
    assert "Первые 2–3 дня" in omitted_click.response.rendered_text


def test_free_fullcontext_prose_and_exact_price_share_one_answer(tmp_path: Path) -> None:
    prose = "All-on-4 explanation from the approved FullContext corpus."
    payload = production_envelope_template(
        commercial_intent="price", primary_price_request_id="r2",
        request_understanding={"subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}], "requests": [
            {"request_id": "r1", "kind": "content", "subject_id": None,
             "context": "general_information", "content_text": prose,
             "service_id": "all_on_4", "topic_id": "implantation"},
            {"request_id": "r2", "kind": "price", "subject_id": "s1",
             "context": "general_information", "service_id": None,
             "topic_id": "implantation"},
        ]},
    )
    answer = _run(tmp_path, json.dumps(payload), "Explain All-on-4 and its price")
    assert prose in answer
    assert "₽" in answer


def test_free_fullcontext_prose_and_exact_contact_share_one_answer(tmp_path: Path) -> None:
    prose = "A free FullContext explanation remains the conversational answer."
    payload = production_envelope_template(
        request_understanding={"subjects": [], "requests": [
            {"request_id": "r1", "kind": "content", "subject_id": None,
             "context": "general_information", "content_text": prose,
             "service_id": "all_on_4", "topic_id": "implantation"},
            {"request_id": "r2", "kind": "contact", "subject_id": None,
             "context": "general_information", "contact_fields": ["contact_address"],
             "content_text": None, "service_id": None, "topic_id": None},
        ]},
    )
    answer = _run(tmp_path, json.dumps(payload), "Tell me about All-on-4 and your address")
    assert prose in answer
    assert "г. Москва, ул. Тверская, 12" in answer


def test_exact_contact_still_works_without_a_free_prose_part(tmp_path: Path) -> None:
    payload = production_envelope_template(
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "contact", "subject_id": None,
            "context": "general_information", "contact_fields": ["contact_phone"],
            "content_text": None, "service_id": None, "topic_id": None,
        }]},
    )
    answer = _run(tmp_path, json.dumps(payload), "What is your phone number?")
    assert "+7 (495) 128-47-60" in answer


def test_free_prose_price_and_contact_use_one_typed_composition(tmp_path: Path) -> None:
    prose = "The FullContext model explains the method in its own words."
    payload = production_envelope_template(
        commercial_intent="price", primary_price_request_id="r3",
        request_understanding={"subjects": [{"subject_id": "s1", "relation": "self", "age_group": "unknown"}], "requests": [
            {"request_id": "r1", "kind": "content", "subject_id": None,
             "context": "general_information", "content_text": prose,
             "service_id": "all_on_4", "topic_id": "implantation"},
            {"request_id": "r2", "kind": "contact", "subject_id": None,
             "context": "general_information", "contact_fields": ["contact_address"],
             "content_text": None, "service_id": None, "topic_id": None},
            {"request_id": "r3", "kind": "price", "subject_id": "s1",
             "context": "general_information", "service_id": None, "topic_id": "implantation"},
        ]},
    )
    answer = _run(tmp_path, json.dumps(payload), "Explain All-on-4, its price, and your address")
    assert prose in answer
    assert "₽" in answer
    assert "г. Москва, ул. Тверская, 12" in answer
    assert answer.index(prose) < answer.index("г. Москва, ул. Тверская, 12") < answer.index("₽")


def test_available_contact_keeps_information_text_with_number(tmp_path: Path) -> None:
    payload = production_envelope_template(
        request_understanding={"subjects": [], "requests": [
            {"request_id": "r1", "kind": "content", "subject_id": None,
             "context": "general_information", "content_text": "100 ₽",
             "content_ref": None, "service_id": None, "topic_id": None},
            {"request_id": "r2", "kind": "contact", "subject_id": None,
             "context": "general_information", "contact_fields": ["contact_phone"],
             "content_text": None, "service_id": None, "topic_id": None},
        ]},
    )
    answer = _run(tmp_path, json.dumps(payload), "Tell me about something and give me your phone")
    assert "100 ₽" in answer
    assert "+7 (495) 128-47-60" in answer


def test_free_fullcontext_prose_and_exact_commercial_fact_share_one_answer(tmp_path: Path) -> None:
    prose = "The model explains how the clinic organizes treatment financing."
    payload = production_envelope_template(
        commercial_intent="payment",
        references={"direct_fact_ids": ["installment_12"]},
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "content", "subject_id": None,
            "context": "general_information", "content_text": prose,
            "service_id": "all_on_4", "topic_id": "implantation",
        }]},
    )
    answer = _run(tmp_path, json.dumps(payload), "Explain All-on-4 and whether installment is available")
    assert prose in answer
    assert "12" in answer
