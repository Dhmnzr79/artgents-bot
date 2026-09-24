"""The opt-in local transcript contains enough evidence to audit one D2 turn."""

from __future__ import annotations

import json
from types import SimpleNamespace

from core.d2_full_audit import full_audit, full_audit_path, full_audit_trace
from core.d2_live_provider import D2HttpProvider
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_r3_free_dialogue import _raw


def _rows():
    return [json.loads(line) for line in full_audit_path().read_text(encoding="utf-8").splitlines()]


def test_full_audit_is_opt_in_and_correlates_a_complete_dialogue(http_env, monkeypatch):
    client, _db, use_provider, _tmp_path = http_env
    raw = _raw(kind="content", text="Живой ответ по материалам клиники.")
    use_provider(FakeProvider(raw))
    monkeypatch.delenv("D2_FULL_AUDIT_LOG", raising=False)
    assert post(client, sid="audit-off", request_id="off").status_code == 200
    assert not full_audit_path().exists()

    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    response = post_sse(client, sid="audit-on", request_id="on", q="Что происходит после установки?")
    assert sse_events(response)[-1][0] == "done"
    trace_id = response.headers["X-D2-Trace-Id"]
    rows = [row for row in _rows() if row["trace_id"] == trace_id]
    by_event = {row["event"]: row for row in rows}
    assert by_event["http_request"]["body"]["q"] == "Что происходит после установки?"
    assert by_event["raw_model_response"]["raw"] == raw
    assert by_event["parsed_envelope"]["envelope"]["route"] == "ANSWER"
    assert by_event["focus_binding"]["content_lookup"] is True
    assert by_event["http_result"]["payload"]["answer"] == response_data_answer(response)


def response_data_answer(response):
    return next(payload["answer"] for kind, payload in sse_events(response) if kind == "ui")


def test_full_audit_keeps_raw_failure_and_traceback_out_of_public_logs(http_env, monkeypatch, caplog):
    client, _db, use_provider, _tmp_path = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    use_provider(FakeProvider("BROKEN_MODEL_OUTPUT{"))
    response = post(client, sid="private-session", request_id="failed", q="Мой вопрос")
    assert response.status_code == 503
    assert "BROKEN_MODEL_OUTPUT" not in str(response.get_json())
    rows = [row for row in _rows() if row["trace_id"] == response.headers["X-D2-Trace-Id"]]
    assert any(row["event"] == "raw_model_response" and row["raw"] == "BROKEN_MODEL_OUTPUT{" for row in rows)
    assert any(row["event"] == "exception" and "parse_production_envelope_json" in row["traceback"]
               for row in rows)
    assert any(row["event"] == "http_error" and row["error"]["stage"] == "parser" for row in rows)
    assert all("Мой вопрос" not in str(getattr(record, "extra_data", {})) for record in caplog.records)

    stream = post_sse(client, sid="private-stream", request_id="failed-sse", q="Другой вопрос")
    assert [kind for kind, _payload in sse_events(stream)] == ["status", "error"]
    assert "BROKEN_MODEL_OUTPUT" not in str(sse_events(stream)[-1][1])
    stream_rows = [row for row in _rows() if row["trace_id"] == stream.headers["X-D2-Trace-Id"]]
    assert any(row["event"] == "raw_model_response" and row["raw"] == "BROKEN_MODEL_OUTPUT{"
               for row in stream_rows)
    assert any(row["event"] == "http_error" and row["error"]["stage"] == "parser"
               for row in stream_rows)


def test_full_audit_captures_the_actual_provider_messages(http_env, monkeypatch):
    client, _db, use_provider, _tmp_path = http_env
    raw = _raw(kind="content", text="Ответ.")
    fake = use_provider(FakeProvider(raw))
    assert post(client, sid="prompt-input", request_id="first").status_code == 200
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=raw))],
        model="offline-model", usage={"prompt_tokens": 123},
    )
    with full_audit_trace("prompt-test"):
        assert D2HttpProvider(transport=lambda **_kwargs: response).generate(fake.inputs[0]) == raw
    rows = [row for row in _rows() if row["trace_id"] == "prompt-test"]
    messages = next(row for row in rows if row["event"] == "provider_messages")
    assert "APPROVED_MD_CORPUS" in messages["system"]["content"]
    assert "USER_MESSAGE" in messages["user"]["content"]
    assert any(row["event"] == "provider_response" and row["raw"] == raw for row in rows)


def test_full_audit_redacts_credentials_and_is_off_in_prod(http_env, monkeypatch):
    _client, _db, _use_provider, _tmp_path = http_env
    monkeypatch.setenv("D2_FULL_AUDIT_LOG", "1")
    with full_audit_trace("test-credentials"):
        full_audit("sample", body={"api_key": "PRIVATE_KEY", "q": "Bearer TOPSECRET123"},
                   raw='{"api_key": "EMBEDDED_KEY"}')
    content = full_audit_path().read_text(encoding="utf-8")
    assert all(item not in content for item in ("PRIVATE_KEY", "TOPSECRET123", "EMBEDDED_KEY"))
    assert "[REDACTED_CREDENTIAL]" in content
    monkeypatch.setenv("APP_ENV", "prod")
    with full_audit_trace("test-prod"):
        full_audit("sample", body="should not appear")
    assert "test-prod" not in full_audit_path().read_text(encoding="utf-8")
