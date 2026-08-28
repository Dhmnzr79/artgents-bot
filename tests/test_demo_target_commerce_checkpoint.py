"""Demo commerce checkpoint: canonical facts, bindings, selector and widget paths."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from core.response_schema_loader import load_response_schema_bundle
from core.target_marketing_selector import select_target_marketing
from core.target_runtime_session import read_target_runtime_session
from session import bind_session_client, mem_reset
from tests.test_sales_fast_widget_integration import (
    _CountingBackend,
    _orchestrate_ask,
    _run_widget_turn_keep_session,
    flask_app,
)
from tests.test_sales_one_plus_turn import answer_envelope

from tests.test_demo_target_marketing_selection import _real_inputs

TARGET_ROOT = Path("clients/demo/target_response")

IMPLANT_GROUP = (
    "classic",
    "one_stage",
    "all_on_4",
    "all_on_6",
    "bone_graft",
    "sinus_lift",
    "zygomatic_implants",
    "pterygoid_implants",
    "temporary_teeth",
    "implant_supported_prosthetics",
    "veneers",
    "zirconia_crowns",
    "clasp_dentures",
    "removable_dentures",
)
SAME_DAY_SERVICES = (
    "classic",
    "one_stage",
    "all_on_4",
    "all_on_6",
    "bone_graft",
    "sinus_lift",
    "zygomatic_implants",
    "pterygoid_implants",
)
OTHER_ACTIVE = (
    "tomography",
    "professional_whitening",
    "caries",
    "pulpitis",
    "teeth_treatment",
    "tooth_extraction",
    "periodontitis",
    "aligners",
)
ALL_ACTIVE = frozenset(IMPLANT_GROUP + OTHER_ACTIVE)
PROMO_IDS = frozenset(
    {
        "implant_same_day_discount",
        "free_implant_consult",
        "professional_whitening_discount",
    }
)
AUTO_AMP_IDS = frozenset(
    {"installment_12", "tax_deduction", "payment_stages", "fixed_price"}
)
SV_IDS = frozenset({"sv_3d_diagnocat", "sv_aprf"})

TAX_TEXT = (
    "Поможем подготовить документы для оформления налогового вычета за лечение."
)
INSTALLMENT_TEXT = (
    "Доступна рассрочка на имплантацию и протезирование до 12 месяцев; "
    "оформление на консультации."
)
PAYMENT_STAGES_TEXT = "Доступна оплата лечения по этапам."
FIXED_PRICE_TEXT = (
    "Стоимость согласованного плана лечения фиксируется в договоре до начала лечения."
)
CONSULT_TEXT = (
    "До 31 декабря 2026 — бесплатная консультация по имплантации и протезированию. "
    "На консультации подготовим три варианта плана лечения по стоимости, "
    "чтобы вы могли выбрать подходящий под свой бюджет. "
    "Врач подскажет, какой протокол или конструкция подойдут именно вам. "
    "КТ при необходимости оплачивается отдельно."
)
SAME_DAY_TEXT = "При оплате в день обращения — скидка до 15% на имплантацию."
WHITENING_TEXT = (
    "Сейчас на профессиональное отбеливание действует скидка 10% "
    "до 30 ноября 2026 года."
)
SV_3D_TEXT = (
    "Имплантацию планируем по 3D-диагностике: заранее оцениваем костную ткань "
    "и позицию импланта. При необходимости подключаем ИИ-анализ снимков Diagnocat — "
    "он помогает врачу точнее разобрать 3D-изображение и не упустить важные детали."
)
WARRANTY_TEXT = (
    "Гарантия на работу врача — 1 год (корректировки и помощь бесплатно). "
    "На импланты Impro и Nobel — пожизненная, на Implantium — 5 лет."
)
TODAY = date(2026, 7, 21)


def _bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def test_demo_commerce_fact_inventory_and_stable_ids() -> None:
    bundle = _bundle()
    assert set(bundle.facts) == PROMO_IDS | AUTO_AMP_IDS | SV_IDS | {"implant_warranty"}
    assert {f.kind for f in bundle.facts.values() if f.id in PROMO_IDS} == {"promo"}
    assert bundle.facts["sv_3d_diagnocat"].kind == "service_value"
    assert bundle.facts["sv_aprf"].kind == "service_value"


def test_warranty_kept_out_of_automatic_lists() -> None:
    bundle = _bundle()
    assert bundle.facts["implant_warranty"].active is True
    ordered = bundle.marketing.ordered_amplifier_refs
    assert "fact:implant_warranty" not in ordered
    for mapping in bundle.marketing.service_automatic_commercial.values():
        for block in (mapping.service, mapping.price):
            if block is None:
                continue
            assert "fact:implant_warranty" not in block.ordered_amplifier_refs
            assert "fact:implant_warranty" not in block.ordered_promo_refs


def test_all_active_services_have_explicit_profiles() -> None:
    bundle = _bundle()
    sac = bundle.marketing.service_automatic_commercial
    assert set(sac) == ALL_ACTIVE
    assert "braces" not in sac
    assert bundle.services["braces"].active is False


def test_implant_group_service_and_price_bindings() -> None:
    bundle = _bundle()
    for service_id in IMPLANT_GROUP:
        mapping = bundle.marketing.service_automatic_commercial[service_id]
        assert mapping.service is not None
        assert mapping.price is not None
        if service_id in SAME_DAY_SERVICES:
            assert list(mapping.service.ordered_promo_refs) == [
                "fact:implant_same_day_discount",
                "fact:free_implant_consult",
            ]
        else:
            assert list(mapping.service.ordered_promo_refs) == ["fact:free_implant_consult"]
        assert list(mapping.service.ordered_amplifier_refs) == [
            "fact:installment_12",
            "fact:tax_deduction",
        ]
        assert list(mapping.price.ordered_amplifier_refs) == [
            "fact:installment_12",
            "fact:tax_deduction",
            "fact:payment_stages",
            "fact:fixed_price",
        ]
        assert "fact:fixed_price" not in mapping.service.ordered_amplifier_refs


def test_other_active_services_bindings() -> None:
    bundle = _bundle()
    for service_id in OTHER_ACTIVE:
        mapping = bundle.marketing.service_automatic_commercial[service_id]
        if service_id == "professional_whitening":
            assert list(mapping.service.ordered_promo_refs) == [
                "fact:professional_whitening_discount",
            ]
        else:
            assert list(mapping.service.ordered_promo_refs) == []
        assert list(mapping.service.ordered_amplifier_refs) == [
            "fact:tax_deduction",
            "fact:fixed_price",
        ]
        assert list(mapping.price.ordered_amplifier_refs) == [
            "fact:tax_deduction",
            "fact:fixed_price",
        ]
        assert "fact:installment_12" not in mapping.service.ordered_amplifier_refs


def test_service_value_refs_in_catalog_only() -> None:
    bundle = _bundle()
    sv_3d_services = {
        "classic",
        "one_stage",
        "all_on_4",
        "all_on_6",
        "zygomatic_implants",
        "pterygoid_implants",
    }
    sv_aprf_services = {"bone_graft", "sinus_lift"}
    for service_id, service in bundle.services.items():
        if service_id in sv_3d_services:
            assert service.service_value_ref == "fact:sv_3d_diagnocat"
        elif service_id in sv_aprf_services:
            assert service.service_value_ref == "fact:sv_aprf"
        else:
            assert service.service_value_ref is None


def test_whitening_date_boundary() -> None:
    bundle, doctors, index = _real_inputs()
    active = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="professional_whitening",
        today=date(2026, 11, 30),
        include_initial_block=True,
    )
    expired = select_target_marketing(
        bundle,
        doctors,
        index,
        semantic_context="service",
        service_id="professional_whitening",
        today=date(2026, 12, 1),
        include_initial_block=True,
    )
    assert active.selected_refs == ("fact:professional_whitening_discount",)
    assert expired.selected_refs == ()


def test_widget_all_on_4_price_turn_shows_price_promos_and_four_amplifiers(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.sales_fast_presentation import AUTOMATIC_AMPLIFIER_LIST_HEADER

    sid = "demo-commerce-allon4-price"
    bind_session_client("demo")
    mem_reset(sid)
    payload, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит All-on-4 на нижнюю челюсть?",
        envelope_json=answer_envelope(
            "All-on-4 на нижнюю челюсть — 368 000 ₽.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
        ),
        flask_app=flask_app,
    )
    answer = str(payload.get("answer") or "")
    assert "368" in answer
    assert SAME_DAY_TEXT in answer
    assert CONSULT_TEXT in answer
    assert answer.count(AUTOMATIC_AMPLIFIER_LIST_HEADER) == 1
    assert INSTALLMENT_TEXT in answer
    assert TAX_TEXT in answer
    assert PAYMENT_STAGES_TEXT in answer
    assert FIXED_PRICE_TEXT in answer
    assert SV_3D_TEXT not in answer
    session = read_target_runtime_session(sid)
    assert session.shown_service_value_ids == ()


def test_widget_all_on_4_service_turn_shows_sv_without_price_only_amplifiers(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "demo-commerce-allon4-service"
    bind_session_client("demo")
    mem_reset(sid)
    payload, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Расскажите про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол восстановления всех зубов на четырёх имплантах.",
            commercial_intent="none",
            service_id="all_on_4",
            extent="full_arch",
        ),
        flask_app=flask_app,
    )
    answer = str(payload.get("answer") or "")
    assert SV_3D_TEXT in answer
    assert INSTALLMENT_TEXT in answer
    assert TAX_TEXT in answer
    assert PAYMENT_STAGES_TEXT not in answer
    assert FIXED_PRICE_TEXT not in answer


def test_widget_zirconia_crowns_has_consult_without_implant_discount(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "demo-commerce-zirconia"
    payload = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "Коронки из диоксида циркония восстанавливают разрушенный зуб.",
                commercial_intent="none",
                service_id="zirconia_crowns",
            )
        ),
        q="Расскажите про коронки из циркония",
        sid=sid,
    )
    answer = str(payload.get("answer") or "")
    assert CONSULT_TEXT in answer
    assert SAME_DAY_TEXT not in answer
    assert INSTALLMENT_TEXT in answer
    assert TAX_TEXT in answer


def test_widget_whitening_and_extraction_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    whitening = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "Профессиональное отбеливание осветляет эмаль.",
                commercial_intent="none",
                service_id="professional_whitening",
            )
        ),
        q="Хочу отбелить зубы",
        sid="demo-commerce-whitening",
    )
    whitening_answer = str(whitening.get("answer") or "")
    assert WHITENING_TEXT in whitening_answer
    assert TAX_TEXT in whitening_answer
    assert FIXED_PRICE_TEXT in whitening_answer
    assert INSTALLMENT_TEXT not in whitening_answer

    extraction = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "Удаление зуба выполняем под анестезией.",
                commercial_intent="none",
                service_id="tooth_extraction",
            )
        ),
        q="Нужно удалить зуб",
        sid="demo-commerce-extraction",
    )
    extraction_answer = str(extraction.get("answer") or "")
    assert CONSULT_TEXT not in extraction_answer
    assert SAME_DAY_TEXT not in extraction_answer
    assert WHITENING_TEXT not in extraction_answer
    assert TAX_TEXT in extraction_answer
    assert FIXED_PRICE_TEXT in extraction_answer


def test_widget_direct_installment_promo_and_warranty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installment = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "Да, рассрочка доступна.",
                references={"direct_fact_ids": ["installment_12"]},
            )
        ),
        q="Можно ли в рассрочку?",
        sid="demo-commerce-direct-installment",
    )
    assert INSTALLMENT_TEXT in str(installment.get("answer") or "")

    promo = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "Расскажу об актуальных акциях клиники.",
                commercial_intent="promotion",
                promotion_scope="general",
                service_id=None,
            )
        ),
        q="Какие акции у вас есть?",
        sid="demo-commerce-direct-promo",
    )
    promo_answer = str(promo.get("answer") or "")
    assert SAME_DAY_TEXT in promo_answer
    assert WHITENING_TEXT in promo_answer
    assert CONSULT_TEXT in promo_answer

    warranty = _orchestrate_ask(
        monkeypatch,
        backend=_CountingBackend(
            answer_envelope(
                "По имплантации действует гарантия.",
                service_id="all_on_4",
                references={"direct_fact_ids": ["implant_warranty"]},
            )
        ),
        q="Какая гарантия на имплантацию?",
        sid="demo-commerce-direct-warranty",
    )
    assert WARRANTY_TEXT in str(warranty.get("answer") or "")


def test_widget_session_repeat_and_service_switch(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "demo-commerce-session-repeat"
    bind_session_client("demo")
    mem_reset(sid)
    payload1, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 — 368 000 ₽.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
        ),
        flask_app=flask_app,
    )
    answer1 = str(payload1.get("answer") or "")
    assert CONSULT_TEXT in answer1
    assert INSTALLMENT_TEXT in answer1

    payload2, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="Расскажите ещё раз про All-on-4",
        envelope_json=answer_envelope(
            "All-on-4 — протокол на четырёх имплантах.",
            commercial_intent="none",
            service_id="all_on_4",
            extent="full_arch",
        ),
        flask_app=flask_app,
    )
    answer2 = str(payload2.get("answer") or "")
    assert CONSULT_TEXT not in answer2
    assert INSTALLMENT_TEXT not in answer2
    assert SV_3D_TEXT in answer2

    payload3, _ = _run_widget_turn_keep_session(
        monkeypatch,
        client_id="demo",
        sid=sid,
        user_message="А что с коронками из циркония?",
        envelope_json=answer_envelope(
            "Циркониевые коронки прочные и эстетичные.",
            commercial_intent="none",
            service_id="zirconia_crowns",
        ),
        flask_app=flask_app,
    )
    answer3 = str(payload3.get("answer") or "")
    assert CONSULT_TEXT not in answer3
    session = read_target_runtime_session(sid)
    assert "implant_same_day_discount" in session.shown_fact_ids
    assert "free_implant_consult" in session.shown_fact_ids
