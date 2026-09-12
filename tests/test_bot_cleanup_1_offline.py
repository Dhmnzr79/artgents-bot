"""BOT-CLEANUP-1 offline acceptance: restored payment MD and cleanup contract."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

import app as app_module
import config
from core.one_call_client_pack_identity import compute_client_pack_hash
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_price_microfacts import resolve_price_microfacts
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.response_schema_loader import load_response_schema_bundle
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.service_consultation_source import build_service_consultation_values
from core.target_client_data import load_target_client_data
from session import mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_DEMO_ROOT = Path("clients/demo")
_MD_ROOT = _DEMO_ROOT / "md"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_FACTS_PATH = _TARGET_ROOT / "pricebook" / "facts.json"
_MICROFACTS_PATH = _TARGET_ROOT / "price_microfacts.yaml"
_PAYMENT_TERMS_DOC = _MD_ROOT / "clinic__info__payment_terms.md"
_DEMO_BUNDLE = load_target_client_data("demo").bundle


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output
        self.call_count = 0
        self.invocations: list[object] = []

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocations.append(invocation)
        return self.output


class _SequenceBackend:
    def __init__(self, outputs: list[str]) -> None:
        self.outputs = outputs
        self.call_count = 0
        self.invocations: list[object] = []

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocations.append(invocation)
        return self.outputs[self.call_count - 1]


def _bundle_without_discount_on_impro():
    offers = []
    for offer in _DEMO_BUNDLE.offers:
        if offer.offer_id == "all_on_4.jaw.impro":
            refs = tuple(
                ref
                for ref in (offer.fact_refs or ())
                if ref != "implant_same_day_discount"
            )
            offer = offer.model_copy(update={"fact_refs": refs})
        offers.append(offer)
    return _DEMO_BUNDLE.model_copy(update={"offers": tuple(offers)})


def _bundle_sinus_open_only_discount():
    offers = []
    for offer in _DEMO_BUNDLE.offers:
        if offer.offer_id == "sinus_lift.one_site.closed":
            refs = tuple(
                ref
                for ref in (offer.fact_refs or ())
                if ref != "implant_same_day_discount"
            )
            offer = offer.model_copy(update={"fact_refs": refs})
        offers.append(offer)
    return _DEMO_BUNDLE.model_copy(update={"offers": tuple(offers)})


def _sinus_lift_demo_offers(bundle=_DEMO_BUNDLE):
    return tuple(
        offer
        for offer in bundle.offers
        if offer.offer_id in {"sinus_lift.one_site.closed", "sinus_lift.one_site.open"}
    )


def _patch_demo_bundle(monkeypatch: pytest.MonkeyPatch, bundle) -> None:
    from dataclasses import replace

    from core.target_runtime_client_context import load_target_runtime_client_context

    ctx = replace(load_target_runtime_client_context("demo"), bundle=bundle)

    def _loader(_client_id: str):
        return ctx

    monkeypatch.setattr(
        "core.sales_fast_widget_runtime.load_target_runtime_client_context",
        _loader,
    )
    monkeypatch.setattr(
        "core.target_runtime_client_context.load_target_runtime_client_context",
        _loader,
    )


def _run_widget(monkeypatch: pytest.MonkeyPatch, flask_app, *, sid: str, message: str, backend: _Backend):
    mem_reset(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": message, "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": f"rid-{sid}"}
        return run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=message,
            backend=backend,
        )


@pytest.fixture
def flask_app():
    return app_module.app


def test_payment_terms_document_restored() -> None:
    assert _PAYMENT_TERMS_DOC.is_file()
    text = _PAYMENT_TERMS_DOC.read_text(encoding="utf-8").lower()
    assert "рассрочк" in text
    assert "оплата по этапам" in text
    assert "налогов" in text


def test_facts_have_payment_and_promo_detail_refs() -> None:
    facts = json.loads(_FACTS_PATH.read_text(encoding="utf-8"))
    assert facts["installment_12"]["detail_ref"] == "clinic__info__payment_terms.md#rassrochka"
    assert facts["payment_stages"]["detail_ref"] == "clinic__info__payment_terms.md#oplata-po-etapam"
    assert (
        facts["implant_same_day_discount"]["detail_ref"]
        == "clinic__info__promo__implant_same_day_discount.md#korotko"
    )
    assert facts["free_implant_consult"]["detail_ref"].startswith("clinic__info__promo__")


def test_consultation_value_removed_from_implantation_service_md() -> None:
    for name in (
        "implantation__service__all_on_4.md",
        "implantation__service__classic.md",
        "implantation__service__one_stage.md",
    ):
        raw = (_MD_ROOT / name).read_text(encoding="utf-8")
        assert "consultation_value:" not in raw


def test_consultation_values_no_longer_loaded_from_demo_services() -> None:
    values = build_service_consultation_values(_MD_ROOT)
    assert values == ()


def test_price_microfacts_assignments_exist_for_top_services() -> None:
    raw = yaml.safe_load(_MICROFACTS_PATH.read_text(encoding="utf-8"))
    services = raw["services"]
    assert services["all_on_4"][:2] == ["installment_12", "implant_same_day_discount"]
    assert services["professional_whitening"] == ["professional_whitening_discount"]


def test_prompt_contract_version_bumped_for_cleanup() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 13


def test_facts_bundle_loads_microfact_text_field() -> None:
    bundle = load_response_schema_bundle(_TARGET_ROOT)
    assert bundle.facts["installment_12"].microfact_text is not None


def test_resolve_price_microfacts_for_all_on_4_offer() -> None:
    microfacts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="all_on_4",
        offer_ids=("all_on_4.jaw.implantium",),
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
    )
    assert [item.fact_id for item in microfacts] == [
        "installment_12",
        "implant_same_day_discount",
    ]


def test_mixed_price_payment_excludes_requested_installment_microfact() -> None:
    microfacts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="all_on_4",
        offer_ids=("all_on_4.jaw.implantium",),
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
        exclude_fact_ids=frozenset({"installment_12"}),
    )
    assert [item.fact_id for item in microfacts] == ["implant_same_day_discount"]


def test_widget_price_turn_has_code_price_and_microfacts_without_marketing_blocks(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    installment_explanation = (
        "На имплантацию и протезирование можно оформить рассрочку до 12 месяцев. "
        "Оформление — на консультации после согласования плана лечения."
    )
    patient = (
        "All-on-4 на Implantium — популярный вариант. "
        f"{installment_explanation}"
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text=patient,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-price-microfacts",
        message="Сколько стоит All-on-4 Implantium и как оформляется рассрочка?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert "318000" in answer.replace("\u00a0", "").replace(" ", "")
    assert "на Implantium" in answer
    assert installment_explanation in answer
    assert "Скидка до 15%" not in answer
    assert "бесплатная консультация" not in answer.casefold()


def test_direct_promo_answer_preserves_model_percentage_text(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    promo_sentence = (
        "При оплате в день обращения на имплантацию действует скидка до 15 %."
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text=promo_sentence,
            commercial_intent="promotion",
            promotion_scope="service",
            service_id="all_on_4",
            references={"direct_fact_ids": ["implant_same_day_discount"]},
        )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-direct-promo",
        message="Какая скидка при оплате в день обращения на All-on-4?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert promo_sentence in answer
    assert "15 %" in answer or "15%" in answer


def test_cleaned_path_does_not_call_marketing_sanitizer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    def _forbidden_sanitize(*_args, **_kwargs):
        raise AssertionError("sanitize_model_text_for_authoritative_marketing must stay off")

    monkeypatch.setattr(
        "core.sales_fast_authoritative_commerce.sanitize_model_text_for_authoritative_marketing",
        _forbidden_sanitize,
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text="При оплате в день обращения действует скидка до 15 %.",
            commercial_intent="promotion",
            promotion_scope="service",
            service_id="all_on_4",
            references={"direct_fact_ids": ["implant_same_day_discount"]},
        )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-no-sanitize",
        message="Какая скидка на All-on-4?",
        backend=backend,
    )
    assert "15" in str(outcome.widget.payload.get("answer") or "")


def test_payment_stages_direct_question_appends_code_amounts(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text="Оплата делится на этапы лечения.",
            commercial_intent="payment_stages",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
                    )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-payment-stages",
        message="Сколько стоит All-on-4 Implantium по этапам?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert "190800" in answer.replace("\u00a0", "").replace(" ", "")
    assert "127200" in answer.replace("\u00a0", "").replace(" ", "")
    assert "220800" not in answer.replace("\u00a0", "").replace(" ", "")


def test_payment_stages_multi_offer_shows_labeled_blocks(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text="Оплата по этапам зависит от выбранного варианта.",
            commercial_intent="payment_stages",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
                    )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-payment-stages-multi",
        message="Сколько стоит All-on-4 по этапам?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    normalized = answer.replace("\u00a0", "").replace(" ", "")
    assert "Implantium:" in answer
    assert "Impro:" in answer
    assert "190800" in normalized
    assert "220800" in normalized


def test_partial_microfact_overview_block_shown_only_on_matching_offer() -> None:
    from core.one_call_price_microfacts import apply_microfacts_to_price_block, resolve_price_microfacts
    from core.sales_fast_authoritative_commerce import _build_overview_lines

    bundle = _bundle_without_discount_on_impro()
    offers = tuple(
        offer
        for offer in bundle.offers
        if offer.offer_id in {"all_on_4.jaw.implantium", "all_on_4.jaw.impro"}
    )
    overview = _build_overview_lines(offers, bundle=bundle, featured_offer_id=None)
    microfacts = resolve_price_microfacts(
        bundle=bundle,
        target_root=_TARGET_ROOT,
        service_id="all_on_4",
        displayed_offers=offers,
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
    )
    enriched, rendered = apply_microfacts_to_price_block(
        overview,
        bundle=bundle,
        displayed_offers=offers,
        microfacts=microfacts,
    )
    discount = str(bundle.facts["implant_same_day_discount"].microfact_text)
    installment = str(bundle.facts["installment_12"].microfact_text)
    assert discount in enriched
    assert installment in enriched
    implantium_idx = enriched.index("Implantium")
    impro_idx = enriched.index("Impro")
    discount_idx = enriched.index(discount)
    assert implantium_idx < discount_idx
    assert discount_idx < impro_idx
    assert [item.fact_id for item in rendered] == [
        "installment_12",
        "implant_same_day_discount",
    ]


def test_sinus_lift_overview_option_labels_and_partial_microfact() -> None:
    from core.one_call_price_microfacts import apply_microfacts_to_price_block, resolve_price_microfacts
    from core.sales_fast_authoritative_commerce import _build_overview_lines

    bundle = _bundle_sinus_open_only_discount()
    offers = _sinus_lift_demo_offers(bundle)
    overview = _build_overview_lines(offers, bundle=bundle, featured_offer_id=None)
    assert "Закрытый синус-лифтинг" in overview
    assert "Открытый синус-лифтинг" in overview
    normalized = overview.replace("\u00a0", "").replace(" ", "")
    assert "42000" in normalized
    assert "68000" in normalized
    assert "от" in normalized.casefold()
    assert overview.count("—") == 2
    assert "-  —" not in overview

    microfacts = resolve_price_microfacts(
        bundle=bundle,
        target_root=_TARGET_ROOT,
        service_id="sinus_lift",
        displayed_offers=offers,
        authoritative_service_id="sinus_lift",
        today=date(2026, 8, 10),
    )
    enriched, rendered = apply_microfacts_to_price_block(
        overview,
        bundle=bundle,
        displayed_offers=offers,
        microfacts=microfacts,
    )
    discount = str(bundle.facts["implant_same_day_discount"].microfact_text)
    installment = str(bundle.facts["installment_12"].microfact_text)
    assert discount in enriched
    assert installment in enriched
    lines = enriched.splitlines()
    open_line = next(
        index for index, line in enumerate(lines) if line.startswith("- Открытый синус-лифтинг —")
    )
    closed_line = next(
        index for index, line in enumerate(lines) if line.startswith("- Закрытый синус-лифтинг —")
    )
    discount_line = next(index for index, line in enumerate(lines) if discount in line)
    assert lines[discount_line].startswith("  ")
    assert discount_line == open_line + 1
    assert closed_line + 1 != discount_line
    assert [item.fact_id for item in rendered] == [
        "installment_12",
        "implant_same_day_discount",
    ]

    reversed_offers = tuple(reversed(offers))
    reversed_overview = _build_overview_lines(
        reversed_offers,
        bundle=bundle,
        featured_offer_id=None,
    )
    reversed_enriched, reversed_rendered = apply_microfacts_to_price_block(
        reversed_overview,
        bundle=bundle,
        displayed_offers=reversed_offers,
        microfacts=microfacts,
    )
    assert discount in reversed_enriched
    assert [item.fact_id for item in reversed_rendered] == [
        "installment_12",
        "implant_same_day_discount",
    ]
    reversed_lines = reversed_enriched.splitlines()
    open_line_reversed = next(
        index
        for index, line in enumerate(reversed_lines)
        if line.startswith("- Открытый синус-лифтинг —")
    )
    discount_line_reversed = next(
        index for index, line in enumerate(reversed_lines) if discount in line
    )
    assert reversed_lines[discount_line_reversed].startswith("  ")
    assert discount_line_reversed == open_line_reversed + 1


def test_pure_price_does_not_auto_materialize_microfacts_or_shown_ids(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text="All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            price_text=None,
        )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-rendered-microfact-positive",
        message="Сколько стоит All-on-4 Implantium?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    discount = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].microfact_text)
    assert discount not in answer
    session = read_target_runtime_session("cleanup-rendered-microfact-positive")
    assert "implant_same_day_discount" not in session.shown_fact_ids


def test_unrendered_microfact_not_in_session_shown_ids(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    backend = _Backend(
        dumps_production_envelope(
            patient_text="All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            jaw="lower",
            price_text=None,
        )
    )
    outcome = _run_widget(
        monkeypatch,
        flask_app,
        sid="cleanup-unrendered-microfact",
        message="Сколько стоит All-on-4 Implantium?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    discount = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].microfact_text)
    installment = str(_DEMO_BUNDLE.facts["installment_12"].microfact_text)
    assert discount not in answer
    assert "Рассрочка до 12 месяцев, оформление на консультации." in answer
    session = read_target_runtime_session("cleanup-unrendered-microfact")
    assert "implant_same_day_discount" not in session.shown_fact_ids


def test_microfact_memory_followup_uses_shown_fact_context(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    from core.target_runtime_session import read_target_runtime_session

    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "cleanup-microfact-memory"
    mem_reset(sid)
    discount_microfact = str(
        _DEMO_BUNDLE.facts["implant_same_day_discount"].microfact_text
    )
    promo_answer = (
        "При оплате в день обращения на имплантацию действует скидка до 15 %. "
        "Акция распространяется на услуги имплантации, указанные в прайсе клиники."
    )
    backend = _SequenceBackend(
        [
            dumps_production_envelope(
                patient_text=promo_answer,
                commercial_intent="promotion",
                promotion_scope="service",
                service_id="all_on_4",
                references={"direct_fact_ids": ["implant_same_day_discount"]},
            ),
            dumps_production_envelope(
                patient_text=(
                    "При оплате в день обращения на имплантацию действует скидка до 15 %. "
                    "Акция распространяется на услуги имплантации, указанные в прайсе клиники."
                ),
                commercial_intent="promotion",
                promotion_scope="shown",
                service_id="all_on_4",
                references={"direct_fact_ids": ["implant_same_day_discount"]},
            ),
        ]
    )
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={
            "q": "Какая скидка при оплате в день обращения на All-on-4?",
            "sid": sid,
            "client_id": "demo",
        },
    ):
        from flask import request

        request.ctx = {"request_id": "rid-1"}
        outcome1 = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="Какая скидка при оплате в день обращения на All-on-4?",
            backend=backend,
        )
    answer1 = str(outcome1.widget.payload.get("answer") or "")
    assert promo_answer in answer1
    session1 = read_target_runtime_session(sid)
    assert "implant_same_day_discount" not in session1.shown_fact_ids

    from session import mem_add_bot, mem_add_user

    mem_add_user(sid, "Какая скидка при оплате в день обращения на All-on-4?")
    mem_add_bot(sid, answer1)
    mem_add_user(sid, "А какие у неё условия?")

    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": "А какие у неё условия?", "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        request.ctx = {"request_id": "rid-2"}
        outcome2 = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message="А какие у неё условия?",
            backend=backend,
        )
    answer2 = str(outcome2.widget.payload.get("answer") or "")
    assert backend.call_count == 2
    assert len(backend.invocations) == 2
    turn2_prompt = str(backend.invocations[1].user_prompt)
    assert "Контекст диалога" in turn2_prompt
    assert promo_answer in turn2_prompt
    assert "При оплате в день обращения" in answer2
    assert "15" in answer2


def test_client_pack_hash_includes_price_microfacts_yaml(tmp_path: Path) -> None:
    import shutil

    pack = tmp_path / "clients" / "demo"
    shutil.copytree(_DEMO_ROOT, pack)
    before = compute_client_pack_hash(pack)
    (pack / "target_response" / "price_microfacts.yaml").write_text(
        "version: 1\nservices:\n  all_on_4:\n    - installment_12\n",
        encoding="utf-8",
    )
    after = compute_client_pack_hash(pack)
    assert before != after
    unchanged = compute_client_pack_hash(pack)
    assert after == unchanged
