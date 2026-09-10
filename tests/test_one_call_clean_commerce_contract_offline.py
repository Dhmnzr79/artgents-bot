"""Clean One Call commerce contract — code-owned price/payment/installment boundaries."""

from __future__ import annotations

import inspect
import re
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

import app as app_module
import core.one_call_presentation_pass as presentation_pass_module
from core.one_call_installment_auto_policy import (
    INSTALLMENT_12_FACT_ID,
    INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT,
    installment_microfact_text,
    resolve_shared_installment_suffix_for_price_turn,
)
from core.sales_fast_authoritative_commerce import PAYMENT_STAGES_UNAVAILABLE_TEXT
from core.sales_fast_presentation import AUTOMATIC_AMPLIFIER_LIST_HEADER
from core.target_client_data import load_target_client_data
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from tests.session_binding_test_support import read_target_runtime_session_for
from session import mem_reset
from tests.target_runtime_test_support import _seed_followups
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import answer_envelope

_DEMO_BUNDLE = load_target_client_data("demo").bundle
_INSTALLMENT_MICROFACT = installment_microfact_text(_DEMO_BUNDLE)
_ALL_ON_STAGE_AMOUNTS = (190800, 127200, 318000)
_FALSE_STAGE_AMOUNTS = (99999, 88888)
_UNAUTHORIZED_PROMO_PHRASE = "скидка 99% по промокоду FAKE_PROMO_XYZ"


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    patch_runtime = patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    patch_session = patch("session.sqlite_path_for_client", _sqlite_path)
    patch_runtime.start()
    patch_session.start()
    from session import bind_session_client

    bind_session_client("demo")
    try:
        yield
    finally:
        patch_session.stop()
        patch_runtime.stop()


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _offer(offer_id: str):
    return next(item for item in _DEMO_BUNDLE.offers if item.offer_id == offer_id)


def _post_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
) -> tuple[dict, _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref is not None:
        payload["ref"] = ref
    resp = app_module.app.test_client().post("/ask", json=payload)
    assert resp.status_code == 200
    return resp.get_json(), backend


def test_model_cannot_replace_code_owned_all_on_4_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-clean-price-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 стоит 1 рубль.",
            service_id="all_on_4",
            commercial_intent="price",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert "1" not in digits or "318000" in digits
    assert "318000" in digits
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


def test_wrong_service_price_is_not_applied_to_caries_question(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-clean-caries-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "All-on-4 стоит 318 000 рублей.",
            service_id="caries",
            commercial_intent="price",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    assert backend.call_count == 1
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "6500" in digits
    assert "318000" not in digits


def test_multi_offer_ambiguity_shows_multiple_brands_not_random_single_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-clean-ambiguity-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium 318 000, на Nobel 428 000.",
            service_id="all_on_4",
            commercial_intent="price",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert "318000" in digits
    assert "428000" in digits
    assert "implantium" in answer.lower() or "nobel" in answer.lower()


def test_payment_stages_ref_returns_exact_authored_amounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_ref = "price:all_on_4/stages"
    sid = f"s-clean-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=payment_ref, label="Оплата по этапам"),
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=payment_ref,
        envelope_json=answer_envelope(
            "Оплата по этапам возможна.",
            commercial_intent="payment_stages",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert digits.count("190800") >= 1
    assert digits.count("127200") >= 1
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


def test_model_cannot_replace_authored_payment_stage_amounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_ref = "price:all_on_4/stages"
    sid = f"s-clean-false-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=payment_ref, label="Оплата по этапам"),
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=payment_ref,
        envelope_json=answer_envelope(
            "Первый этап 99 999 рублей, второй 88 888 рублей.",
            commercial_intent="payment_stages",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    digits = _norm_digits(str(payload.get("answer") or ""))
    for false_amount in _FALSE_STAGE_AMOUNTS:
        assert str(false_amount) not in digits
    assert "190800" in digits
    assert "127200" in digits


def test_service_without_payment_stages_uses_canonical_unavailable_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment_ref = "price:tomography/stages"
    sid = f"s-clean-no-stages-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=payment_ref, label="Этапы"))
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="",
        ref=payment_ref,
        envelope_json=answer_envelope(
            "Да, оплата по этапам 190 800 и 127 200 рублей.",
            commercial_intent="payment",
            service_id="tomography",
            service_reference_status="resolved",
            requested_service_id="tomography",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert PAYMENT_STAGES_UNAVAILABLE_TEXT in answer
    digits = _norm_digits(answer)
    for amount in _ALL_ON_STAGE_AMOUNTS:
        assert str(amount) not in digits


def test_payment_intent_after_non_stage_service_does_not_materialize_all_on_4_amounts(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    sid = f"s-clean-payment-intent-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Есть рассрочка?",
        envelope_json=answer_envelope(
            "Доступна рассрочка.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    assert backend.call_count == 1
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "190800" not in digits
    assert "127200" not in digits


def test_eligible_all_on_4_price_appends_installment_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"s-clean-inst-eligible-{uuid.uuid4().hex[:8]}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert "318000" in _norm_digits(answer)
    assert _INSTALLMENT_MICROFACT in answer
    assert answer.count(_INSTALLMENT_MICROFACT) == 1
    assert INSTALLMENT_12_FACT_ID in read_target_runtime_session_for(sid).shown_fact_ids


def test_ineligible_caries_price_has_no_installment_suffix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-clean-inst-ineligible-{uuid.uuid4().hex[:8]}"
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Рассрочка доступна на любую услугу.",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert "6500" in _norm_digits(answer)
    assert _INSTALLMENT_MICROFACT not in answer
    assert "рассрочка доступна на любую услугу" not in answer.lower()


def test_contextual_installment_follow_up_after_eligible_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"s-clean-inst-follow-eligible-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="А рассрочка есть?",
        envelope_json=answer_envelope(
            "Да, рассрочка доступна.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert "до 12 месяцев" in answer or _INSTALLMENT_MICROFACT.lower() in answer
    assert "рассрочка" in answer


def test_contextual_installment_follow_up_after_ineligible_price_uses_neutral_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-clean-inst-follow-ineligible-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _post_ask(
        monkeypatch,
        sid=sid,
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Лечение кариеса.",
            commercial_intent="price",
            service_id="caries",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
    )
    payload, backend = _post_ask(
        monkeypatch,
        sid=sid,
        user_message="А рассрочка есть?",
        envelope_json=answer_envelope(
            "Да, рассрочка точно доступна.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert (
        INSTALLMENT_UNAVAILABLE_NEUTRAL_TEXT.lower() in answer
        or "не предоставляется" in answer
        or "не указана" in answer
    )
    assert "рассрочка точно доступна" not in answer


def test_mixed_multi_offer_has_no_shared_installment_suffix() -> None:
    implantium = _offer("all_on_4.jaw.implantium")
    nobel = _offer("all_on_4.jaw.nobel")
    impro_without = _offer("all_on_4.jaw.impro").model_copy(
        update={
            "fact_refs": tuple(
                ref
                for ref in _offer("all_on_4.jaw.impro").fact_refs
                if ref != INSTALLMENT_12_FACT_ID
            )
        }
    )
    today = date(2026, 8, 10)
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, nobel),
        today=today,
    ) == installment_microfact_text(_DEMO_BUNDLE)
    assert resolve_shared_installment_suffix_for_price_turn(
        bundle=_DEMO_BUNDLE,
        displayed_offers=(implantium, impro_without, nobel),
        today=today,
    ) is None


def test_promo_fact_refs_alone_do_not_materialize_marketing_block_or_answer_promo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-clean-promo-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            f"All-on-4 от 318 000 рублей. {_UNAUTHORIZED_PROMO_PHRASE}",
            service_id="all_on_4",
            commercial_intent="price",
            direct_fact_ids=("promo_spring_2026",),
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "").lower()
    assert payload.get("promo") is None
    assert payload.get("marketing") is None
    assert "fake_promo_xyz" not in answer
    assert "99%" not in answer


def test_plain_price_question_does_not_activate_automatic_marketing_flow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-clean-no-marketing-{uuid.uuid4().hex[:8]}",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    assert backend.call_count == 1
    answer = str(payload.get("answer") or "")
    assert AUTOMATIC_AMPLIFIER_LIST_HEADER not in answer
    assert payload.get("marketing") is None


def test_universal_commercial_renderer_is_not_in_active_presentation_pass() -> None:
    source = inspect.getsource(presentation_pass_module.build_one_call_presentation_result)
    assert "render_offer_commercial_blocks" not in source
