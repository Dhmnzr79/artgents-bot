from __future__ import annotations

from contracts.response_plan import ComposerResult, PricePlan, RouteModePair
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from tests.test_response_plan_contract import (
    admin_terminal,
    compose,
    contacts_terminal,
    deterministic_route_authority,
    make_plan,
    price_single,
)


def _normal_overrides() -> dict[str, object]:
    return {
        "price_plan": PricePlan(kind="none"),
        "textual_cta_candidate": None,
        "service_value_candidate": None,
        "selected_topic_id": "implantation",
    }


def test_normal_order() -> None:
    plan = make_plan(**_normal_overrides())
    resolved = resolve_response_plan(
        plan,
        compose(patient_text="Основной ответ", requested_fact_ids=("installment_12",)),
    )
    text = render_response_text(resolved)
    assert text.startswith("Основной ответ")
    assert "installment_12" in text


def test_price_order_single_block() -> None:
    plan = make_plan()
    resolved = resolve_response_plan(
        plan,
        compose(patient_text="Пояснение"),
    )
    text = render_response_text(resolved)
    assert text.startswith("120 000 ₽ за имплант")
    assert "Цена указана за челюсть" in text
    assert "Пояснение" in text


def test_multi_price_renders_one_section() -> None:
    from tests.test_response_plan_contract import price_multi

    plan = make_plan(
        price_plan=price_multi(),
        required_offer_conditions=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Ответ"))
    text = render_response_text(resolved)
    assert text.count("100 000") == 1
    assert text.count("150 000") == 1
    assert text.index("100 000") < text.index("150 000")


def test_exactly_one_amplifier_list() -> None:
    plan = make_plan(**_normal_overrides())
    text = render_response_text(resolve_response_plan(plan, compose(patient_text="Ответ")))
    assert text.count("Также мы предлагаем:") == 1


def test_no_amplifiers_no_header() -> None:
    plan = make_plan(**_normal_overrides(), automatic_amplifier_candidate_ids=())
    text = render_response_text(resolve_response_plan(plan, compose(patient_text="Ответ")))
    assert "Также мы предлагаем:" not in text


def test_warranty_once_when_requested() -> None:
    plan = make_plan(**_normal_overrides())
    resolved = resolve_response_plan(
        plan,
        compose(requested_fact_ids=("implant_warranty",), patient_text="Ответ"),
    )
    assert render_response_text(resolved).count("implant_warranty") == 1


def test_warranty_absent_when_not_requested() -> None:
    plan = make_plan(**_normal_overrides())
    text = render_response_text(resolve_response_plan(plan, compose(patient_text="Ответ")))
    assert "implant_warranty" not in text


def test_foreign_amount_in_patient_text_preserved() -> None:
    plan = make_plan()
    resolved = resolve_response_plan(
        plan,
        compose(patient_text="Слышал, что это стоит 999 999 ₽"),
    )
    assert "999 999 ₽" in render_response_text(resolved)


def test_admin_uses_terminal_text_not_patient_text() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="ADMIN", mode="standard", patient_text=None),
    )
    assert resolved.patient_text is None
    assert render_response_text(resolved) == "ADMIN TEXT"


def test_contacts_uses_terminal_text() -> None:
    plan = make_plan(
        route_authority=deterministic_route_authority(
            terminal=contacts_terminal(text="Контакты demo"),
        ),
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(plan, None)
    assert render_response_text(resolved) == "Контакты demo"


def test_clarify_uses_patient_text_only() -> None:
    plan = make_plan(
        price_plan=PricePlan(kind="none"),
        response_scope="clinic",
        selected_service_id=None,
        textual_cta_candidate=None,
        service_value_candidate=None,
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
    )
    resolved = resolve_response_plan(
        plan,
        ComposerResult(route="CLARIFY", mode="standard", patient_text="Уточните услугу."),
    )
    assert render_response_text(resolved) == "Уточните услугу."


def test_clinic_topic_answer_without_service_renders_normally() -> None:
    plan = make_plan(
        response_scope="topic",
        selected_service_id=None,
        selected_topic_id="technologies",
        price_plan=PricePlan(kind="none"),
        promo_candidate_ids=(),
        automatic_amplifier_candidate_ids=(),
        service_value_candidate=None,
        textual_cta_candidate=None,
    )
    resolved = resolve_response_plan(plan, compose(patient_text="Цифровая диагностика доступна."))
    assert render_response_text(resolved) == "Цифровая диагностика доступна."


def test_deterministic_repeated_rendering() -> None:
    plan = make_plan()
    resolved = resolve_response_plan(
        plan,
        compose(patient_text="Ответ"),
    )
    assert render_response_text(resolved) == render_response_text(resolved)
