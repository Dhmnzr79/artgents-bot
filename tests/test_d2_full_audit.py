"""Opt-in local transcript of the real D2 HTTP turn, with fake providers only."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_full_audit import full_audit, full_audit_path
from core.d2_live_provider import D2HttpProvider
from tests.d1r_envelope_fixtures import envelope_adult_booking_only
from tests.test_d2_http_contract import (
    FakeProvider, _mixed_price_content_policy_raw, http_env, post, post_sse, sse_events,
)
from tests.test_d2_rec2_content_http import _content_raw
from tests.test_d2_ui_b12_scenarios import PAIN_FOLLOW, _content_pain_raw


def _rows() -> list[dict]:
    return [json.loads(line) for line in full_audit_path().read_text(encoding="utf-8").splitlines()]


def _trace_for(rows: list[dict], request_id: str) -> list[dict]:
    start = next(
        row for row in rows
        if row["event"] == "http_request"
        and json.loads(row["body"]).get("request_id") == request_id
    )
    return [row for row in rows if row["trace_id"] == start["trace_id"]]


def test_full_audit_is_opt_in_and_production_disabled(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    use_provider(FakeProvider(_content_raw(text="Точный ответ.")))
    monkeypatch.delenv("D2_FULL_AUDIT_LOG", raising=False)
    assert post(client, sid="audit-off", request_id="off").status_code == 200
    assert not full_audit_path().exists()

    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    monkeypatch.setenv("APP_ENV", "prod")
    assert post(client, sid="audit-prod", request_id="prod").status_code == 200
    assert not full_audit_path().exists()

    monkeypatch.setenv("APP_ENV", "local")
    assert post(client, sid="audit-on", request_id="on").status_code == 200
    assert full_audit_path().exists()


def test_json_and_sse_capture_exact_frozen_answer_provider_and_wire(http_env, monkeypatch):
    client, _db, _use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    raw = _content_raw(text="Живой ответ про анестезию.", ref="implantation__faq__pain.md")
    calls = []

    def transport(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
            model="offline-model", usage={"prompt_tokens": 12, "completion_tokens": 8},
        )

    monkeypatch.setattr(
        "core.d2_http_adapter.D2HttpProvider",
        lambda: D2HttpProvider(model="offline-model", transport=transport),
    )
    first = post(client, sid="audit-json", request_id="json", q="Как делают анестезию?")
    assert first.status_code == 200
    streamed = post_sse(client, sid="audit-sse", request_id="sse", q="Как делают анестезию?")
    events = sse_events(streamed)
    assert events[-1][0] == "done"
    sse_payload = next(payload for kind, payload in events if kind == "ui")
    assert sse_payload["answer"] == first.get_json()["answer"]
    assert len(calls) == 2

    rows = _rows()
    for request_id, expected in (("json", first.get_json()), ("sse", sse_payload)):
        trace = _trace_for(rows, request_id)
        names = {row["event"] for row in trace}
        assert {
            "http_request", "validated_request", "session_before", "provider_input",
            "provider_messages", "provider_response", "raw_model_response",
            "parsed_envelope", "effective_envelope", "materialized_response",
            "commit_confirmed", "adapter_result",
        } <= names
        result_event = "http_result" if request_id == "json" else "sse_result_ready"
        assert result_event in names
        assert next(row for row in trace if row["event"] == "raw_model_response")["raw"] == raw
        assert next(row for row in trace if row["event"] == result_event)["payload"] == expected
        assert json.loads(next(row for row in trace if row["event"] == "http_request")["body"])["q"] == "Как делают анестезию?"
        messages = next(row for row in trace if row["event"] == "provider_messages")
        assert "APPROVED_MD_CORPUS" in messages["system"]["content"]
        assert "USER_MESSAGE" in messages["user"]["content"]
    sse_trace = _trace_for(rows, "sse")
    chunks = [row["chunk"] for row in sse_trace if row["event"] == "sse_chunk"]
    assert any(chunk.startswith("event: status") for chunk in chunks)
    assert any(chunk.startswith("event: ui") and sse_payload["answer"] in chunk for chunk in chunks)
    assert any(chunk.startswith("event: done") for chunk in chunks)


def test_typed_click_and_replay_are_visible_without_fake_provider_call(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_pain_raw()))
    first = post(client, sid="audit-click", request_id="first", q="Боюсь боли")
    assert first.status_code == 200
    chosen = post(
        client, sid="audit-click", request_id="clicked", q="",
        ref=PAIN_FOLLOW, ui_revision=first.get_json()["revision"],
    )
    assert chosen.status_code == 200
    assert len(fake.inputs) == 2
    replay = post(
        client, sid="audit-click", request_id="clicked", q="",
        ref=PAIN_FOLLOW, ui_revision=first.get_json()["revision"],
    )
    assert replay.get_json() == chosen.get_json()
    assert len(fake.inputs) == 2

    rows = _rows()
    click_trace = _trace_for(rows, "clicked")
    # The same request body appears on a replay, but has a different attempt ID.
    trace_ids = {
        row["trace_id"] for row in rows
        if row["event"] == "http_request"
        and json.loads(row["body"]).get("request_id") == "clicked"
    }
    assert len(trace_ids) == 2
    assert next(row for row in click_trace if row["event"] == "ui_binding")["selected_ui_ref"]["reply_id"] == PAIN_FOLLOW
    assert any(row["event"] == "parsed_envelope" for row in click_trace)
    replay_trace = [row for row in rows if row["trace_id"] != click_trace[0]["trace_id"] and row["trace_id"] in trace_ids]
    assert any(row["event"] == "replay" for row in replay_trace)
    assert not any(row["event"] == "provider_input" for row in replay_trace)


def test_mixed_price_content_policy_has_one_frozen_trace(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_mixed_price_content_policy_raw()))
    response = post(client, sid="audit-mixed", request_id="mixed", q="Цена и условия лечения")
    assert response.status_code == 200
    assert len(fake.inputs) == 1
    trace = _trace_for(_rows(), "mixed")
    frozen = next(row for row in trace if row["event"] == "materialized_response")["response"]
    assert [part["kind"] for part in frozen["resolved"]["d2_request_parts"]] == [
        "price", "content", "clinic_policy",
    ]
    assert frozen["resolved"]["d2_price_block"] is not None
    assert frozen["resolved"]["information_blocks"]
    assert frozen["rendered_text"] == response.get_json()["answer"]
    assert next(row for row in trace if row["event"] == "http_result")["payload"]["ui"] == response.get_json()["ui"]


def test_same_sid_in_two_tenants_keeps_attempt_traces_separate(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_raw(text="Ответ без источника.")))
    for tenant in ("demo", "nikadent"):
        assert post(
            client, sid="audit-shared-sid", request_id=f"{tenant}-r1",
            client_id=tenant, q="Одинаковый вопрос",
        ).status_code == 200
    assert len(fake.inputs) == 2
    rows = _rows()
    first = _trace_for(rows, "demo-r1")
    second = _trace_for(rows, "nikadent-r1")
    assert first[0]["trace_id"] != second[0]["trace_id"]
    assert next(row for row in first if row["event"] == "validated_request")["client_id"] == "demo"
    assert next(row for row in second if row["event"] == "validated_request")["client_id"] == "nikadent"
    assert next(row for row in first if row["event"] == "http_result")["payload"]["client_id"] == "demo"
    assert next(row for row in second if row["event"] == "http_result")["payload"]["client_id"] == "nikadent"


def test_interleaved_sse_attempts_do_not_mix_tenants_or_delivery(http_env, monkeypatch):
    import app

    _client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_raw(text="Отдельный ответ.")))
    responses = []
    for tenant in ("demo", "nikadent"):
        with app.app.test_request_context("/ask/stream", method="POST", json={
            "client_id": tenant, "sid": f"audit-interleaved-{tenant}",
            "request_id": "same", "q": "Одинаковый вопрос",
        }):
            responses.append(app.ask_stream())
    streams = [iter(response.response) for response in responses]
    assert all(next(stream).startswith("event: status") for stream in streams)
    assert next(streams[0]).startswith("event: typing")
    responses[0].close()
    assert next(streams[1]).startswith("event: typing")
    assert next(streams[1]).startswith("event: ui")
    assert next(streams[1]).startswith("event: done")
    responses[1].close()
    assert len(fake.inputs) == 2

    rows = _rows()
    starts = [row for row in rows if row["event"] == "http_request"]
    assert len(starts) == 2 and starts[0]["trace_id"] != starts[1]["trace_id"]
    for start in starts:
        trace = [row for row in rows if row["trace_id"] == start["trace_id"]]
        tenant = json.loads(start["body"])["client_id"]
        assert next(row for row in trace if row["event"] == "validated_request")["client_id"] == tenant
        assert next(row for row in trace if row["event"] == "sse_result_ready")["payload"]["client_id"] == tenant
        chunks = [row["chunk"] for row in trace if row["event"] == "sse_chunk"]
        assert any(chunk.startswith("event: status") for chunk in chunks)
        assert (tenant == "nikadent") == any(chunk.startswith("event: ui") for chunk in chunks)


def test_lead_turns_keep_synthetic_name_phone_and_effect_without_new_model(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    assert post(client, sid="audit-lead", request_id="book", q="Хочу записаться").status_code == 200
    assert post(client, sid="audit-lead", request_id="name", q="Анна").status_code == 200
    phone = post(client, sid="audit-lead", request_id="phone", q="+7 999 123 45 67")
    assert phone.status_code == 200
    assert len(fake.inputs) == 1
    rows = _rows()
    name_trace = _trace_for(rows, "name")
    phone_trace = _trace_for(rows, "phone")
    assert json.loads(next(row for row in name_trace if row["event"] == "http_request")["body"])["q"] == "Анна"
    assert json.loads(next(row for row in phone_trace if row["event"] == "http_request")["body"])["q"] == "+7 999 123 45 67"
    assert not any(row["event"] == "provider_input" for row in name_trace + phone_trace)
    assert any(row["event"] == "materialized_response" for row in phone_trace)
    assert any(row["event"] == "effect_result" and row["status"] == "demo_stub" for row in phone_trace)
    name_before = next(row for row in name_trace if row["event"] == "lead_session_before")["row"]
    name_after = next(row for row in name_trace if row["event"] == "lead_session_after")["row"]
    phone_before = next(row for row in phone_trace if row["event"] == "lead_session_before")["row"]
    phone_after = next(row for row in phone_trace if row["event"] == "lead_session_after")["row"]
    assert name_before != name_after
    assert "Анна" in name_after[0]
    assert phone_before == name_after
    assert phone_after != phone_before
    # The completed booking clears lead PII from the live session. The phone
    # remains visible in this opt-in trace's ingress, not in the final row.
    assert "+7 999 123 45 67" not in phone_after[0]
    assert next(row for row in phone_trace if row["event"] == "lead_session_after")["phase"] == "success"


def test_writer_failure_does_not_change_http_result_and_credentials_are_scrubbed(
    http_env, monkeypatch, tmp_path,
):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    full_audit(
        "sample", trace_id="audit-secret", body={"api_key": "PRIVATE_KEY", "q": "Меня зовут Анна"},
        raw="Bearer TOPSECRET123", basic="authorization: Basic ZXhhbXBsZQ==",
        password="password: two words secret value",
        refresh="refresh_token: REFRESH123", plain_token="token: PLAINTOKEN123",
        raw_json='{"q":"Вопрос от Анны","password":"two words","access_token":"TOKEN123","refresh_token":"JSONREFRESH123"}',
    )
    content = full_audit_path().read_text(encoding="utf-8")
    assert "Меня зовут Анна" in content
    for secret in (
        "PRIVATE_KEY", "TOPSECRET123", "ZXhhbXBsZQ==", "two words",
        "TOKEN123", "REFRESH123", "PLAINTOKEN123", "JSONREFRESH123",
    ):
        assert secret not in content
    assert "Вопрос от Анны" in content

    class BrokenSerialization:
        def model_dump(self, *, mode):
            raise RuntimeError("synthetic serialization failure")

    full_audit("broken_serialization", trace_id="audit-secret", value=BrokenSerialization())

    fake = use_provider(FakeProvider(_content_raw(text="Сохранённый ответ.")))
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("core.d2_full_audit.full_audit_path", lambda: blocked / "audit.jsonl")
    response = post(client, sid="audit-sink-failure", request_id="sink")
    assert response.status_code == 200
    assert "Сохранённый ответ." in response.get_json()["answer"]
    assert len(fake.inputs) == 1


def test_unknown_request_field_does_not_expose_token_in_raw_http_audit(http_env, monkeypatch):
    client, _db, _use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    response = client.post("/ask", json={
        "client_id": "demo", "sid": "audit-token", "request_id": "token-invalid",
        "q": "Вопрос от Анны", "refresh_token": "HTTP_REFRESH_SECRET",
    })
    assert response.status_code == 400
    trace = _trace_for(_rows(), "token-invalid")
    body = json.loads(next(row for row in trace if row["event"] == "http_request")["body"])
    assert body["q"] == "Вопрос от Анны"
    assert body["refresh_token"] == "[REDACTED_CREDENTIAL]"
    assert "HTTP_REFRESH_SECRET" not in full_audit_path().read_text(encoding="utf-8")


def test_parser_failure_has_raw_model_exception_and_no_final_answer(http_env, monkeypatch):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    use_provider(FakeProvider("BROKEN_MODEL_OUTPUT{"))
    response = post(client, sid="audit-invalid", request_id="invalid", q="Вопрос")
    assert response.status_code == 400
    assert "answer" not in response.get_json()
    trace = _trace_for(_rows(), "invalid")
    assert any(row["event"] == "raw_model_response" and row["raw"] == "BROKEN_MODEL_OUTPUT{" for row in trace)
    assert any(row["event"] == "exception" and "parse_production_envelope_json" in row["traceback"] for row in trace)
    assert not any(row["event"] == "commit_confirmed" for row in trace)
    assert next(row for row in trace if row["event"] == "lead_session_before")["row"] is None
    after = next(row for row in trace if row["event"] == "lead_session_after")
    assert after["phase"] == "rollback" and after["row"] is None


def test_broken_audit_sink_preserves_original_error_and_lead_rollback(
    http_env, monkeypatch, tmp_path,
):
    from core.d2_http_adapter import run_d2_ask_json
    from session import capture_lead_session_row, session_client_scope, set_lead_pending_name

    _client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_raw(text="Не должен вызываться.")))
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("core.d2_full_audit.full_audit_path", lambda: blocked / "audit.jsonl")
    original = RuntimeError("synthetic turn failure")

    def mutate_then_fail(**kwargs):
        set_lead_pending_name(kwargs["session_key"].sid, "Анна")
        raise original

    monkeypatch.setattr("core.d2_http_adapter.run_d2_dialogue_turn", mutate_then_fail)
    with session_client_scope("demo"):
        assert capture_lead_session_row("audit-rollback") is None
        with pytest.raises(RuntimeError) as caught:
            run_d2_ask_json({"sid": "audit-rollback", "request_id": "rollback", "q": "Вопрос"}, client_id="demo")
        assert caught.value is original
        assert capture_lead_session_row("audit-rollback") is None
    assert not fake.inputs


def test_broken_audit_sink_does_not_duplicate_lead_effect_or_replay(
    http_env, monkeypatch, tmp_path,
):
    client, _db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(envelope_adult_booking_only()))
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("core.d2_full_audit.full_audit_path", lambda: blocked / "audit.jsonl")
    effect_updates = []
    original_update = D2DialogueStore.update_lead_effect

    def counted_update(self, *args, **kwargs):
        effect_updates.append((args, kwargs))
        return original_update(self, *args, **kwargs)

    monkeypatch.setattr(D2DialogueStore, "update_lead_effect", counted_update)
    assert post(client, sid="audit-sink-lead", request_id="book", q="Хочу записаться").status_code == 200
    assert post(client, sid="audit-sink-lead", request_id="name", q="Анна").status_code == 200
    phone = post(client, sid="audit-sink-lead", request_id="phone", q="+7 999 123 45 67")
    replay = post(client, sid="audit-sink-lead", request_id="phone", q="+7 999 123 45 67")
    assert phone.status_code == replay.status_code == 200
    assert replay.get_json() == phone.get_json()
    assert phone.get_json()["lead_effect"]["status"] == "demo_stub"
    assert len(effect_updates) == 1
    assert len(fake.inputs) == 1


def test_sse_disconnect_distinguishes_before_work_from_after_commit(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_raw(text="Сохранённый ответ.")))

    before = post_sse(client, sid="audit-before-close", request_id="before", buffered=False)
    assert next(before.response).decode().startswith("event: status\n")
    before.close()
    assert len(fake.inputs) == 0

    after = post_sse(client, sid="audit-after-close", request_id="after", buffered=False)
    assert next(after.response).decode().startswith("event: status\n")
    assert next(after.response).decode().startswith("event: typing\n")
    after.close()
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="audit-before-close")) is None
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="audit-after-close")) is not None

    rows = _rows()
    before_trace = _trace_for(rows, "before")
    after_trace = _trace_for(rows, "after")
    assert not any(row["event"] == "provider_input" for row in before_trace)
    assert not any(row["event"] == "commit_confirmed" for row in before_trace)
    assert any(row["event"] == "commit_confirmed" for row in after_trace)
    assert not any(row["event"] == "sse_chunk" and row["chunk"].startswith("event: ui") for row in after_trace)
    assert any(
        row["event"] == "diagnostic"
        and row["diagnostic"]["event"] == "stream_disconnected"
        and row["diagnostic"]["commit_state"] == "confirmed"
        for row in after_trace
    )


def test_broken_audit_sink_does_not_change_sse_close_or_commit(http_env, monkeypatch, tmp_path):
    client, db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    fake = use_provider(FakeProvider(_content_raw(text="Сохранённый ответ.")))
    blocked = tmp_path / "not_a_directory"
    blocked.write_text("occupied", encoding="utf-8")
    monkeypatch.setattr("core.d2_full_audit.full_audit_path", lambda: blocked / "audit.jsonl")

    before = post_sse(client, sid="audit-sink-before", request_id="before", buffered=False)
    assert next(before.response).decode().startswith("event: status\n")
    before.close()
    assert not fake.inputs

    after = post_sse(client, sid="audit-sink-after", request_id="after", buffered=False)
    assert next(after.response).decode().startswith("event: status\n")
    assert next(after.response).decode().startswith("event: typing\n")
    after.close()
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="audit-sink-before")) is None
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="audit-sink-after")) is not None


def test_sse_framing_failure_after_commit_keeps_saved_answer(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    use_provider(FakeProvider(_content_raw(text="Сохранённый ответ.")))

    def broken_typing(_phase):
        raise RuntimeError("synthetic framing failure")

    monkeypatch.setattr("app._sse_typing_line", broken_typing)
    response = post_sse(client, sid="audit-framing", request_id="framing")
    assert [kind for kind, _payload in sse_events(response)] == ["status", "error"]
    with D2DialogueStore(db) as store:
        assert store.read_latest_completion(SessionKey(client_id="demo", sid="audit-framing")) is not None
    trace = _trace_for(_rows(), "framing")
    assert any(row["event"] == "commit_confirmed" for row in trace)
    assert any(row["event"] == "exception" and row["stage"] == "/ask/stream/framing" for row in trace)
    assert any(row["event"] == "sse_chunk" and row["chunk"].startswith("event: error") for row in trace)
