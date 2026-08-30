from __future__ import annotations

import hashlib
import json
from pathlib import Path

import config
import pytest

from contracts.one_call_envelope import OneCallEnvelope, OneCallEnvelopeReferences, required_envelope_field_names
from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_envelope_protocol import (
    MAX_ENVELOPE_UTF8_BYTES,
    OneCallEnvelopeProtocolError,
    dumps_production_envelope,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.one_call_prefix_cache import clear_one_call_prefix_cache, get_or_build_stable_prefix
from core.one_call_prefix_input_fingerprint import compute_prefix_input_fingerprint
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)
from core.sales_one_plus_protocol import SALES_ONE_PLUS_SYSTEM_POLICY
from core.sales_one_plus_stream import SalesOnePlusStreamParser
from core.target_cached_full_context import build_target_cached_full_context
from core.target_client_data import load_target_client_data
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_EXACT_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_EXACT_CATALOG,
    _EMPTY_REF_CATALOG,
    _PACK_IDENTITY,
    _context,
    _resolution,
    admin_envelope,
    answer_envelope,
)
from core.sales_one_plus_turn import (
    SalesOnePlusBackendFailure,
    run_sales_one_plus_candidate,
    run_sales_one_plus_candidate_stream,
)


_DEMO = Path(__file__).resolve().parents[1] / "clients" / "demo"


class _Backend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0

    def generate(self, _invocation, /):
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


class _StreamBackend:
    def __init__(self, chunks: tuple[str, ...], *, fail_after: bool = False) -> None:
        self.chunks = chunks
        self.fail_after = fail_after
        self.calls = 0

    def generate_stream(self, _invocation, callback, /) -> None:
        self.calls += 1
        for chunk in self.chunks:
            callback(chunk)
        if self.fail_after:
            raise RuntimeError("stream failed")


def _run_blocking(output: object):
    return run_sales_one_plus_candidate(
        user_message="Есть парковка?",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=_Backend(output),
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )


def _run_stream(chunks: tuple[str, ...], *, fail_after: bool = False):
    emitted: list[str] = []

    def on_delta(delta: str) -> None:
        emitted.append(delta)

    result = run_sales_one_plus_candidate_stream(
        user_message="Есть парковка?",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=_StreamBackend(chunks, fail_after=fail_after),
        on_delta=on_delta,
        pack_identity=_PACK_IDENTITY,
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
    )
    return result, emitted


@pytest.mark.parametrize(
    "route,decision,reason",
    (
        ("ANSWER", "answer", "model_answer"),
        ("CLARIFY", "clarify", "model_clarify"),
    ),
)
def test_blocking_valid_answer_and_clarify_routes(route: str, decision: str, reason: str) -> None:
    payload = dumps_production_envelope(
        route=route,
        patient_text="Уточните, пожалуйста.",
        clarify_axis="extent" if route == "CLARIFY" else None,
        clarify_service_options=None,
    )
    result = _run_blocking(payload)
    assert result.decision == decision
    assert result.reason == reason
    assert result.patient_text == "Уточните, пожалуйста."
    assert result.envelope is not None


def test_blocking_valid_admin_route() -> None:
    result = _run_blocking(admin_envelope())
    assert result.decision == "admin"
    assert result.reason == "model_admin"
    assert result.patient_text is None
    assert result.handoff_text == "Позвоните администратору."
    assert result.envelope is not None
    assert result.envelope.route == "ADMIN"


@pytest.mark.parametrize("commercial_intent", ("none", "price", "payment", "included", "promotion"))
def test_blocking_accepts_all_commercial_intent_values(commercial_intent: str) -> None:
    scope = "general" if commercial_intent == "promotion" else "none"
    result = _run_blocking(
        answer_envelope("Ответ.", commercial_intent=commercial_intent, promotion_scope=scope)
    )
    assert result.envelope is not None
    assert result.envelope.commercial_intent == commercial_intent
    assert result.envelope.promotion_scope == scope


def test_exact_fifteen_key_contract() -> None:
    assert required_envelope_field_names() == frozenset(production_envelope_template().keys())
    assert len(production_envelope_template()) == 15


@pytest.mark.parametrize(
    "mutator,code",
    (
        (lambda payload: payload.pop("route"), "missing_fields"),
    ),
)
def test_missing_and_extra_keys_rejected(mutator, code: str) -> None:
    payload = production_envelope_template()
    mutator(payload)
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


@pytest.mark.parametrize(
    "field,value,code",
    (
        ("route", "MAYBE", "route_invalid"),
        ("extent", "many_teeth", "extent_invalid"),
        ("jaw", "middle", "jaw_invalid"),
        ("scenario", "panic", "scenario_invalid"),
        ("commercial_intent", "discount", "commercial_intent_invalid"),
        ("clarify_axis", "symptom", "clarify_axis_invalid"),
    ),
)
def test_invalid_enums_rejected(field: str, value: object, code: str) -> None:
    payload = production_envelope_template(**{field: value})
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


@pytest.mark.parametrize(
    "field,value,code",
    (
        ("service_id", 1, "service_id_invalid"),
        ("stage", True, "stage_invalid"),
        ("patient_text", 1, "patient_text_invalid"),
    ),
)
def test_type_confusions_rejected(field: str, value: object, code: str) -> None:
    payload = production_envelope_template(**{field: value})
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_empty_and_whitespace_patient_text_rejected() -> None:
    for text in ("", "   "):
        payload = production_envelope_template(patient_text=text)
        with pytest.raises(OneCallEnvelopeProtocolError, match="patient_text_required"):
            parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_inactive_service_id_rejected() -> None:
    payload = production_envelope_template(service_id="classic")
    with pytest.raises(OneCallEnvelopeProtocolError, match="service_id_inactive"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_active_service_id_accepted() -> None:
    payload = production_envelope_template(service_id="classic", patient_text="Ответ.")
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.service_id == "classic"


def test_forbidden_stage_rejected() -> None:
    payload = production_envelope_template(stage="unknown_stage", patient_text="Ответ.")
    with pytest.raises(OneCallEnvelopeProtocolError, match="stage_not_allowed"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_allowed_stage_accepted() -> None:
    allowed = next(iter(_DEMO_CATALOG.allowed_patient_stages))
    payload = production_envelope_template(stage=allowed, patient_text="Ответ.")
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.stage == allowed


@pytest.mark.parametrize("count", (2, 3))
def test_service_clarify_accepts_two_or_three_active_options(count: int) -> None:
    options = list(_DEMO_CATALOG.active_service_ids)[:count]
    payload = production_envelope_template(
        route="CLARIFY",
        patient_text="Какую услугу вас интересует?",
        clarify_axis="service",
        clarify_service_options=options,
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.clarify_service_options == tuple(options)


@pytest.mark.parametrize("options", (None, ["classic"], ["a", "b", "c", "d"], ["classic", "classic"]))
def test_service_clarify_rejects_invalid_option_sets(options) -> None:
    payload = production_envelope_template(
        route="CLARIFY",
        patient_text="Какую услугу вас интересует?",
        clarify_axis="service",
        clarify_service_options=options,
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="clarify_service_options_invalid"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_non_service_clarify_forbids_options() -> None:
    payload = production_envelope_template(
        route="CLARIFY",
        patient_text="Сколько зубов?",
        clarify_axis="extent",
        clarify_service_options=["classic", "all_on_4"],
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="clarify_service_options_forbidden_for_axis"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_streaming_splits_json_at_every_boundary() -> None:
    payload = answer_envelope('Текст с "кавычками" и {скобками}.')
    for split_at in range(1, len(payload)):
        emitted: list[str] = []
        parser = SalesOnePlusStreamParser(
            emitted.append,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        parser.ingest(payload[:split_at])
        parser.ingest(payload[split_at:])
        envelope = parser.finalize()
        assert envelope.patient_text == 'Текст с "кавычками" и {скобками}.'
        assert emitted == [envelope.patient_text]


def test_invalid_stream_emits_zero_patient_delta() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_stream(("{not json",))


def test_interrupted_stream_emits_zero_patient_delta() -> None:
    partial = answer_envelope("Частичный")[:12]
    with pytest.raises(SalesOnePlusBackendFailure, match="stream_interrupted"):
        _run_stream((partial,), fail_after=True)


def test_valid_stream_emits_only_patient_text_once() -> None:
    payload = answer_envelope("Видимый текст")
    result, emitted = _run_stream((payload,))
    assert result.patient_text == "Видимый текст"
    assert emitted == ["Видимый текст"]
    assert '"route"' not in emitted[0]


def test_admin_stream_emits_zero_patient_delta() -> None:
    result, emitted = _run_stream((admin_envelope(),))
    assert result.decision == "admin"
    assert emitted == []


def test_oversized_blocking_and_streaming_rejected() -> None:
    huge_text = "x" * (MAX_ENVELOPE_UTF8_BYTES + 1)
    payload = answer_envelope(huge_text)
    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_blocking(payload)
    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_stream((payload,))


def test_blocking_and_streaming_share_one_parser() -> None:
    payload = answer_envelope("Shared parser")
    blocking = _run_blocking(payload)
    streaming, emitted = _run_stream((payload,))
    assert blocking.patient_text == streaming.patient_text == "Shared parser"
    assert emitted == ["Shared parser"]


def test_invalid_envelope_does_not_retry() -> None:
    backend = _Backend("not-json")
    with pytest.raises(OneCallEnvelopeProtocolError):
        run_sales_one_plus_candidate(
            user_message="Есть парковка?",
            cached_full_context=_context(),
            exact_sales_resolution=_resolution(),
            static_admin_handoff_text="Позвоните администратору.",
            backend=backend,
            pack_identity=_PACK_IDENTITY,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
        )
    assert backend.calls == 1


def test_prompt_contract_version_is_five() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 9
    assert "commercial_intent" in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    assert "@ANSWER" not in ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS


def test_prompt_v2_bump_changes_prefix_fingerprint() -> None:
    identity = ClientPackIdentityKey(
        client_id="fingerprint-test",
        client_pack_hash=hashlib.sha256(b"fingerprint-test").hexdigest(),
        prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
        model_snapshot=config.SALES_ONE_PLUS_FLASH_MODEL,
    )
    corpus = build_target_cached_full_context(_DEMO / "md")
    catalog = _DEMO_CATALOG
    ref_catalog = _DEMO_REF_CATALOG
    fingerprint = compute_prefix_input_fingerprint(
        identity, corpus, catalog, ref_catalog, _DEMO_EXACT_CATALOG
    )
    assert f"p{ONE_CALL_PROMPT_CONTRACT_VERSION}" in identity.cache_key()
    clear_one_call_prefix_cache()
    bundle, hit = get_or_build_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=catalog,
        service_reference_catalog=ref_catalog,
        exact_commercial_catalog=_DEMO_EXACT_CATALOG,
    )
    assert hit is False
    assert "=== SERVICE_REFERENCE_CATALOG ===" in bundle.stable_prefix
    assert "allowed_patient_stages" in bundle.stable_prefix
    assert "@ANSWER" not in bundle.stable_prefix
    assert SALES_ONE_PLUS_SYSTEM_POLICY in bundle.stable_prefix
    assert fingerprint


def test_flag_default_off() -> None:
    assert config.SALES_ONE_PLUS_ON is False


def test_protocol_and_backend_admin_preserve_no_envelope() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_blocking("not-json")

    with pytest.raises(SalesOnePlusBackendFailure, match="backend_failed"):
        run_sales_one_plus_candidate(
            user_message="Есть парковка?",
            cached_full_context=_context(),
            exact_sales_resolution=_resolution(),
            static_admin_handoff_text="Позвоните администратору.",
            backend=_Backend(RuntimeError("network")),
            pack_identity=_PACK_IDENTITY,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            exact_commercial_catalog=_EMPTY_EXACT_CATALOG,
        )


def test_sales_one_plus_result_rejects_answer_route_mismatch() -> None:
    envelope = OneCallEnvelope(
        route="CLARIFY",
        service_id=None,
        extent=None,
        jaw=None,
        stage=None,
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis="extent",
        clarify_service_options=None,
            patient_text="Текст",
            service_reference_status="none",
            requested_service_id=None,
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )
    with pytest.raises(ValueError, match="sales_one_plus_answer_envelope_required"):
        from contracts.sales_one_plus import SalesOnePlusResult

        SalesOnePlusResult(
            decision="answer",
            source="model",
            reason="model_answer",
            patient_text="Текст",
            envelope=envelope,
        )


def test_sales_one_plus_result_rejects_patient_text_mismatch() -> None:
    envelope = OneCallEnvelope(
        route="ANSWER",
        service_id=None,
        extent=None,
        jaw=None,
        stage=None,
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis=None,
        clarify_service_options=None,
            patient_text="Envelope text",
            service_reference_status="none",
            requested_service_id=None,
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )
    with pytest.raises(ValueError, match="sales_one_plus_answer_patient_text_mismatch"):
        from contracts.sales_one_plus import SalesOnePlusResult

        SalesOnePlusResult(
            decision="answer",
            source="model",
            reason="model_answer",
            patient_text="Different text",
            envelope=envelope,
        )


def test_one_call_envelope_rejects_blank_service_id_direct() -> None:
    with pytest.raises(ValueError, match="service_id_invalid"):
        OneCallEnvelope(
            route="ANSWER",
            service_id="   ",
            extent=None,
            jaw=None,
            stage=None,
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis=None,
            clarify_service_options=None,
            patient_text="Ответ.",
            service_reference_status="none",
            requested_service_id=None,
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )


def test_one_call_envelope_rejects_blank_stage_direct() -> None:
    with pytest.raises(ValueError, match="stage_invalid"):
        OneCallEnvelope(
            route="ANSWER",
            service_id=None,
            extent=None,
            jaw=None,
            stage="  ",
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis=None,
            clarify_service_options=None,
            patient_text="Ответ.",
            service_reference_status="none",
            requested_service_id=None,
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )


@pytest.mark.parametrize("options", (("a",), ("a", "b", "c", "d"), ("a", "a", "b")))
def test_one_call_envelope_rejects_invalid_option_sets_direct(options: tuple[str, ...]) -> None:
    with pytest.raises(ValueError, match="clarify_service_options_invalid"):
        OneCallEnvelope(
            route="CLARIFY",
            service_id=None,
            extent=None,
            jaw=None,
            stage=None,
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis="service",
            clarify_service_options=options,
            patient_text="Уточните.",
            service_reference_status="none",
            requested_service_id=None,
            references=OneCallEnvelopeReferences(direct_fact_ids=()),
        )


def test_duplicate_json_keys_rejected() -> None:
    payload = answer_envelope("Ответ.")
    duplicate = payload.replace('"route":"ANSWER"', '"route":"ANSWER","route":"ADMIN"', 1)
    with pytest.raises(OneCallEnvelopeProtocolError, match="json_duplicate_keys"):
        parse_production_envelope_json(
            duplicate,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_unencodable_unicode_rejected_blocking_and_streaming() -> None:
    bad = '{"route":"ANSWER","service_id":null,"extent":null,"jaw":null,"stage":null,"scenario":"none","commercial_intent":"none","promotion_scope":"none","clarify_axis":null,"clarify_service_options":null,"patient_text":"\ud800","service_reference_status":"none","requested_service_id":null,"references":{"direct_fact_ids":[]}}'
    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_blocking(bad)

    with pytest.raises(OneCallEnvelopeProtocolError):
        _run_stream((bad,))


def test_prompt_policy_forbids_exact_commercial_values_in_patient_text() -> None:
    assert "Marketing promotions" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "A price for several teeth" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "deterministic code renders those values" in SALES_ONE_PLUS_SYSTEM_POLICY
