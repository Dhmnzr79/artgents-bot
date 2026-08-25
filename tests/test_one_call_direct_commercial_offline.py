"""Direct commercial materializer and widget-path offline tests (Checkpoint B1)."""

from __future__ import annotations

from datetime import date

import pytest

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_envelope import OneCallEnvelope
from contracts.sales_one_plus_semantic import SalesOnePlusSemanticFrame
from contracts.turn_frame import TurnFrame
from core.one_call_direct_commercial import (
    DIRECT_COMMERCIAL_INELIGIBLE_PHRASE,
    DirectCommercialMaterialization,
    append_direct_commercial_without_duplicates,
    materialize_direct_commercial,
    materialize_direct_commercial_text,
)
from core.one_call_envelope_protocol import (
    OneCallEnvelopeProtocolError,
    dumps_production_envelope,
    production_envelope_template,
)
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.sales_one_plus_turn import run_sales_one_plus_candidate, run_sales_one_plus_candidate_stream
from core.target_client_data import load_target_client_data
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from session import mem_reset
import app as app_module
import config
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_REF_CATALOG,
    _PACK_IDENTITY,
    _context,
    _resolution,
    admin_envelope,
    answer_envelope,
)

_DEMO_BUNDLE = load_target_client_data("demo").bundle
_INSTALLMENT_TEXT = _DEMO_BUNDLE.facts["installment_12"].text_fact
_TAX_TEXT = _DEMO_BUNDLE.facts["tax_deduction"].text_fact
_WHITENING_TEXT = _DEMO_BUNDLE.facts["professional_whitening_discount"].text_fact


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        on_raw_delta(str(self.output))
        return None


def _run_widget_with_backend(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    backend: _CountingBackend,
    on_delta=None,
    client_id: str = "demo",
):
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    if client_id != "demo":
        monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
        from session import bind_session_client

        bind_session_client(client_id)
    mem_reset(sid)
    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    ):
        from flask import request

        request.ctx = {"request_id": f"rid-{sid}"}
        return run_sales_fast_widget_turn(
            client_id=client_id,
            sid=sid,
            user_message=user_message,
            backend=backend,
            on_delta=on_delta,
        )


@pytest.fixture
def flask_app():
    return app_module.app


def test_active_eligible_fact_renders_exact_text_fact() -> None:
    text = materialize_direct_commercial_text(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("installment_12",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == _INSTALLMENT_TEXT


def test_multiple_eligible_facts_preserve_order() -> None:
    text = materialize_direct_commercial_text(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("installment_12", "tax_deduction"),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text.split("\n\n") == [_INSTALLMENT_TEXT, _TAX_TEXT]


def test_inactive_fact_uses_controlled_phrase() -> None:
    inactive = _DEMO_BUNDLE.model_copy(deep=True)
    fact = inactive.facts["installment_12"].model_copy(update={"active": False})
    inactive.facts["installment_12"] = fact
    text = materialize_direct_commercial_text(
        bundle=inactive,
        direct_fact_ids=("installment_12",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == DIRECT_COMMERCIAL_INELIGIBLE_PHRASE


def test_future_active_from_uses_controlled_phrase() -> None:
    bundle = _DEMO_BUNDLE.model_copy(deep=True)
    fact = bundle.facts["installment_12"].model_copy(update={"active_from": "2026-09-01"})
    bundle.facts["installment_12"] = fact
    text = materialize_direct_commercial_text(
        bundle=bundle,
        direct_fact_ids=("installment_12",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == DIRECT_COMMERCIAL_INELIGIBLE_PHRASE


def test_expired_active_until_uses_controlled_phrase() -> None:
    text = materialize_direct_commercial_text(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("professional_whitening_discount",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == DIRECT_COMMERCIAL_INELIGIBLE_PHRASE


def test_date_boundaries_are_inclusive() -> None:
    bundle = _DEMO_BUNDLE.model_copy(deep=True)
    fact = bundle.facts["installment_12"].model_copy(
        update={"active_from": "2026-08-21", "active_until": "2026-08-21"}
    )
    bundle.facts["installment_12"] = fact
    text = materialize_direct_commercial_text(
        bundle=bundle,
        direct_fact_ids=("installment_12",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == _INSTALLMENT_TEXT


def test_service_inapplicable_fact_with_active_service_uses_controlled_phrase() -> None:
    text = materialize_direct_commercial_text(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("installment_12",),
        authoritative_service_id="braces",
        today=date(2026, 8, 21),
    )
    assert text == DIRECT_COMMERCIAL_INELIGIBLE_PHRASE


def test_service_null_general_request_remains_eligible() -> None:
    text = materialize_direct_commercial_text(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("installment_12",),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text == _INSTALLMENT_TEXT


def test_partial_eligibility_renders_eligible_text_and_phrase_once() -> None:
    bundle = _DEMO_BUNDLE.model_copy(deep=True)
    inactive = bundle.facts["tax_deduction"].model_copy(update={"active": False})
    bundle.facts["tax_deduction"] = inactive
    text = materialize_direct_commercial_text(
        bundle=bundle,
        direct_fact_ids=("installment_12", "tax_deduction"),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    assert text.split("\n\n") == [_INSTALLMENT_TEXT, DIRECT_COMMERCIAL_INELIGIBLE_PHRASE]


def test_append_direct_commercial_does_not_duplicate_existing_text() -> None:
    merged = append_direct_commercial_without_duplicates(
        _INSTALLMENT_TEXT,
        _INSTALLMENT_TEXT,
    )
    assert merged == _INSTALLMENT_TEXT
    merged_two = append_direct_commercial_without_duplicates(
        "Модельный текст.",
        f"{_INSTALLMENT_TEXT}\n\n{DIRECT_COMMERCIAL_INELIGIBLE_PHRASE}",
    )
    assert _INSTALLMENT_TEXT in merged_two
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in merged_two


def test_bind_semantic_frame_preserves_ordered_direct_ids() -> None:
    envelope = OneCallEnvelope.model_validate(
        {
            **production_envelope_template(),
            "patient_text": "Условия ниже.",
            "commercial_intent": "payment",
            "references": {"direct_fact_ids": ["installment_12", "tax_deduction"]},
        }
    )
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    resolution = ExactSalesResolution(
        None,
        None,
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed_ui_authority_from_resolution(resolution),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert semantic.direct_fact_ids == ("installment_12", "tax_deduction")


def test_clarify_semantic_direct_ids_empty() -> None:
    envelope = OneCallEnvelope.model_validate(
        {
            **production_envelope_template(),
            "route": "CLARIFY",
            "patient_text": "Уточните.",
            "clarify_axis": "extent",
            "clarify_service_options": None,
            "commercial_intent": "none",
        }
    )
    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    resolution = ExactSalesResolution(
        None,
        None,
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed_ui_authority_from_resolution(resolution),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
    )
    assert semantic.direct_fact_ids == ()


def test_turn_frame_does_not_own_direct_fact_ids() -> None:
    assert "direct_fact_ids" not in TurnFrame.model_fields


def test_semantic_frame_owns_direct_fact_ids() -> None:
    assert "direct_fact_ids" in SalesOnePlusSemanticFrame.model_fields


def test_widget_fact_only_payment_renders_exact_fact(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="По рассрочке — условия из материалов клиники.",
            commercial_intent="payment",
            service_id="classic",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-payment",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert _INSTALLMENT_TEXT in str(outcome.widget.payload.get("answer") or "")


def test_widget_standalone_known_payment_fact_without_service_id(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Можно в рассрочку по условиям клиники.",
            commercial_intent="payment",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-standalone-known",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert "Можно в рассрочку по условиям клиники." in answer
    assert _INSTALLMENT_TEXT in answer
    assert answer.count(_INSTALLMENT_TEXT) == 1


def test_widget_malformed_envelope_is_technical_error_not_admin(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend("not-json")
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-malformed",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    assert backend.call_count == 1
    assert outcome.model_route == "error"
    assert outcome.widget.kind == "error"
    assert outcome.failure_kind == "json_invalid"


def test_widget_unknown_id_preserves_answer_with_ineligible_phrase(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Ответ.",
            commercial_intent="payment",
            references={"direct_fact_ids": ["missing_fact_id"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-unknown",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert outcome.widget.kind != "terminal"
    assert outcome.widget.kind != "error"
    assert "Ответ." in answer
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1
    assert "missing_fact_id" not in answer
    assert outcome.failure_kind != "direct_fact_id_not_in_current_pack"


def test_widget_backend_failure_still_admin(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(RuntimeError("timeout"))
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-backend",
        user_message="Есть парковка?",
        backend=backend,
    )
    assert backend.call_count == 1
    assert outcome.model_route == "model_admin"
    assert outcome.widget.kind == "terminal"
    assert outcome.widget.terminal_mode == "admin"


def test_streaming_protocol_error_emits_zero_patient_deltas() -> None:
    emitted: list[str] = []

    def on_delta(delta: str) -> None:
        emitted.append(delta)

    with pytest.raises(OneCallEnvelopeProtocolError):
        run_sales_one_plus_candidate_stream(
            user_message="Есть рассрочка?",
            cached_full_context=_context(),
            exact_sales_resolution=_resolution(),
            static_admin_handoff_text="Позвоните администратору.",
            backend=_CountingBackend("not-json"),
            on_delta=on_delta,
            pack_identity=_PACK_IDENTITY,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
    assert emitted == []


def test_widget_streaming_protocol_error_emits_zero_deltas(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    emitted: list[str] = []
    backend = _CountingBackend("not-json")
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-stream-protocol",
        user_message="Можно ли в рассрочку?",
        backend=backend,
        on_delta=emitted.append,
    )
    assert backend.call_count == 1
    assert outcome.model_route == "error"
    assert emitted == []


def test_blocking_candidate_protocol_error_propagates() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError):
        run_sales_one_plus_candidate(
            user_message="Есть рассрочка?",
            cached_full_context=_context(),
            exact_sales_resolution=_resolution(),
            static_admin_handoff_text="Позвоните администратору.",
            backend=_CountingBackend("not-json"),
            pack_identity=_PACK_IDENTITY,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_stream_parser_protocol_failure_before_finalize_has_zero_deltas() -> None:
    emitted: list[str] = []
    parser = SalesOnePlusStreamParser(
        emitted.append,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    parser.ingest("not-json")
    with pytest.raises(OneCallEnvelopeProtocolError):
        parser.finalize()
    assert emitted == []


def test_empty_direct_ids_ordinary_md_answer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(answer_envelope("Есть парковка у здания."))
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-empty-ids",
        user_message="Есть парковка?",
        backend=backend,
    )
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert "парков" in str(outcome.widget.payload.get("answer") or "").casefold()


def test_semantic_frame_requires_direct_fact_ids() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        SalesOnePlusSemanticFrame(
            route="ANSWER",
            service_id=None,
            service_id_provenance="null",
            extent=None,
            extent_provenance="null",
            jaw=None,
            jaw_provenance="null",
            stage=None,
            stage_provenance="null",
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis=None,
            clarify_service_options=None,
            service_reference_status="none",
            requested_service_id=None,
            availability_status="none",
        )


def test_materialize_direct_commercial_eligibility_aware_result() -> None:
    result = materialize_direct_commercial(
        bundle=_DEMO_BUNDLE,
        direct_fact_ids=("installment_12", "professional_whitening_discount"),
        authoritative_service_id="classic",
        today=date(2026, 8, 21),
    )
    assert isinstance(result, DirectCommercialMaterialization)
    assert result.eligible_texts == (_INSTALLMENT_TEXT,)
    assert result.has_ineligible is True
    assert _INSTALLMENT_TEXT in result.rendered_text
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in result.rendered_text
    assert _WHITENING_TEXT not in result.eligible_texts


def test_widget_hostile_expired_whitening_model_prose_stripped(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    hostile = "Сейчас действует скидка 10% до 15 августа."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=hostile,
            commercial_intent="promotion",
            promotion_scope="shown",
            references={"direct_fact_ids": ["professional_whitening_discount"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-hostile-whitening",
        user_message="Есть скидка на отбеливание?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert "10%" not in answer
    assert "до 15 августа" not in answer.casefold()
    assert _WHITENING_TEXT not in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1


def test_widget_direct_ids_preserve_all_on_4_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    prose = "Да, клиника выполняет All-on-4."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=prose,
            commercial_intent="none",
            service_id="all_on_4",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-preserve-all-on-4",
        user_message="Делаете All-on-4?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert prose in answer
    assert _INSTALLMENT_TEXT in answer


def test_widget_direct_ids_preserve_all_on_6_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    prose = "Протокол All-on-6 подходит при большей потребности в опоре."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=prose,
            commercial_intent="none",
            service_id="all_on_6",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-preserve-all-on-6",
        user_message="Расскажите про All-on-6.",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert "All-on-6" in answer
    assert prose in answer


def test_widget_direct_ids_preserve_ordinary_number_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    prose = "Врач имеет опыт 15 лет в имплантации."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=prose,
            commercial_intent="payment",
            service_id="classic",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-preserve-ordinary-number",
        user_message="Кто делает имплантацию?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert prose in answer
    assert "15" in answer


def test_widget_hostile_partial_eligibility_strips_unauthorized_promo_preserves_prose(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    hostile = (
        "Сейчас действует скидка 10% до 15 августа. "
        "Рассрочка доступна до 24 месяцев."
    )
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=hostile,
            commercial_intent="payment",
            service_id="classic",
            references={
                "direct_fact_ids": ["installment_12", "professional_whitening_discount"],
            },
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-hostile-partial",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert _INSTALLMENT_TEXT in answer
    assert "10%" not in answer
    assert "до 15 августа" not in answer.casefold()
    assert "24" in answer
    assert "Рассрочка доступна до 24 месяцев." in answer
    assert _WHITENING_TEXT not in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1


def test_widget_installment_month_count_preserved_with_direct_id(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    prose = "Рассрочка доступна до 24 месяцев."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=prose,
            commercial_intent="payment",
            service_id="classic",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-preserve-24-months",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert prose in answer
    assert "24" in answer
    assert _INSTALLMENT_TEXT in answer


def test_widget_price_plus_direct_installment_renders_both(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Стоимость зависит от системы. Ниже — условия из материалов клиники.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            scenario="cost",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-price-installment",
        user_message="Сколько стоит имплант и есть ли рассрочка?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert _INSTALLMENT_TEXT in answer
    assert outcome.widget.payload.get("offer") is not None


def test_widget_all_ineligible_direct_id_controlled_response(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    prose = "Про отбеливание."
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text=prose,
            commercial_intent="promotion",
            promotion_scope="general",
            references={"direct_fact_ids": ["professional_whitening_discount"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-all-ineligible",
        user_message="Есть скидка на отбеливание?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert prose in answer
    assert answer.strip()
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1


def test_widget_nikadent_cross_pack_installment_preserves_answer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Про рассрочку.",
            commercial_intent="payment",
            references={"direct_fact_ids": ["installment_12"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-nika-cross",
        user_message="Есть рассрочка?",
        backend=backend,
        client_id="nikadent",
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert outcome.widget.kind != "terminal"
    assert outcome.widget.kind != "error"
    assert "Про рассрочку." in answer
    assert _INSTALLMENT_TEXT not in answer
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1
    assert "installment_12" not in answer
    assert outcome.failure_kind != "direct_fact_id_not_in_current_pack"


def test_widget_mixed_known_and_unknown_direct_ids_preserve_eligible_fact(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Основной ответ про рассрочку.",
            commercial_intent="payment",
            references={"direct_fact_ids": ["installment_12", "missing_fact_id"]},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-mixed-ids",
        user_message="Можно ли в рассрочку?",
        backend=backend,
    )
    answer = str(outcome.widget.payload.get("answer") or "")
    assert backend.call_count == 1
    assert outcome.model_route == "model"
    assert outcome.widget.kind == "materialized"
    assert "Основной ответ про рассрочку." in answer
    assert _INSTALLMENT_TEXT in answer
    assert answer.count(_INSTALLMENT_TEXT) == 1
    assert DIRECT_COMMERCIAL_INELIGIBLE_PHRASE in answer
    assert answer.count(DIRECT_COMMERCIAL_INELIGIBLE_PHRASE) == 1
    assert "missing_fact_id" not in answer
    assert outcome.failure_kind != "direct_fact_id_not_in_current_pack"


def test_widget_payment_without_service_or_direct_ids_keeps_terminal_dispatch(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    backend = _CountingBackend(
        dumps_production_envelope(
            patient_text="Какие есть общие условия оплаты?",
            commercial_intent="payment",
            references={"direct_fact_ids": []},
        )
    )
    outcome = _run_widget_with_backend(
        monkeypatch,
        flask_app,
        sid="b1-payment-no-ids",
        user_message="Какие есть общие условия оплаты?",
        backend=backend,
    )
    assert backend.call_count == 1
    assert outcome.widget.kind == "terminal"
    assert outcome.widget.kind != "materialized"
    assert outcome.model_route == "local"


def test_duplicate_direct_text_fact_renders_once() -> None:
    bundle = _DEMO_BUNDLE.model_copy(deep=True)
    shared = "Одинаковый коммерческий текст."
    bundle.facts["tax_deduction"] = bundle.facts["tax_deduction"].model_copy(
        update={"text_fact": shared}
    )
    bundle.facts["installment_12"] = bundle.facts["installment_12"].model_copy(
        update={"text_fact": shared}
    )
    text = materialize_direct_commercial_text(
        bundle=bundle,
        direct_fact_ids=("installment_12", "tax_deduction"),
        authoritative_service_id=None,
        today=date(2026, 8, 21),
    )
    merged = append_direct_commercial_without_duplicates("", text)
    assert merged.count(shared) == 1
