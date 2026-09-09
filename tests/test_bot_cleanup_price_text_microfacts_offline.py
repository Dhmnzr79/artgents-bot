"""Offline tests for BOT-CLEANUP-PRICE-TEXT-MICROFACTS-1."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import config
import pytest

import app as app_module
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_price_microfacts import (
    microfact_explained_in_patient_text,
    microfact_ids_explained_in_patient_text,
    resolve_price_microfacts,
)
from core.one_call_price_text import (
    code_owned_amounts_for_offers,
    strip_code_owned_price_claims_from_prose,
)
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.target_client_data import load_target_client_data
from core.target_runtime_session import read_target_runtime_session
from evals.v5.run_bot_cleanup_live import restore_session_snapshot
from session import bind_session_client, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
_LIVE_ARTIFACT = (
    _REPO
    / "evals/v5/artifacts/bot_cleanup_live_1/bot_cleanup_live_1_2026-09-04-live-01"
)

_LIVE_ARTIFACT_AVAILABLE = _LIVE_ARTIFACT.is_dir()
_SKIP_LIVE_ARTIFACT = pytest.mark.skipif(
    not _LIVE_ARTIFACT_AVAILABLE,
    reason="requires local LIVE artifact tree (not committed to git)",
)
_TARGET_ROOT = _REPO / "clients/demo/target_response"
_DEMO_BUNDLE = load_target_client_data("demo").bundle
_REPO_DEMO_DB = _REPO / "data" / "demo" / "bot.db"


def _clear_session_connection_cache() -> None:
    import session as session_module

    with session_module._lock:
        for conn in list(session_module._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_module._conns.clear()


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    patch_runtime = patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    patch_session = patch("session.sqlite_path_for_client", _sqlite_path)
    patch_runtime.start()
    patch_session.start()
    bind_session_client("demo")
    try:
        yield {"db_path": sessions_dir / "demo.db"}
    finally:
        patch_session.stop()
        patch_runtime.stop()
        _clear_session_connection_cache()


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        return self.output


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


def _load_provider_envelope(turn_id: str) -> str:
    raw_turn = json.loads((_LIVE_ARTIFACT / "raw_turns" / f"{turn_id}.json").read_text(encoding="utf-8"))
    attempt_index = int(raw_turn["turn"]["provider_attempt"]["attempt_index"])
    provider_raw = json.loads(
        (_LIVE_ARTIFACT / "provider_raw" / f"{turn_id}_attempt_{attempt_index}.json").read_text(
            encoding="utf-8"
        )
    )
    return str(provider_raw["provider_snapshot"]["choices"][0]["message"]["content"])


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
) -> dict:
    backend = _Backend(envelope_json)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )
    if reset_session:
        mem_reset(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": "demo"},
    ):
        from flask import request

        from core.sales_fast_widget_runtime import run_sales_fast_widget_turn

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id="demo",
            sid=sid,
            user_message=user_message,
            backend=backend,
        )
    payload = dict(outcome.widget.payload or {})
    payload["_backend_calls"] = backend.call_count
    return payload


@pytest.fixture
def flask_app():
    return app_module.app


def test_strip_removes_pure_price_sentence_keeps_md_detail() -> None:
    prose = (
        "Стоимость компьютерной томографии (КТ) — 3000 рублей за одно исследование. "
        "Это точный 3D-снимок, который необходим для планирования имплантации."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({3000}))
    assert "3000" not in _norm_digits(cleaned)
    assert "3D-снимок" in cleaned
    assert "планирования имплантации" in cleaned


def test_strip_keeps_package_description_after_offer_amount() -> None:
    prose = (
        "Стоимость имплантации All-on-4 на системе Implantium составляет 318 000 рублей за одну челюсть. "
        "В эту сумму входят 4 импланта, хирургический этап и постоянный протез после приживления."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({318000}))
    assert "318000" not in _norm_digits(cleaned)
    assert "В эту сумму входят 4 импланта" in cleaned


def test_strip_keeps_installment_clause_in_same_sentence_as_price() -> None:
    prose = (
        "Стоимость составляет 318 000 рублей, рассрочка оформляется "
        "на консультации после согласования плана лечения."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({318000}))
    assert "318000" not in _norm_digits(cleaned)
    assert "рассрочка оформляется на консультации" in cleaned.casefold()
    assert "стоимость составляет" not in cleaned.casefold()


def test_strip_keeps_package_clause_without_vhodit_phrase() -> None:
    prose = (
        "Цена All-on-4 на Implantium — 318 000 рублей, в пакет входят 4 импланта и постоянный протез."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({318000}))
    assert "318000" not in _norm_digits(cleaned)
    assert "в пакет входят 4 импланта" in cleaned.casefold()


def test_strip_preserves_list_commas_in_package_clause() -> None:
    prose = (
        "Стоимость 318 000 рублей, в эту сумму входят импланты, анестезия, временный протез."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({318000}))
    assert "318000" not in _norm_digits(cleaned)
    assert cleaned == "в эту сумму входят импланты, анестезия, временный протез."


def test_strip_keeps_installment_after_stage_amount_in_same_sentence() -> None:
    prose = (
        "Первый этап стоит 45 200 рублей, рассрочка оформляется "
        "на консультации после согласования плана лечения."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({45200}))
    assert "45200" not in _norm_digits(cleaned)
    assert cleaned == (
        "рассрочка оформляется на консультации после согласования плана лечения."
    )


def test_strip_removes_pure_stage_price_sentence() -> None:
    prose = "Оплата проходит в два этапа: сначала хирургическая часть (45 200 руб.)."
    cleaned = strip_code_owned_price_claims_from_prose(
        prose,
        forbidden_amounts=frozenset({45200}),
    )
    assert cleaned == ""


def test_price_turn_stage_amount_with_installment_explanation(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    installment_explanation = (
        "рассрочка оформляется на консультации после согласования плана лечения."
    )
    prose = f"Первый этап стоит 45 200 рублей.\n\n{installment_explanation.capitalize()}"
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="stage-plus-installment",
        user_message="Сколько стоит имплантация на Implantium и как оформить рассрочку?",
        envelope_json=dumps_production_envelope(
            patient_text=prose,
            commercial_intent="price",
            scenario="cost",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
            references={"direct_fact_ids": ["payment_stages", "installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert digits.count("76200") == 1
    assert digits.count("45200") == 0
    assert installment_explanation in answer.casefold()
    assert "первый этап стоит" not in answer.casefold()


def test_price_turn_package_list_punctuation_preserved(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    package_clause = "в пакет включены импланты, анестезия, временный протез"
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="package-list-punctuation",
        user_message="Сколько стоит All-on-4 на Implantium и что входит?",
        envelope_json=dumps_production_envelope(
            patient_text=f"В пакет включены импланты, анестезия, временный протез.",
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert _norm_digits(answer).count("318000") == 1
    assert package_clause in answer.casefold()


def test_microfact_discount_not_suppressed_by_unrelated_percent_and_days() -> None:
    fact = _DEMO_BUNDLE.facts["implant_same_day_discount"]
    prose = "Скидка составляет 5%, предложение действует 15 дней."
    assert not microfact_explained_in_patient_text(prose, fact, fact_id="implant_same_day_discount")


def test_microfact_installment_not_suppressed_by_unrelated_twelve() -> None:
    fact = _DEMO_BUNDLE.facts["installment_12"]
    prose = "Лечение занимает 12 дней, затем контрольный осмотр."
    assert not microfact_explained_in_patient_text(prose, fact, fact_id="installment_12")


def test_price_turn_preserves_detailed_discount_explanation(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    discount_explanation = (
        "При оплате в день обращения на имплантацию действует скидка до 15 %."
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="price-plus-discount",
        user_message="Сколько стоит All-on-4 на Implantium и какая скидка в день обращения?",
        envelope_json=dumps_production_envelope(
            patient_text=discount_explanation,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
            references={"direct_fact_ids": ["implant_same_day_discount"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert discount_explanation in answer
    assert answer.count("Скидка до 15%") == 0


def test_price_turn_same_sentence_installment_kept(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    prose = (
        "Стоимость составляет 318 000 рублей.\n\n"
        "Рассрочка оформляется на консультации после согласования плана лечения."
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="price-installment-same-sentence",
        user_message="Сколько стоит All-on-4 на Implantium и как оформить рассрочку?",
        envelope_json=dumps_production_envelope(
            patient_text=prose,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert _norm_digits(answer).count("318000") == 1
    assert "рассрочка оформляется на консультации" in answer.casefold()
    assert "стоимость составляет" not in answer.casefold()


def test_ct_turn_rejects_foreign_amount(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="ct-foreign-amount",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ стоит 999999 ₽. Это точный 3D-снимок для планирования.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert digits.count("3000") == 1
    assert "999999" not in digits
    assert "3D-снимок" not in answer


def test_strip_preserves_informational_numbers() -> None:
    prose = (
        "Врач работает 18 лет. Гарантия на имплант — 1 год по договору. "
        "Стоимость классической имплантации составляет 76 200 рублей."
    )
    cleaned = strip_code_owned_price_claims_from_prose(prose, forbidden_amounts=frozenset({76200}))
    assert "18 лет" in cleaned
    assert "1 год" in cleaned
    assert "76200" not in _norm_digits(cleaned)


def test_microfact_installment_anchor_detects_detailed_prose() -> None:
    fact = _DEMO_BUNDLE.facts["installment_12"]
    prose = "На имплантацию можно оформить рассрочку до 12 месяцев на консультации."
    assert microfact_explained_in_patient_text(prose, fact, fact_id="installment_12")
    assert "installment_12" in microfact_ids_explained_in_patient_text(
        prose,
        _DEMO_BUNDLE,
        candidate_fact_ids=("installment_12", "implant_same_day_discount"),
    )


def test_microfact_not_excluded_by_direct_fact_id_without_prose() -> None:
    microfacts = resolve_price_microfacts(
        bundle=_DEMO_BUNDLE,
        target_root=_TARGET_ROOT,
        service_id="all_on_4",
        offer_ids=("all_on_4.jaw.implantium",),
        authoritative_service_id="all_on_4",
        today=date(2026, 8, 10),
        exclude_fact_ids=microfact_ids_explained_in_patient_text(
            "Стоимость All-on-4 на Implantium — популярный вариант.",
            _DEMO_BUNDLE,
            candidate_fact_ids=("installment_12", "implant_same_day_discount"),
        ),
    )
    assert [item.fact_id for item in microfacts] == [
        "installment_12",
        "implant_same_day_discount",
    ]


@_SKIP_LIVE_ARTIFACT
def test_live_replay_prc_01_ct_single_code_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="prc-01-replay",
        user_message="Сколько стоит КТ?",
        envelope_json=_load_provider_envelope("PRC-01-T1"),
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert digits.count("3000") == 1
    assert "3D-снимок" not in answer


@_SKIP_LIVE_ARTIFACT
def test_live_replay_prc_02_implantium_keeps_package_not_duplicate_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    restore_session_snapshot(
        json.loads(
            (_LIVE_ARTIFACT / "session_snapshots/PRC-02-T1.json").read_text(encoding="utf-8")
        )
    )
    sid = "prc-02-replay"
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит восстановить один зуб на Implantium?",
        envelope_json=_load_provider_envelope("PRC-02-T1"),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert "76200" in digits
    assert "составляет761200" not in digits
    assert "в эту сумму входит" not in answer.casefold()
    assert "45200" not in digits
    assert "31000" not in digits


@_SKIP_LIVE_ARTIFACT
def test_live_replay_prc_03_pure_price_without_auto_microfacts(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="prc-03-replay",
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=_load_provider_envelope("PRC-03-T1"),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert _norm_digits(answer).count("318000") == 1
    assert "Скидка до 15%" not in answer
    assert "Рассрочка до 12 месяцев" in answer
    assert answer.count("Рассрочка до 12 месяцев") == 1
    assert "В эту сумму входят 4 импланта" not in answer


def test_mixed_price_installment_prose_without_duplicate_microfact(
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
    patient = f"All-on-4 на Implantium — популярный вариант. {installment_explanation}"
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="mixed-installment",
        user_message="Сколько стоит All-on-4 Implantium и как оформляется рассрочка?",
        envelope_json=dumps_production_envelope(
            patient_text=patient,
            commercial_intent="price",
            scenario="cost",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            price_text=None,
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert answer.count("Рассрочка до 12 месяцев, оформление на консультации.") == 1


def test_direct_promo_answer_preserves_percentage_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    promo_sentence = (
        "При оплате в день обращения на имплантацию действует скидка до 15 %."
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="direct-promo",
        user_message="Какая скидка при оплате в день обращения на All-on-4?",
        envelope_json=dumps_production_envelope(
            patient_text=promo_sentence,
            commercial_intent="promotion",
            promotion_scope="service",
            service_id="all_on_4",
            references={"direct_fact_ids": ["implant_same_day_discount"]},
        ),
    )
    answer = str(payload.get("answer") or "")
    assert promo_sentence in answer
    assert "15 %" in answer or "15%" in answer


def test_payment_stages_code_block_without_prose_duplicate(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = "payment-stages"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит имплантация на Implantium?",
        envelope_json=dumps_production_envelope(
            patient_text="Имплантация на Implantium.",
            commercial_intent="price",
            scenario="cost",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Как оплачивается по этапам?",
        envelope_json=dumps_production_envelope(
            patient_text="Оплата по этапам возможна.",
            commercial_intent="payment_stages",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
            price_text=None,
        ),
        reset_session=False,
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert digits.count("45200") == 1
    assert digits.count("31000") == 1
    assert "Хирургический этап" in answer


def test_from_price_mode_preserved(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="from-price",
        user_message="Сколько стоит отбеливание?",
        envelope_json=answer_envelope(
            "Отбеливание зубов — популярная процедура. Стоимость от 18 000 рублей.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "от" in answer.casefold()
    assert "18000" in _norm_digits(answer)
    assert "стоимостьот18000" not in _norm_digits(answer).casefold()


def test_informational_answer_keeps_years_and_warranty(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="info-numbers",
        user_message="Какой стаж у врача Орлова?",
        envelope_json=answer_envelope(
            "Врач Орлов работает 18 лет. Гарантия на имплант — 1 год по договору.",
            commercial_intent="none",
            service_id=None,
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "18 лет" in answer
    assert "1 год" in answer


def test_rendered_microfact_ids_not_auto_added_on_pure_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="microfact-memory",
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium — надёжное решение при полной адентии.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
            references={
                "direct_fact_ids": [
                    "installment_12",
                    "implant_same_day_discount",
                ]
            },
        ),
    )
    answer = str(payload.get("answer") or "")
    discount = str(_DEMO_BUNDLE.facts["implant_same_day_discount"].microfact_text)
    installment = str(_DEMO_BUNDLE.facts["installment_12"].microfact_text)
    assert discount not in answer
    assert installment in answer
    session = read_target_runtime_session("microfact-memory")
    shown = tuple(session.shown_fact_ids or ())
    assert "implant_same_day_discount" not in shown
    assert "installment_12" in shown


def test_code_owned_amounts_include_all_displayed_offers() -> None:
    offers = tuple(
        offer
        for offer in _DEMO_BUNDLE.offers
        if offer.service_id == "classic" and offer.price.mode in {"fixed", "from"}
    )[:3]
    amounts = code_owned_amounts_for_offers(offers)
    assert 76200 in amounts
    assert 85200 in amounts
    assert 101200 in amounts
