from __future__ import annotations

import hashlib
import re
from pathlib import Path

import config
import pytest
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from contracts.one_call_client_pack_identity import ClientPackIdentityKey
from contracts.sales_one_plus import SalesOnePlusStrictFact
from contracts.target_cached_full_context import TargetCachedFullContext
from core.one_call_client_pack_identity import build_client_pack_identity
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_envelope_protocol import dumps_production_envelope
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.target_cached_full_context import build_target_cached_full_context
from core.target_client_data import load_target_client_data
from core.sales_one_plus_turn import SalesOnePlusBackendFailure, run_sales_one_plus_candidate
import core.sales_one_plus_live_backend as live_module
from core.sales_one_plus_live_backend import SalesOnePlusLiveBackend


def answer_envelope(text: str, **overrides: object) -> str:
    return dumps_production_envelope(patient_text=text, **overrides)


def admin_envelope(**overrides: object) -> str:
    return dumps_production_envelope(
        route="ADMIN",
        patient_text=None,
        clarify_axis=None,
        clarify_service_options=None,
        **overrides,
    )


def _resolution() -> ExactSalesResolution:
    authority = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    return ExactSalesResolution(None, None, None, None, None, authority, authority, authority, authority, authority)


class _Backend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.calls = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.calls += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def _context() -> TargetCachedFullContext:
    return TargetCachedFullContext(
        corpus_text="WRONG CORPUS",
        prompt_corpus_text="MD number 73.5 and microfact parking.",
        document_count=1,
        document_paths=("x.md",),
        sha256="x",
    )


_PACK_IDENTITY = ClientPackIdentityKey(
    client_id="unit-test-isolated",
    client_pack_hash=hashlib.sha256(b"unit-test-isolated-pack").hexdigest(),
    prompt_contract_version=ONE_CALL_PROMPT_CONTRACT_VERSION,
    model_snapshot=config.SALES_ONE_PLUS_FLASH_MODEL,
)
_DEMO_PACK_IDENTITY = build_client_pack_identity("demo")
_EMPTY_CATALOG = ActiveServiceCatalogSnapshot(
    canonical_json='{"services":[],"allowed_patient_stages":[]}',
)
_EMPTY_REF_CATALOG = ServiceReferenceCatalogSnapshot(
    canonical_json='{"services":[]}',
)
_DEMO_CATALOG = ActiveServiceCatalogSnapshot.from_bundle(load_target_client_data("demo").bundle)
_DEMO_REF_CATALOG = ServiceReferenceCatalogSnapshot.from_bundle(
    load_target_client_data("demo").bundle
)


_EMPTY_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot(
    canonical_json='{"facts":[]}',
)
_DEMO_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot.from_bundle(
    load_target_client_data("demo").bundle
)
_EMPTY_EXACT_CATALOG = ExactCommercialCatalogSnapshot(
    canonical_json='{"facts":[],"offers":[],"services":[]}',
)
_DEMO_EXACT_CATALOG = ExactCommercialCatalogSnapshot.from_bundle(
    load_target_client_data("demo").bundle
)


def _run(**kwargs):
    kwargs.setdefault("pack_identity", _PACK_IDENTITY)
    kwargs.setdefault("active_service_catalog", _EMPTY_CATALOG)
    kwargs.setdefault("service_reference_catalog", _EMPTY_REF_CATALOG)
    kwargs.setdefault("exact_commercial_catalog", _EMPTY_EXACT_CATALOG)
    return run_sales_one_plus_candidate(static_admin_handoff_text="Позвоните администратору.", **kwargs)


def test_local_gate_bypasses_backend_only_for_spam() -> None:
    backend = _Backend(answer_envelope("wrong"))
    symptom = _run(
        user_message="Сильно болит зуб",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        backend=backend,
    )
    assert symptom.decision == "answer" and symptom.patient_text == "wrong" and backend.calls == 1
    spam = _run(
        user_message="!!!!!",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        backend=_Backend(answer_envelope("wrong")),
    )
    assert spam.decision == "spam" and spam.handoff_text is None


def test_pass_uses_model_corpus_and_pre_model_hints_once() -> None:
    backend = _Backend(answer_envelope("Есть парковка, цена по прайсу."))
    result = _run(
        user_message="Есть парковка и сколько стоит?",
        cached_full_context=_context(),
        exact_sales_resolution=_resolution(),
        current_strict_facts=(),
        sales_context={"catalog_service_hint": "имплантация"},
        backend=backend,
    )
    assert (result.decision, result.patient_text, backend.calls) == ("answer", "Есть парковка, цена по прайсу.", 1)
    assert result.envelope is not None and result.envelope.commercial_intent == "none"
    assert "MD number 73.5" in backend.invocation.system_prompt
    assert "WRONG CORPUS" not in backend.invocation.system_prompt
    assert "PRE_MODEL_HINTS" in backend.invocation.user_prompt
    assert "CURRENT_STRICT_FACTS" not in backend.invocation.user_prompt
    assert "EXACT_SALES_RESOLUTION" not in backend.invocation.user_prompt


def test_scoped_service_axes_pre_flash_hints_are_neutral() -> None:
    authority = ExactSalesFieldAuthority(
        authority="governed_ui",
        provenance="target:ui_scope/implantation/few_teeth",
    )
    resolution = ExactSalesResolution(
        service_id="implant_alpha",
        aspect="price",
        extent="few_teeth",
        jaw="both",
        stage="extraction_context",
        service_id_authority=authority,
        aspect_authority=authority,
        extent_authority=authority,
        jaw_authority=authority,
        stage_authority=authority,
    )
    facts = (
        SalesOnePlusStrictFact(
            id="offer:clinic-authored-few-teeth",
            kind="offer",
            text="Несколько зубов: от 321 000 ₽; единица — согласованный объём.",
        ),
    )
    backend = _Backend(answer_envelope("Цена указана в согласованном оффере.", commercial_intent="price"))
    result = _run(
        user_message="Цена для нескольких зубов?",
        cached_full_context=_context(),
        exact_sales_resolution=resolution,
        current_strict_facts=facts,
        backend=backend,
    )

    assert result.decision == "answer" and backend.calls == 1
    assert "PRE_MODEL_HINTS" in backend.invocation.user_prompt
    assert "321 000 ₽" not in backend.invocation.user_prompt
    assert "implant_alpha" in backend.invocation.user_prompt


def test_model_admin_ignores_prose_and_backend_failure_is_not_admin() -> None:
    from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError

    admin = _Backend(admin_envelope())
    malformed = _Backend("not protocol")
    failed = _Backend(RuntimeError("network"))
    admin_result = _run(user_message="Есть парковка?", cached_full_context=_context(), exact_sales_resolution=_resolution(), backend=admin)
    assert admin_result.decision == "admin" and admin_result.patient_text is None and admin_result.handoff_text == "Позвоните администратору." and admin_result.reason == "model_admin" and admin.calls == 1
    assert admin_result.envelope is not None and admin_result.envelope.route == "ADMIN"
    with pytest.raises(OneCallEnvelopeProtocolError, match="json_invalid"):
        _run(user_message="Есть парковка?", cached_full_context=_context(), exact_sales_resolution=_resolution(), backend=malformed)
    assert malformed.calls == 1
    with pytest.raises(SalesOnePlusBackendFailure, match="backend_failed"):
        _run(user_message="Есть парковка?", cached_full_context=_context(), exact_sales_resolution=_resolution(), backend=failed)
    assert failed.calls == 1


def test_live_adapter_is_one_shot_and_requests_json_mode(monkeypatch) -> None:
    calls = []

    class _Response:
        model = "candidate-model"
        choices = [type("Choice", (), {"message": type("Message", (), {"content": answer_envelope("Да")})()})()]

    monkeypatch.setattr(live_module, "chat_completions_create", lambda **kwargs: calls.append(kwargs) or _Response())
    backend = SalesOnePlusLiveBackend(model="candidate-model")
    result = _run(user_message="Есть парковка?", cached_full_context=_context(), exact_sales_resolution=_resolution(), backend=backend)

    assert result.decision == "answer" and len(calls) == 1
    assert calls[0]["model"] == "candidate-model"
    assert calls[0]["response_format"] == {"type": "json_object"}
    spam = _run(user_message="!!!!!", cached_full_context=_context(), exact_sales_resolution=_resolution(), backend=backend)
    assert spam.decision == "spam"
    assert len(calls) == 1


def test_live_adapter_defaults_to_flash_snapshot_model() -> None:
    assert live_module.sales_one_plus_model() == config.SALES_ONE_PLUS_FLASH_MODEL


def test_live_demo_model_corpus_and_every_numeric_line_reach_invocation() -> None:
    cached = build_target_cached_full_context(Path("clients/demo/md"))
    backend = _Backend(answer_envelope("Ответ из корпуса."))
    result = run_sales_one_plus_candidate(
        user_message="Расскажите об услугах клиники",
        cached_full_context=cached,
        exact_sales_resolution=_resolution(),
        static_admin_handoff_text="Позвоните администратору.",
        backend=backend,
        pack_identity=_DEMO_PACK_IDENTITY,
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        exact_commercial_catalog=_DEMO_EXACT_CATALOG,
    )

    assert result.decision == "answer"
    assert backend.invocation.model_corpus_text == cached.model_corpus_text
    assert backend.invocation.model_corpus_text in backend.invocation.system_prompt
    numeric_lines = [
        line.strip()
        for line in backend.invocation.model_corpus_text.splitlines()
        if re.search(r"\d", line) and line.strip()
    ]
    assert len(numeric_lines) >= 100
    missing = [line for line in numeric_lines if line not in backend.invocation.system_prompt]
    assert missing == []
