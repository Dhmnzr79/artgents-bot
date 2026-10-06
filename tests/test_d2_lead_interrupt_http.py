"""D2 lead interruption through the real JSON/SSE adapter, with fake provider."""

import json
import re

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from lead_interrupt import LEAD_CANCEL_REF, LEAD_PENDING_ANSWER_REF, LEAD_RESUME_REF
from session import mem_get, session_client_scope
from tests.d2_ci_http import raw, explanation

def envelope_adult_booking_only():
    return raw({"kind":"booking", "request_id":"r1", "age_group":"adult"})
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
def _price_raw(topic, *, service_id=None):
    return raw({"kind":"price", "request_id":"r1", "target":{"type":"service" if service_id else "topic","id":service_id or topic}})


@pytest.fixture(autouse=True)
def full_audit_off(monkeypatch):
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "0")


def _content_raw(text: str) -> str:
    return raw(explanation(text))


def _send(client, transport, **kwargs):
    response = (post if transport == "json" else post_sse)(client, **kwargs)
    assert response.status_code == 200, response.get_data(as_text=True)
    return response.get_json() if transport == "json" else dict(sse_events(response))["ui"]


def _refs(body):
    return {item["reply_id"] for item in body["ui"]["quick_replies"]}


def _begin(client, fake, transport, sid, *, phone=False):
    fake.raw = envelope_adult_booking_only()
    first = _send(client, transport, sid=sid, request_id="book", q="Хочу записаться")
    assert len(fake.inputs) == 1
    if phone:
        first = _send(client, transport, sid=sid, request_id="name", q="Анна")
        assert len(fake.inputs) == 1
    return first


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("phone", [False, True])
def test_pending_question_gets_d2_answer_and_resumes_exact_slot(http_env, transport, phone):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = f"lead-interrupt-{transport}-{phone}"
    _begin(client, fake, transport, sid, phone=phone)
    question = "Сколько стоит классическая имплантация?"
    pending = _send(client, transport, sid=sid, request_id="question", q=question)
    assert LEAD_PENDING_ANSWER_REF in _refs(pending)
    assert len(fake.inputs) == 1

    fake.raw = _price_raw("implantation", service_id="classic")
    args = dict(sid=sid, request_id="answer", q="", ref=LEAD_PENDING_ANSWER_REF,
                ui_revision=pending["revision"])
    answered = _send(client, transport, **args)
    assert "₽" in answered["answer"]
    assert _refs(answered) == ({LEAD_RESUME_REF, LEAD_CANCEL_REF} if phone else {LEAD_RESUME_REF})
    assert answered["ui"]["buttons"] == []
    assert answered["lead_effect"]["status"] == "not_requested"
    assert fake.inputs[-1].user_message == question
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "paused"
        assert state["lead_resume_step"] == ("collecting_phone" if phone else "collecting_name")
        assert state["lead_pending_interruption_text"] == ""
        if phone:
            assert state["profile"]["name"] == "Анна"
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert saved.response.rendered_text == answered["answer"]
        assert {item.reply_id for item in saved.response.resolved.ui_plan.quick_replies} == _refs(answered)
        assert saved.response.resolved.ui_plan.buttons == ()
        pairs = store.read(SessionKey(client_id="demo", sid=sid)).state.dialogue_pairs
        assert pairs[-1].patient_text == question
        assert pairs[-1].request_id == "answer"

    assert _send(client, transport, **args) == answered
    assert len(fake.inputs) == 2
    conflict = (post if transport == "json" else post_sse)(
        client, **{**args, "ref": LEAD_CANCEL_REF}
    )
    if transport == "json":
        assert conflict.status_code == 409
    else:
        assert "error" in dict(sse_events(conflict)) and "ui" not in dict(sse_events(conflict))
    resumed = _send(client, transport, sid=sid, request_id="resume", q="",
                    ref=LEAD_RESUME_REF, ui_revision=answered["revision"])
    assert "телефон" in resumed["answer"].lower() if phone else "обращ" in resumed["answer"].lower()
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == ("collecting_phone" if phone else "collecting_name")


def test_pending_question_privacy_and_paused_followup_keep_exit(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-private"
    _begin(client, fake, "json", sid, phone=True)
    pending = _send(client, "json", sid=sid, request_id="question",
                    q="Меня зовут Анна, мой номер +7 999 123-45-67. Сколько стоит имплантация?")
    fake.raw = _content_raw("О цене имплантации расскажем по материалам клиники.")
    answer = _send(client, "json", sid=sid, request_id="answer", q="",
                   ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    safe = fake.inputs[-1].user_message
    assert "Сколько стоит" in safe
    assert "Анна" not in safe and "999" not in safe
    assert _refs(answer) == {LEAD_RESUME_REF, LEAD_CANCEL_REF}
    with D2DialogueStore(db) as store:
        record = store.read(SessionKey(client_id="demo", sid=sid))
        assert "Анна" not in record.model_dump_json()
        assert "79991234567" not in re.sub(r"\D", "", record.model_dump_json())
        assert store.read_latest_completion(SessionKey(client_id="demo", sid=sid)).response.resolved.textual_cta_block is None
    assert post(client, sid=sid, request_id="name-while-paused", q="Анна").status_code != 200
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        assert mem_get(sid)["lead_intent"] == "paused"
    fake.raw = _content_raw("Ещё одно пояснение по вопросу.")
    followup = _send(client, "json", sid=sid, request_id="followup", q="А что дальше?")
    assert _refs(followup) == {LEAD_RESUME_REF, LEAD_CANCEL_REF}
    assert followup["ui"]["buttons"] == []
    cancelled = _send(client, "json", sid=sid, request_id="cancel", q="",
                      ref=LEAD_CANCEL_REF, ui_revision=followup["revision"])
    assert LEAD_RESUME_REF not in _refs(cancelled)
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "none"
        assert "name" not in state["profile"]


def test_privacy_only_pending_question_fails_without_provider_or_state_loss(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-only-pii"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="+7 999 123-45-67")
    response = post(client, sid=sid, request_id="answer", q="",
                    ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    assert response.status_code != 200
    assert len(fake.inputs) == 1
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_name"
        assert state["lead_pending_interruption_text"]


def test_postcommit_pause_failure_replays_and_repairs_without_second_provider(http_env, monkeypatch):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-repair"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Как проходит имплантация?")
    fake.raw = _content_raw("Описываю ход имплантации по материалам клиники.")
    import core.d2_lead_bridge as bridge
    original = bridge.complete_lead_pending_answer_pause
    calls = 0

    def fail_once(session_id, *, expected_source_revision):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("postcommit pause interrupted")
        return original(session_id, expected_source_revision=expected_source_revision)

    monkeypatch.setattr(bridge, "complete_lead_pending_answer_pause", fail_once)
    args = dict(sid=sid, request_id="answer", q="", ref=LEAD_PENDING_ANSWER_REF,
                ui_revision=pending["revision"])
    assert post(client, **args).status_code == 503
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        assert mem_get(sid)["lead_intent"] == "collecting_name"
    replay = _send(client, "json", **args)
    assert _refs(replay) == {LEAD_RESUME_REF}
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        assert mem_get(sid)["lead_intent"] == "paused"


def test_next_resume_click_repairs_postcommit_gap_without_replay(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-repair-on-click"
    _begin(client, fake, "json", sid, phone=True)
    pending = _send(client, "json", sid=sid, request_id="question", q="Как проходит имплантация?")
    fake.raw = _content_raw("Описываю ход имплантации по материалам клиники.")
    import core.d2_lead_bridge as bridge
    original = bridge.complete_lead_pending_answer_pause
    calls = 0

    def fail_once(session_id, *, expected_source_revision):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("postcommit pause interrupted")
        return original(session_id, expected_source_revision=expected_source_revision)

    monkeypatch.setattr(bridge, "complete_lead_pending_answer_pause", fail_once)
    assert post(client, sid=sid, request_id="answer", q="",
                ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"]).status_code == 503
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert LEAD_RESUME_REF in {item.reply_id for item in saved.response.ui_projection.quick_replies}
    resumed = _send(client, "json", sid=sid, request_id="resume", q="",
                    ref=LEAD_RESUME_REF, ui_revision=saved.committed_revision)
    assert "телефон" in resumed["answer"].lower()
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_phone"
        assert state["profile"]["name"] == "Анна"


def test_replay_old_answer_cannot_consume_new_pending_question(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-two-pending-questions"
    _begin(client, fake, "json", sid)
    first_question = _send(
        client, "json", sid=sid, request_id="question-a", q="Как проходит имплантация?",
    )
    fake.raw = _content_raw("Рассказываю об имплантации по материалам клиники.")
    first_args = dict(
        sid=sid, request_id="answer-a", q="", ref=LEAD_PENDING_ANSWER_REF,
        ui_revision=first_question["revision"],
    )
    first_answer = _send(client, "json", **first_args)
    _send(
        client, "json", sid=sid, request_id="resume-a", q="",
        ref=LEAD_RESUME_REF, ui_revision=first_answer["revision"],
    )
    second_question = _send(
        client, "json", sid=sid, request_id="question-b", q="Как ухаживать за имплантом?",
    )
    assert LEAD_PENDING_ANSWER_REF in _refs(second_question)
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_name"
        assert state["lead_pending_interruption_text"] == "Как ухаживать за имплантом?"
        assert state["lead_pending_interruption_source_revision"] == second_question["revision"]

    assert _send(client, "json", **first_args) == first_answer
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_name"
        assert state["lead_pending_interruption_text"] == "Как ухаживать за имплантом?"
        assert state["lead_pending_interruption_source_revision"] == second_question["revision"]

    fake.raw = _content_raw("Рассказываю об уходе по материалам клиники.")
    second_answer = _send(
        client, "json", sid=sid, request_id="answer-b", q="",
        ref=LEAD_PENDING_ANSWER_REF, ui_revision=second_question["revision"],
    )
    assert _refs(second_answer) == {LEAD_RESUME_REF}
    assert fake.inputs[-1].user_message == "Как ухаживать за имплантом?"


def test_stale_and_forged_pending_clicks_fail_before_provider(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-boundaries"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Что входит?")
    for request_id, ref, revision in (
        ("stale", LEAD_PENDING_ANSWER_REF, pending["revision"] - 1),
        ("forged", "lead:pending:unknown", pending["revision"]),
    ):
        assert post(client, sid=sid, request_id=request_id, q="", ref=ref,
                    ui_revision=revision).status_code == 400
    assert len(fake.inputs) == 1


def test_failed_d2_commit_keeps_pending_question_and_slot(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-commit-failure"
    _begin(client, fake, "json", sid, phone=True)
    pending = _send(client, "json", sid=sid, request_id="question", q="А сколько стоит имплантация?")
    fake.raw = _price_raw("implantation", service_id="classic")
    original = D2DialogueStore.complete

    def fail_answer(self, *args, **kwargs):
        if kwargs["completion"].request_id == "answer":
            raise RuntimeError("commit refused")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(D2DialogueStore, "complete", fail_answer)
    response = post(client, sid=sid, request_id="answer", q="",
                    ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    assert response.status_code == 503
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_phone"
        assert state["profile"]["name"] == "Анна"
        assert state["lead_pending_interruption_text"] == "А сколько стоит имплантация?"
    with D2DialogueStore(db) as store:
        latest = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert latest.request_id == "question"


def test_provider_failure_keeps_pending_question_and_slot(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-provider-failure"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Что входит в лечение?")
    fake.raw = "{invalid"
    failed = post(client, sid=sid, request_id="answer", q="",
                  ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    assert failed.status_code != 200
    with session_client_scope("demo"):
        state = mem_get(sid)
        assert state["lead_intent"] == "collecting_name"
        assert state["lead_pending_interruption_text"] == "Что входит в лечение?"
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid=sid)).request_id == "question"


def test_sse_framing_failure_replays_committed_answer_and_pause(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-frame-failure"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Как проходит лечение?")
    fake.raw = _content_raw("Рассказываю о лечении по материалам клиники.")
    import app

    def fail_framing(*_args, **_kwargs):
        raise RuntimeError("transport framing failed")

    args = dict(sid=sid, request_id="answer", q="", ref=LEAD_PENDING_ANSWER_REF,
                ui_revision=pending["revision"])
    with monkeypatch.context() as patch:
        patch.setattr(app, "_sse_typing_line", fail_framing)
        events = dict(sse_events(post_sse(client, **args)))
    assert "error" in events and "ui" not in events
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert saved.request_id == "answer"
    with session_client_scope("demo"):
        assert mem_get(sid)["lead_intent"] == "paused"
    replay = _send(client, "json", **args)
    assert _refs(replay) == {LEAD_RESUME_REF}
    assert len(fake.inputs) == 2


def test_tenant_bound_pending_answer_cannot_use_foreign_session(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-foreign"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Сколько стоит?")
    assert post(client, sid=sid, request_id="foreign", q="",
                client_id="nikadent", ref=LEAD_PENDING_ANSWER_REF,
                ui_revision=pending["revision"]).status_code != 200
    assert len(fake.inputs) == 1


def test_hidden_volume_choices_are_not_remembered_as_shown(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    sid = "lead-volume-hidden"
    _begin(client, fake, "json", sid)
    pending = _send(client, "json", sid=sid, request_id="question", q="Сколько стоит имплантация?")
    fake.raw = _price_raw("implantation")
    answer = _send(client, "json", sid=sid, request_id="answer", q="",
                   ref=LEAD_PENDING_ANSWER_REF, ui_revision=pending["revision"])
    assert _refs(answer) == {LEAD_RESUME_REF}
    with D2DialogueStore(db) as store:
        state = store.read(SessionKey(client_id="demo", sid=sid)).state
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert saved.response.ui_projection.buttons == ()
        assert {q.reply_id for q in saved.response.ui_projection.quick_replies} == {LEAD_RESUME_REF}
        assert state.accumulated_shown_ids.shown_service_option_ids == ()
    rejected = post(client, sid=sid, request_id="hidden-volume", q="",
                    ref="volume:implantation:one_tooth", ui_revision=answer["revision"])
    assert rejected.status_code == 400
    assert len(fake.inputs) == 2
    with session_client_scope("demo"):
        assert mem_get(sid)["lead_intent"] == "paused"
