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


# Legacy helpers above remain importable by historical D1 suites. Current HTTP
# acceptance below uses D2 exclusively; it does not adapt old envelopes.
from tests.d2_ci_http import FakeProvider, http_env, send, prompt, raw, explanation
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore


@pytest.mark.parametrize('tenant', ['demo', 'nikadent'])
def test_prompt_and_doctor_corpus_are_tenant_bound(http_env, tenant):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Рассказываю о клинике.'))))
    send(client, client_id=tenant, q='Расскажите о врачах')
    text = prompt(fake).lower()
    own, foreign = ('кузнецов', 'данилов') if tenant == 'demo' else ('данилов', 'кузнецов')
    assert own in text
    assert foreign not in text
    own_fact, foreign_fact = (_DEMO_FACT_MARKER, _NIKADENT_FACT_MARKER) if tenant == 'demo' else (_NIKADENT_FACT_MARKER, _DEMO_FACT_MARKER)
    assert own_fact in text and foreign_fact not in text
    assert fake.inputs[0].model_view.client_id == tenant


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_contact_prices_and_warm_cache_stay_in_tenant(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw({'kind':'contact', 'request_id':'r1', 'contact_fields':['contact_phone']})))
    for tenant, own, foreign in [('demo', _DEMO_PHONE, _NIKADENT_BRANCH_PHONE), ('nikadent', _NIKADENT_BRANCH_PHONE, _DEMO_PHONE), ('demo', _DEMO_PHONE, _NIKADENT_BRANCH_PHONE)]:
        body = send(client, transport, sid=uuid.uuid4().hex, client_id=tenant, q='Какой телефон?')
        assert _norm_digits(own) in _norm_digits(body['answer'])
        assert _norm_digits(foreign) not in _norm_digits(body['answer'])
    for tenant, service, own, foreign in [('demo', 'all_on_4', '318000', '10000'), ('nikadent', 'fixed_bridge', '10000', '318000'), ('demo', 'caries', '6500', '10000')]:
        fake.raw = raw({'kind':'price', 'request_id':'r1', 'target':{'type':'service','id':service}})
        body = send(client, transport, sid=uuid.uuid4().hex, client_id=tenant, q='Сколько стоит?')
        assert own in _norm_digits(body['answer']) and foreign not in _norm_digits(body['answer'])
        assert body['client_id'] == tenant
    assert len(fake.inputs) == 6


def test_same_sid_history_replay_and_alternating_tenants(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Ответ demo.'))))
    demo = send(client, sid='shared', request_id='one', q='DEMO_CONTEXT')
    fake.raw = raw(explanation('Ответ другой клиники.'))
    nika = send(client, sid='shared', request_id='one', client_id='nikadent', q='NIKA_CONTEXT')
    assert send(client, sid='shared', request_id='one', q='DEMO_CONTEXT') == demo
    assert send(client, sid='shared', request_id='one', client_id='nikadent', q='NIKA_CONTEXT') == nika
    assert len(fake.inputs) == 2
    for tenant, own, foreign in [('demo','DEMO_CONTEXT','NIKA_CONTEXT'), ('nikadent','NIKA_CONTEXT','DEMO_CONTEXT'), ('demo','DEMO_CONTEXT','NIKA_CONTEXT')]:
        send(client, sid='shared', request_id=uuid.uuid4().hex, client_id=tenant, q='Продолжите')
        assert own in prompt(fake) and foreign not in prompt(fake)
        with D2DialogueStore(db) as store:
            assert store.read(SessionKey(client_id=tenant, sid='shared')).state.revision >= 2


def test_parallel_requests_do_not_mix_prompts(http_env):
    _, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Объяснение.'))))
    def run(tenant):
        return send(app_module.app.test_client(), client_id=tenant, sid=tenant, q=tenant)
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, ['demo', 'nikadent']))
    assert {b['client_id'] for b in results} == {'demo','nikadent'}
    assert len(fake.inputs) == 2
    for i, request in enumerate(fake.inputs):
        own, foreign = ('кузнецов','данилов') if request.model_view.client_id == 'demo' else ('данилов','кузнецов')
        assert own in prompt(fake, i).lower() and foreign not in prompt(fake, i).lower()


def test_unknown_client_rejected_and_default_is_demo(http_env):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Ответ demo.'))))
    bad = client.post('/ask', json={'sid':'shared','request_id':'one','q':'Вопрос','client_id':'foreign'})
    assert bad.status_code == 403 and bad.get_json()['error'] == 'unknown_client'
    assert not db.exists() and fake.inputs == []
    good = client.post('/ask', json={'sid':'shared','request_id':'one','q':'Вопрос'})
    assert good.get_json()['client_id'] == 'demo'
    assert len(fake.inputs) == 1 and fake.inputs[0].model_view.client_id == 'demo'


def test_json_sse_same_pack_identity(http_env):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(explanation('Объяснение.'))))
    for transport in ['json','sse']:
        send(client, transport, sid=transport, client_id='nikadent', q='О клинике')
    assert fake.inputs[0].model_view == fake.inputs[1].model_view
