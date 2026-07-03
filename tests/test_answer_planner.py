from __future__ import annotations

import pytest

from contracts.dialog_focus import DialogFocusDecision
from contracts.answer_plan import AnswerPlan
from contracts.source_route_result import SourceRouteResult
from core.answer_plan_apply import (
    append_text_has_payment_stages,
    apply_answer_plan_append,
    clean_answer_for_applied_appends,
    payment_terms_suppress_refs,
    render_payment_terms_append,
    render_warranty_terms_append,
    should_suppress_payment_terms_quick_ref,
    suppress_payment_terms,
)
from core.answer_planner import build_answer_plan, detect_aspects
from session import mem_reset, set_last_subject


def test_detect_aspects_price_and_payment():
    aspects = detect_aspects("Сколько стоит имплант и есть ли рассрочка?")
    assert "price" in aspects
    assert "payment" in aspects


def test_build_answer_plan_composite_append():
    plan = build_answer_plan(
        q="Сколько стоит classic с коронкой и можно ли в рассрочку?",
        sid="t1",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert "price" in plan.aspects
    assert "payment" in plan.aspects
    assert "payment_terms" in plan.append


def test_build_answer_plan_adds_warranty_append_for_service_question():
    plan = build_answer_plan(
        q="А вы делаете all-on-4 и какие гарантии на нее?",
        sid="t_all_on_4_warranty",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=SourceRouteResult(
            source="catalog_md",
            service_id="all_on_4",
            ref="implantation__service__all_on_4.md#korotko",
            match_score=1.0,
            match_method="catalog_containment",
        ),
    )
    assert "warranty" in plan.aspects
    assert "warranty_terms" in plan.append
    assert plan.service_id == "all_on_4"


def test_primary_aspect_only_from_current_question():
    plan = build_answer_plan(
        q="а это?",
        sid="t_no_carry",
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert plan.aspects == ["overview"]
    assert plan.primary_aspect is None
    assert plan.append == []


def test_follow_up_payment_uses_last_subject():
    sid = "t_follow_payment"
    mem_reset(sid)
    set_last_subject(
        sid,
        service_id="classic",
        topic="implantation",
        label="Классическая имплантация",
    )
    plan = build_answer_plan(
        q="рассрочка?",
        sid=sid,
        client_id="demo",
        intent="content",
        decision=None,
        source_route=None,
    )
    assert plan.service_id == "classic"
    assert "payment" in plan.aspects
    assert "payment_terms" in plan.append
    assert "price_offer" not in plan.append


def test_planner_uses_dialog_focus_for_attribute_without_session_subject():
    app = pytest.importorskip("flask").Flask(__name__)
    with app.test_request_context("/"):
        from flask import request

        request.ctx = {
            "dialog_focus_decision": DialogFocusDecision(
                focus_service_id="classic",
                focus_topic="implantation",
                focus_label="Классическая имплантация",
                focus_turn_age=0,
                attribute="warranty",
                explicit_topic_change=False,
                resolved_service_id="classic",
                source="last_subject",
                used_llm=False,
                confidence=0.8,
                reason="test",
            ).model_dump()
        }
        plan = build_answer_plan(
            q="Гарантия какая?",
            sid="planner-dialog-focus",
            client_id="demo",
            intent="content",
            decision=None,
            source_route=None,
        )
    assert plan.service_id == "classic"
    assert "warranty" in plan.aspects
    assert "dialog_focus" in plan.plan_reason


def test_suppress_payment_terms_when_answer_has_installment():
    assert suppress_payment_terms(
        existing_append=None,
        price_offer_meta=None,
        answer_body="Доступна рассрочка от клиники до 12 месяцев.",
    )


def test_suppress_payment_terms_not_for_surgical_stages_only():
    assert not suppress_payment_terms(
        existing_append="**Оплата по этапам:**\n- Хирургический этап — 50 000 ₽",
        price_offer_meta={"price_offers_applied": True},
        answer_body=None,
    )


def test_apply_plan_skips_payment_terms_if_answer_has_installment():
    plan = AnswerPlan(
        aspects=["price", "payment"],
        primary_aspect="price",
        service_id="classic",
        append=["price_offer", "payment_terms"],
    )
    tail, meta = apply_answer_plan_append(
        plan,
        client_id="demo",
        service_id="classic",
        q="цена и рассрочка",
        existing_append=None,
        price_offer_meta={"price_offers_applied": True},
        answer_body="Точные цены ... Доступна рассрочка от клиники.",
    )
    assert "payment_terms" in meta.get("suppressed", []) or "payment_terms" not in meta.get(
        "applied", []
    )


def test_render_payment_terms_append_demo():
    text = render_payment_terms_append(client_id="demo")
    assert text
    assert "рассроч" in text.lower()


def test_render_warranty_terms_append_demo():
    text = render_warranty_terms_append(client_id="demo")
    assert text
    assert "гарантия на работу врача" in text.lower()


def test_apply_plan_adds_warranty_and_clean_negative_answer():
    plan = AnswerPlan(
        aspects=["warranty"],
        primary_aspect="warranty",
        service_id="all_on_4",
        append=["warranty_terms"],
    )
    answer = "Да, мы проводим имплантацию по методике All-on-4.\n\nГарантийные сроки в этом материале не указаны."
    tail, meta = apply_answer_plan_append(
        plan,
        client_id="demo",
        service_id="all_on_4",
        q="all-on-4 и гарантия",
        existing_append=None,
        price_offer_meta=None,
        answer_body=answer,
    )
    cleaned = clean_answer_for_applied_appends(answer, meta.get("applied") or [])
    assert "warranty_terms" in meta.get("applied", [])
    assert tail and "пожизн" in tail.lower()
    assert "не указаны" not in cleaned.lower()


def test_suppress_payment_terms_ref_when_primary_doc_is_payment_terms():
    assert should_suppress_payment_terms_quick_ref(doc_id="clinic__info__payment_terms")


def test_suppress_payment_terms_ref_when_append_suppressed_not_applied():
    plan_meta = {
        "answer_plan": {"append": ["payment_terms"]},
        "answer_plan_apply": {
            "applied": [],
            "suppressed": ["payment_terms"],
        },
    }
    assert should_suppress_payment_terms_quick_ref(plan_meta=plan_meta)
    assert payment_terms_suppress_refs(plan_meta=plan_meta)


def test_suppress_payment_terms_ref_when_answer_covers_installment():
    plan_meta = {"answer_plan": {"append": ["payment_terms"]}}
    body = "Да, у нас есть рассрочка до 12 месяцев."
    assert should_suppress_payment_terms_quick_ref(plan_meta=plan_meta, answer_body=body)
