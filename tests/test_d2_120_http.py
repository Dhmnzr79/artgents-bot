"""Approved turn-only medical handoff and technical failures, offline HTTP."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_document_click_task_http import PromptProvider, _body
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_sim2_dialogues import raw, explanation


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("next_kind", ["child", "address", "medicine", "pain_price", "fear"])
def test_medical_history_continues_in_same_session(http_env, transport, next_kind):
    client, db, use, _ = http_env
    fake = use(PromptProvider(raw(outcome="admin")))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="pain", q="Сильно болит имплант после установки"), transport)
    assert ". Если ситуация срочная" in first["answer"]
    assert first["ui"]["quick_replies"] == first["ui"]["buttons"] == []
    question, payload = {
        "child": ("Можно записать ребёнка 12 лет?", raw({"request_id": "r1", "kind": "clinic_policy",
            "policy_ids": ["no_pediatric_dentistry"], "age_group": "child", "context": "current_care"})),
        "address": ("А адрес клиники?", raw({"request_id": "r1", "kind": "contact", "contact_fields": ["contact_address"]})),
        "medicine": ("А что мне выпить?", raw(outcome="admin")),
        "pain_price": ("Сколько стоит вылечить эту боль?", raw(outcome="admin")),
        "fear": ("Другой вопрос: я боюсь будущего лечения", raw(explanation("Врач объяснит, как проходит обезболивание."))),
    }[next_kind]
    fake.raw = payload
    args = dict(request_id="next", q=question)
    answer = _body(send(client, **args), transport)
    assert _body(send(client, **args), transport) == answer
    assert len(fake.inputs) == 2
    prior = fake.inputs[-1].context.ordinary.dialogue_pairs[-1]
    assert prior.patient_text == "Сильно болит имплант после установки"
    assert "Такой вопрос лучше решить напрямую с клиникой" in prior.assistant_text
    assert "An earlier medical/admin handoff ends that question" in fake.messages[-1][0]["content"]
    if next_kind in {"medicine", "pain_price"}:
        assert answer["answer"] == first["answer"]
        assert answer["ui"]["quick_replies"] == answer["ui"]["buttons"] == []
    elif next_kind == "child":
        assert "детскую стоматологию" in answer["answer"]
    elif next_kind == "fear":
        assert answer["answer"] == "Врач объяснит, как проходит обезболивание."
    else:
        assert answer["answer"] and answer["answer"] != first["answer"]
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid="cp6a")).state
        assert state.revision == 2
        assert not state.clarify_pending


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_medical_does_not_bypass_spam_hard_stop(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(outcome="admin")))
    send = post if transport == "json" else post_sse
    _body(send(client, request_id="pain", q="Болит после операции"), transport)
    for i in range(2):
        _body(send(client, request_id=f"spam{i}", q="!!!!!!!!!!!!"), transport)
    closed = _body(send(client, request_id="closed", q="Какой адрес?"), transport)
    assert len(fake.inputs) == 1
    assert closed["ui"]["buttons"] == []


def assert_error(response, transport):
    if transport == "json":
        assert response.status_code == 503
        assert response.get_json() == {"error": "d2_turn_failed"}
    else:
        events = dict(sse_events(response))
        assert events["error"] == {"error": "d2_turn_failed"}
        assert "ui" not in events and "done" not in events


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_medical_continuation_after_one_spam_warning(http_env, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(raw(outcome="admin")))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="pain", q="Болит имплант после установки"), transport)
    _body(send(client, request_id="warn", q="!!!!!!!!!!!!"), transport)
    answer = _body(send(client, request_id="medicine", q="Что выпить от этой боли?"), transport)
    assert answer["answer"] == first["answer"]
    assert answer["ui"]["buttons"] == answer["ui"]["quick_replies"] == []
    assert len(fake.inputs) == 2
    assert any(p.patient_text == "Болит имплант после установки"
               for p in fake.inputs[-1].context.ordinary.dialogue_pairs)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_failure_before_commit_is_logged_without_success_receipt(http_env, transport):
    client, db, use, tmp_path = http_env
    fake = use(FakeProvider(raw(explanation())))
    def fail(request):
        fake.inputs.append(request)
        raise RuntimeError("offline_provider_failure")
    fake.generate = fail
    send = post if transport == "json" else post_sse
    assert_error(send(client, request_id="failed", q="Как проходит лечение?"), transport)
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a")) is None
    rows = [json.loads(line) for line in (tmp_path / "logs/d2_full_audit.jsonl").read_text(encoding="utf-8").splitlines()]
    assert any(r["event"] == "exception" and r.get("exception_type") == "RuntimeError" for r in rows)
    assert any(r["event"] == "diagnostic" and r["diagnostic"]["event"] == "failure" for r in rows)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_post_commit_error_preserves_lead_and_replays_receipt(http_env, transport, monkeypatch):
    from session import capture_lead_session_row, session_client_scope
    import core.d2_http_adapter as adapter
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw({"request_id": "r1", "kind": "booking", "age_group": "adult"})))
    send = post if transport == "json" else post_sse
    _body(send(client, request_id="book", q="Хочу записаться"), transport)
    _body(send(client, request_id="name", q="Анна"), transport)
    args = dict(request_id="phone", q="+7 999 123 45 67")
    def fail_payload(*args, **kwargs):
        raise RuntimeError("offline_after_commit")
    with monkeypatch.context() as patch:
        patch.setattr(adapter, "_response_payload", fail_payload)
        assert_error(send(client, **args), transport)
    with session_client_scope("demo"):
        lead_before = capture_lead_session_row("cp6a")
    with D2DialogueStore(db) as store:
        saved = store.read_completion(SessionKey(client_id="demo", sid="cp6a"), "phone")
        assert saved.lead_effect.status == "demo_stub"
        effect_id = saved.lead_effect.effect_id
    replay = _body(send(client, **args), transport)
    assert replay["lead_effect"] == {"status": "demo_stub", "effect_id": effect_id}
    assert len(fake.inputs) == 1
    with session_client_scope("demo"):
        assert capture_lead_session_row("cp6a") == lead_before
