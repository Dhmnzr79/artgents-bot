"""Architectural tenant isolation for One Call (offline HTTP/SSE)."""

from __future__ import annotations

import concurrent.futures
import json
import re
import uuid

import pytest

import app as app_module
import config
from core.one_call_client_pack_identity import build_client_pack_identity
from core.target_contact_authority import canonical_contact_phone
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_fast_widget_integration import (
    _CountingBackend,
    _install_rotating_backend_factory,
    _install_sales_fast_transport,
)
from tests.test_sales_one_plus_turn import answer_envelope

_DEMO_PHONE = canonical_contact_phone("demo")
_NIKADENT_BRANCH_PHONE = "+7 (900) 444-69-97"
_DEMO_DOCTOR = "Кузнецов"
_NIKADENT_DOCTOR = "Данилов"
_DEMO_FACT_MARKER = "free_implant_consult"
_NIKADENT_FACT_MARKER = "free_orthopedic_consult"
_DEMO_ALL_ON_4_AMOUNT = "318000"
_NIKADENT_FIXED_BRIDGE_AMOUNT = "10000"
_DEMO_CARIES_AMOUNT = "6500"


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _enable_demo_nikadent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))


def _parse_sse_ui_payload(resp) -> dict:
    text = resp.get_data(as_text=True)
    assert text.count("event: done") == 1
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    return json.loads(match.group(1))


def _post_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    client_id: str,
) -> tuple[dict, _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    )
    assert resp.status_code == 200
    return resp.get_json(), backend


def _post_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    client_id: str,
) -> tuple[dict, _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    )
    assert resp.status_code == 200
    return _parse_sse_ui_payload(resp), backend


def _prompt_text(backend: _CountingBackend) -> str:
    assert backend.invocation is not None
    return str(backend.invocation.user_prompt or "")


def _corpus_text(backend: _CountingBackend) -> str:
    assert backend.invocation is not None
    return str(backend.invocation.model_corpus_text or "")


def _capture_runtime_diagnostics(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    captured: list[dict] = []

    def _capture(_logger, msg, **fields):
        if msg == "runtime_turn_diagnostic":
            captured.append(fields)

    monkeypatch.setattr(app_module, "log_json_no_context", _capture)
    return captured


def _diagnostic_pack_hash(fields: dict, *, client_id: str) -> str:
    sales_fast = fields.get("sales_fast") or {}
    assert sales_fast.get("client_id") == client_id
    pack_hash = sales_fast.get("client_pack_hash")
    assert pack_hash
    return str(pack_hash)


@pytest.mark.parametrize("client_id", ["demo", "nikadent"])
def test_prompt_isolation_includes_own_markers_not_foreign(
    monkeypatch: pytest.MonkeyPatch,
    client_id: str,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    _, backend = _post_ask(
        monkeypatch,
        sid=f"s-tenant-prompt-{client_id}-{uuid.uuid4().hex[:6]}",
        user_message="Расскажите о клинике",
        envelope_json=answer_envelope("Кратко о клинике."),
        client_id=client_id,
    )
    prompt = _prompt_text(backend).lower()
    if client_id == "demo":
        assert '"client_id":"demo"' in prompt
        assert _norm_digits(_DEMO_PHONE) in _norm_digits(prompt)
        assert _DEMO_FACT_MARKER in prompt
        assert _norm_digits(_NIKADENT_BRANCH_PHONE) not in _norm_digits(prompt)
        assert _NIKADENT_FACT_MARKER not in prompt
        assert "ryabikova" not in prompt
    else:
        assert '"client_id":"nikadent"' in prompt or "ryabikova" in prompt
        assert "ryabikova" in prompt or "pogranichnaya" in prompt
        assert _NIKADENT_FACT_MARKER in prompt
        assert _DEMO_PHONE not in prompt
        assert _DEMO_FACT_MARKER not in prompt


def test_code_owned_phone_route_uses_bound_client_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    backend = _CountingBackend(answer_envelope("must not be used"))
    _install_sales_fast_transport(monkeypatch, backend)
    client = app_module.app.test_client()
    question = "Какой у вас телефон?"
    for client_id, expected_phone, forbidden_phone in (
        ("demo", _DEMO_PHONE, _NIKADENT_BRANCH_PHONE),
        ("nikadent", _NIKADENT_BRANCH_PHONE, _DEMO_PHONE),
    ):
        sid_base = uuid.uuid4().hex[:6]
        ask_resp = client.post(
            "/ask",
            json={
                "q": question,
                "sid": f"s-phone-ask-{client_id}-{sid_base}",
                "client_id": client_id,
            },
        )
        assert ask_resp.status_code == 200
        ask_payload = ask_resp.get_json()

        stream_resp = client.post(
            "/ask/stream",
            json={
                "q": question,
                "sid": f"s-phone-stream-{client_id}-{sid_base}",
                "client_id": client_id,
            },
        )
        assert stream_resp.status_code == 200
        stream_payload = _parse_sse_ui_payload(stream_resp)

        for payload in (ask_payload, stream_payload):
            assert payload["meta"]["client_id"] == client_id
            assert payload["meta"]["service_route"] == "sales_fast_contacts"
            answer = str(payload.get("answer") or "")
            assert answer.strip()
            assert _norm_digits(expected_phone) in _norm_digits(answer)
            assert forbidden_phone not in answer
            assert _norm_digits(forbidden_phone) not in _norm_digits(answer)

        assert ask_payload["answer"] == stream_payload["answer"]
        assert (
            ask_payload["meta"]["service_route"]
            == stream_payload["meta"]["service_route"]
        )

    assert backend.call_count == 0


def test_code_owned_prices_stay_tenant_specific_after_cache_warmup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    demo_envelope = answer_envelope(
        "All-on-4 стоит 1 рубль.",
        service_id="all_on_4",
        commercial_intent="price",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
    )
    nika_envelope = answer_envelope(
        "Мост стоит 1 рубль.",
        service_id="fixed_bridge",
        commercial_intent="price",
        service_reference_status="resolved",
        requested_service_id="fixed_bridge",
    )
    backends = [
        _CountingBackend(demo_envelope),
        _CountingBackend(nika_envelope),
        _CountingBackend(demo_envelope),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    client = app_module.app.test_client()

    demo_payload = client.post(
        "/ask",
        json={
            "q": "Сколько стоит All-on-4?",
            "sid": f"s-tenant-price-demo-{uuid.uuid4().hex[:6]}",
            "client_id": "demo",
        },
    ).get_json()
    assert _DEMO_ALL_ON_4_AMOUNT in _norm_digits(str(demo_payload.get("answer") or ""))

    nika_payload = client.post(
        "/ask",
        json={
            "q": "Сколько стоит мост?",
            "sid": f"s-tenant-price-nika-{uuid.uuid4().hex[:6]}",
            "client_id": "nikadent",
        },
    ).get_json()
    nika_answer = _norm_digits(str(nika_payload.get("answer") or ""))
    assert _NIKADENT_FIXED_BRIDGE_AMOUNT in nika_answer
    assert _DEMO_ALL_ON_4_AMOUNT not in nika_answer

    demo_payload_again = client.post(
        "/ask",
        json={
            "q": "Сколько стоит All-on-4?",
            "sid": f"s-tenant-price-demo2-{uuid.uuid4().hex[:6]}",
            "client_id": "demo",
        },
    ).get_json()
    assert _DEMO_ALL_ON_4_AMOUNT in _norm_digits(str(demo_payload_again.get("answer") or ""))


def test_doctor_catalog_markers_stay_in_bound_corpus(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    _, demo_backend = _post_ask(
        monkeypatch,
        sid=f"s-tenant-doc-demo-{uuid.uuid4().hex[:6]}",
        user_message=f"Кто такой {_DEMO_DOCTOR}?",
        envelope_json=answer_envelope("Кратко о враче."),
        client_id="demo",
    )
    demo_corpus = _corpus_text(demo_backend).lower()
    assert _DEMO_DOCTOR.lower() in demo_corpus or "kuznetsov" in demo_corpus
    assert _NIKADENT_DOCTOR.lower() not in demo_corpus

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: _CountingBackend(answer_envelope("Кратко о враче.")),
    )
    _, nika_backend = _post_ask(
        monkeypatch,
        sid=f"s-tenant-doc-nika-{uuid.uuid4().hex[:6]}",
        user_message=f"Кто такой {_NIKADENT_DOCTOR}?",
        envelope_json=answer_envelope("Кратко о враче."),
        client_id="nikadent",
    )
    nika_corpus = _corpus_text(nika_backend).lower()
    assert _NIKADENT_DOCTOR.lower() in nika_corpus or "danilov" in nika_corpus
    assert _DEMO_DOCTOR.lower() not in nika_corpus


def test_demo_price_question_does_not_surface_nikadent_pricebook_amounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    payload, backend = _post_ask(
        monkeypatch,
        sid=f"s-tenant-promo-{uuid.uuid4().hex[:6]}",
        user_message="Сколько стоит лечение кариеса?",
        envelope_json=answer_envelope(
            "Лечение кариеса.",
            service_id="caries",
            commercial_intent="price",
            service_reference_status="resolved",
            requested_service_id="caries",
        ),
        client_id="demo",
    )
    assert backend.call_count == 1
    answer_digits = _norm_digits(str(payload.get("answer") or ""))
    assert _DEMO_CARIES_AMOUNT in answer_digits
    assert _NIKADENT_FIXED_BRIDGE_AMOUNT not in answer_digits
    prompt = _prompt_text(backend).lower()
    assert "nikadent" not in prompt
    assert "ryabikova" not in prompt


def test_same_sid_uses_separate_session_namespaces_per_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    sid = f"shared-tenant-{uuid.uuid4().hex[:8]}"
    demo_q = "Сколько стоит All-on-4 в demo?"
    nika_q = "Сколько стоит мост в nikadent?"
    demo_answer = "Demo All-on-4 ответ."
    nika_answer = "Nikadent bridge ответ."
    backends = [
        _CountingBackend(answer_envelope(demo_answer, service_id="all_on_4")),
        _CountingBackend(answer_envelope(nika_answer, service_id="fixed_bridge")),
        _CountingBackend(answer_envelope("Продолжение demo.")),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    bind_session_client("demo")
    mem_reset(sid)
    bind_session_client("nikadent")
    mem_reset(sid)
    bind_session_client("demo")
    client = app_module.app.test_client()

    resp_demo = client.post("/ask", json={"q": demo_q, "sid": sid, "client_id": "demo"})
    visible_demo = str(resp_demo.get_json().get("answer") or "")
    client.post("/ask", json={"q": nika_q, "sid": sid, "client_id": "nikadent"})
    nika_prompt = str(backends[1].invocation.user_prompt)
    assert demo_q.lower() not in nika_prompt.lower()
    assert visible_demo.lower() not in nika_prompt.lower()

    client.post("/ask", json={"q": "а рассрочка?", "sid": sid, "client_id": "demo"})
    demo_prompt = str(backends[2].invocation.user_prompt)
    assert demo_q.lower() in demo_prompt.lower()
    assert visible_demo.lower() in demo_prompt.lower()
    assert nika_q.lower() not in demo_prompt.lower()
    bind_session_client("demo")


def test_alternating_demo_nikadent_demo_restores_demo_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    demo_hash = build_client_pack_identity("demo").client_pack_hash
    nika_hash = build_client_pack_identity("nikadent").client_pack_hash
    diagnostics = _capture_runtime_diagnostics(monkeypatch)
    backends = [
        _CountingBackend(answer_envelope("Demo шаг 1.")),
        _CountingBackend(answer_envelope("Nikadent шаг 2.")),
        _CountingBackend(answer_envelope("Demo шаг 3.")),
    ]
    _install_rotating_backend_factory(monkeypatch, backends)
    client = app_module.app.test_client()
    sequence = (
        ("demo", "s-alt-1"),
        ("nikadent", "s-alt-2"),
        ("demo", "s-alt-3"),
    )
    for client_id, sid in sequence:
        payload = client.post(
            "/ask",
            json={"q": "Расскажите о клинике", "sid": sid, "client_id": client_id},
        ).get_json()
        assert payload["meta"]["client_id"] == client_id

    assert _diagnostic_pack_hash(diagnostics[0], client_id="demo") == demo_hash
    assert _diagnostic_pack_hash(diagnostics[1], client_id="nikadent") == nika_hash
    assert _diagnostic_pack_hash(diagnostics[2], client_id="demo") == demo_hash

    demo_prompt = str(backends[2].invocation.user_prompt).lower()
    assert _norm_digits(_DEMO_PHONE) in _norm_digits(demo_prompt)
    assert "ryabikova" not in demo_prompt


def test_parallel_requests_do_not_mix_prompts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import threading

    _enable_demo_nikadent(monkeypatch)
    stores: dict[int, _CountingBackend] = {}
    lock = threading.Lock()

    def _backend_factory() -> _CountingBackend:
        with lock:
            backend = stores[threading.get_ident()]
        return backend

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        _backend_factory,
    )
    results: dict[str, tuple[str, str]] = {}

    def _run(client_id: str) -> None:
        backend = _CountingBackend(answer_envelope(f"Ответ {client_id}."))
        with lock:
            stores[threading.get_ident()] = backend
        payload = app_module.app.test_client().post(
            "/ask",
            json={
                "q": "Расскажите о клинике",
                "sid": f"s-par-{client_id}-{uuid.uuid4().hex[:6]}",
                "client_id": client_id,
            },
        ).get_json()
        results[client_id] = (_prompt_text(backend), str(payload.get("meta", {}).get("client_id")))

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(_run, cid) for cid in ("demo", "nikadent")]
        for future in futures:
            future.result()

    demo_prompt, demo_meta = results["demo"]
    nika_prompt, nika_meta = results["nikadent"]
    assert demo_meta == "demo"
    assert nika_meta == "nikadent"
    assert _norm_digits(_DEMO_PHONE) in _norm_digits(demo_prompt)
    assert _DEMO_PHONE not in nika_prompt
    assert "ryabikova" in nika_prompt.lower() or _NIKADENT_BRANCH_PHONE in nika_prompt
    assert "ryabikova" not in demo_prompt.lower()


def test_unknown_client_id_is_rejected_without_demo_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": f"s-unknown-{uuid.uuid4().hex[:6]}", "client_id": "not-a-real-clinic"},
    )
    assert resp.status_code == 403
    payload = resp.get_json()
    assert payload.get("error") == "unknown_client"
    assert _DEMO_PHONE not in json.dumps(payload, ensure_ascii=False)


def test_missing_client_id_uses_documented_demo_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    backend = _CountingBackend(answer_envelope("Ответ demo."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Расскажите о клинике", "sid": f"s-default-{uuid.uuid4().hex[:6]}"},
    )
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["client_id"] == config.DEFAULT_CLIENT_ID
    assert _norm_digits(_DEMO_PHONE) in _norm_digits(_prompt_text(backend))


def test_ask_and_stream_resolve_same_client_pack_hash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable_demo_nikadent(monkeypatch)
    diagnostics = _capture_runtime_diagnostics(monkeypatch)
    envelope = answer_envelope("Ответ по клинике.")
    ask_payload, ask_backend = _post_ask(
        monkeypatch,
        sid=f"s-parity-ask-{uuid.uuid4().hex[:6]}",
        user_message="Расскажите о клинике",
        envelope_json=envelope,
        client_id="nikadent",
    )
    stream_payload, stream_backend = _post_stream(
        monkeypatch,
        sid=f"s-parity-stream-{uuid.uuid4().hex[:6]}",
        user_message="Расскажите о клинике",
        envelope_json=envelope,
        client_id="nikadent",
    )
    expected_hash = build_client_pack_identity("nikadent").client_pack_hash
    assert ask_payload["meta"]["client_id"] == "nikadent"
    assert stream_payload["meta"]["client_id"] == "nikadent"
    assert _diagnostic_pack_hash(diagnostics[0], client_id="nikadent") == expected_hash
    assert _diagnostic_pack_hash(diagnostics[1], client_id="nikadent") == expected_hash
    assert "ryabikova" in _prompt_text(ask_backend).lower()
    assert "ryabikova" in _prompt_text(stream_backend).lower()
    assert _DEMO_PHONE not in _prompt_text(ask_backend)
    assert _DEMO_PHONE not in _prompt_text(stream_backend)
