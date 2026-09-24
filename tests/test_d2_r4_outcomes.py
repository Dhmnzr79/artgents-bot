"""R4: real HTTP adapters and temporary SQLite, with no provider network."""

from __future__ import annotations

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore, D2RequestInProgress
from core.d2_tenant_snapshot import D2TenantSnapshotError
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.d1r_envelope_fixtures import envelope_clinic_policy_only
from tests.test_d2_r3_free_dialogue import _raw


def _assert_safe(payload, *, stage, code, committed=False):
    assert payload["stage"] == stage
    assert payload["error"] == code
    assert payload["committed"] is committed
    assert payload["category"] in {"validation", "conflict", "provider", "protocol", "state", "storage", "unexpected"}
    assert payload["message"] == "Не удалось обработать запрос. Попробуйте ещё раз."
    assert "RAW_SECRET_MARKER" not in str(payload)
    assert "sid" not in payload and "request_id" not in payload


def test_parser_error_is_typed_and_preserves_state_on_json_and_sse(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider("RAW_SECRET_MARKER{"))
    json_response = post(client, sid="parser-json", request_id="same")
    assert json_response.status_code == 503
    json_error = json_response.get_json()
    _assert_safe(json_error, stage="parser", code="parser_invalid_envelope")
    stream_response = post_sse(client, sid="parser-sse", request_id="same")
    assert stream_response.status_code == 200
    events = sse_events(stream_response)
    assert [kind for kind, _ in events] == ["status", "error"]
    _assert_safe(events[-1][1], stage="parser", code="parser_invalid_envelope")
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="parser-json")) is None
        assert store.read(SessionKey(client_id="demo", sid="parser-sse")) is None
    fake.raw = envelope_clinic_policy_only("no_pediatric_dentistry")
    assert post(client, sid="parser-json", request_id="same").status_code == 200
    assert len(fake.inputs) == 3


def test_trace_header_finds_safe_internal_reason_for_json_and_sse(http_env, caplog):
    client, _db, use_provider, _ = http_env
    use_provider(FakeProvider("RAW_SECRET_MARKER{"))

    json_response = post(client, sid="private-session", request_id="json-trace")
    json_trace = json_response.headers["X-D2-Trace-Id"]
    assert len(json_trace) == 32
    _assert_safe(json_response.get_json(), stage="parser", code="parser_invalid_envelope")

    stream_response = post_sse(client, sid="private-session", request_id="sse-trace")
    stream_trace = stream_response.headers["X-D2-Trace-Id"]
    assert len(stream_trace) == 32 and stream_trace != json_trace
    assert sse_events(stream_response)[-1][0] == "error"

    records = [getattr(record, "extra_data", {}) for record in caplog.records]
    json_rows = [row for row in records if row.get("trace_id") == json_trace]
    stream_rows = [row for row in records if row.get("trace_id") == stream_trace]
    assert any(row.get("msg") == "http_request" or row.get("path") == "/ask"
               for row in json_rows)
    assert any(row.get("diagnostic_code") == "json_invalid" and row.get("stage") == "parser"
               for row in json_rows)
    assert any(row.get("diagnostic_code") == "json_invalid" and row.get("stage") == "parser"
               for row in stream_rows)
    assert any(str(row.get("diagnostic_site", "")).startswith(
        "core/one_call_envelope_protocol.py:"
    ) for row in stream_rows)
    assert any(row.get("outcome") == "error" for row in stream_rows)
    assert all("private-session" not in str(row) and "RAW_SECRET_MARKER" not in str(row)
               for row in json_rows + stream_rows)


def test_tenant_and_ui_fail_before_commit(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    bad_ui = post(client, sid="bad-ui", request_id="ui", ref="service:foreign", ui_revision=1, q="")
    assert bad_ui.status_code == 400
    _assert_safe(bad_ui.get_json(), stage="d2_gate", code="ui_action_invalid")

    import core.d2_dialogue as dialogue
    with monkeypatch.context() as patch:
        patch.setattr(dialogue, "load_d2_tenant_snapshot",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(D2TenantSnapshotError("RAW_SECRET_MARKER")))
        tenant = post(client, sid="tenant", request_id="tenant")
    assert tenant.status_code == 503
    _assert_safe(tenant.get_json(), stage="tenant_binding", code="tenant_binding_failed")
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="bad-ui")) is None
        assert store.read(SessionKey(client_id="demo", sid="tenant")) is None


def test_valid_parser_then_d2_gate_failure_is_separate(http_env, monkeypatch, caplog):
    client, db, use_provider, _ = http_env
    use_provider(FakeProvider(_raw(kind="content", text="Объяснение услуги.")))
    import core.d2_dialogue as dialogue
    with monkeypatch.context() as patch:
        patch.setattr(dialogue, "seed_d2_plan_focus",
                      lambda _binding: (_ for _ in ()).throw(ValueError("d2_experiment_resolved_topic_required")))
        response = post(client, sid="gate", request_id="gate")
    assert response.status_code == 503
    _assert_safe(response.get_json(), stage="d2_gate", code="d2_gate_rejected")
    assert "diagnostic_code" not in response.get_json()
    assert any(getattr(record, "extra_data", {}).get("diagnostic_code")
               == "d2_experiment_resolved_topic_required" for record in caplog.records)
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="gate")) is None


def test_materializer_provider_store_and_unexpected_errors_are_distinct(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    import core.d2_dialogue as dialogue
    import core.d2_http_adapter as adapter
    from core.d2_dialogue_store import D2DialogueStore

    fake = use_provider(FakeProvider(_raw(kind="content", text="Объяснение услуги.")))
    with monkeypatch.context() as patch:
        patch.setattr(dialogue, "resolve_d2_envelope_response",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        response = post(client, sid="materializer", request_id="m")
    assert response.status_code == 503
    _assert_safe(response.get_json(), stage="materializer", code="materializer_failed")

    class BrokenProvider:
        def generate(self, _request):
            raise RuntimeError("RAW_SECRET_MARKER")

    use_provider(BrokenProvider())
    provider = post(client, sid="provider", request_id="p")
    _assert_safe(provider.get_json(), stage="provider", code="provider_failed")

    use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    with monkeypatch.context() as patch:
        patch.setattr(D2DialogueStore, "complete",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        store = post(client, sid="store", request_id="s")
    _assert_safe(store.get_json(), stage="store", code="store_failed")

    with monkeypatch.context() as patch:
        patch.setattr(adapter, "run_d2_dialogue_turn",
                      lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        unexpected = post(client, sid="unexpected", request_id="u")
    _assert_safe(unexpected.get_json(), stage="d2_gate", code="unexpected_failure")
    with D2DialogueStore(db) as dialogue_store:
        for sid in ("materializer", "provider", "store", "unexpected"):
            assert dialogue_store.read(SessionKey(client_id="demo", sid=sid)) is None


def test_materializer_log_uses_only_allowlisted_internal_code(http_env, monkeypatch, caplog):
    client, _db, use_provider, _ = http_env
    use_provider(FakeProvider(_raw(kind="content", text="Объяснение услуги.")))
    import core.d2_dialogue as dialogue
    from contracts.response_plan_materialization import MaterializationContractError

    with monkeypatch.context() as patch:
        patch.setattr(dialogue, "resolve_d2_envelope_response",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(
                          MaterializationContractError("d2_content_scope_required")))
        response = post_sse(client, sid="safe-detail", request_id="same")
    events = sse_events(response)
    assert [kind for kind, _ in events] == ["status", "error"]
    _assert_safe(events[-1][1], stage="materializer", code="materializer_failed")
    assert "diagnostic_code" not in events[-1][1]
    assert any(getattr(record, "extra_data", {}).get("diagnostic_code")
               == "d2_content_scope_required" for record in caplog.records)


def test_unknown_materializer_error_logs_safe_kind_and_site(http_env, monkeypatch, caplog):
    client, _db, use_provider, _ = http_env
    use_provider(FakeProvider(_raw(kind="content", text="Объяснение услуги.")))
    import core.d2_dialogue as dialogue

    with monkeypatch.context() as patch:
        patch.setattr(dialogue, "resolve_d2_envelope_response",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        response = post(client, sid="private-session", request_id="unknown-error")
    _assert_safe(response.get_json(), stage="materializer", code="materializer_failed")
    trace_id = response.headers["X-D2-Trace-Id"]
    rows = [getattr(record, "extra_data", {}) for record in caplog.records]
    row = next(row for row in rows if row.get("trace_id") == trace_id
               and row.get("d2_outcome") == "materializer_failed")
    assert row["diagnostic_code"] == "internal_runtime_error"
    assert row["diagnostic_site"].startswith("tests/test_d2_r4_outcomes.py:")
    assert "private-session" not in str(row)
    assert "RAW_SECRET_MARKER" not in str(row)


def test_commit_time_request_in_progress_keeps_conflict_code(http_env, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    with monkeypatch.context() as patch:
        patch.setattr(D2DialogueStore, "complete",
                      lambda *_args, **_kwargs: (_ for _ in ()).throw(D2RequestInProgress("internal")))
        response = post(client, sid="commit-conflict", request_id="same")
    assert response.status_code == 409
    _assert_safe(response.get_json(), stage="store", code="request_in_progress")
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="commit-conflict")) is None


def test_sse_terminal_replay_and_safe_logs(http_env, caplog, monkeypatch):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    import app

    with monkeypatch.context() as patch:
        patch.setattr(app, "_sse_typing_line",
                      lambda _phase: (_ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        failed = sse_events(post_sse(client, sid="private-session", request_id="same"))
    assert [kind for kind, _ in failed] == ["status", "error"]
    _assert_safe(failed[-1][1], stage="transport", code="transport_failed", committed=True)
    replay = sse_events(post_sse(client, sid="private-session", request_id="same"))
    assert [kind for kind, _ in replay] == ["status", "typing", "ui", "done"]
    assert replay[-1][1] == {"outcome": "final", "committed": True}
    assert len(fake.inputs) == 1
    safe_records = [str(getattr(record, "extra_data", {})) for record in caplog.records
                    if record.getMessage() in {"d2_sse_outcome", "http_request"}]
    assert safe_records
    assert all("private-session" not in record and "RAW_SECRET_MARKER" not in record
               for record in safe_records)
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="private-session")).state.revision == 1


def test_disconnect_after_status_is_not_success_or_state_change(http_env, caplog):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(envelope_clinic_policy_only("no_pediatric_dentistry")))
    response = post_sse(client, sid="disconnect", request_id="same", buffered=False)
    assert response.status_code == 200
    assert next(response.response).decode("utf-8").startswith("event: status")
    response.close()
    assert fake.inputs == []
    with D2DialogueStore(db) as store:
        assert store.read(SessionKey(client_id="demo", sid="disconnect")) is None
    outcomes = [getattr(record, "extra_data", {}) for record in caplog.records
                if record.getMessage() == "d2_sse_outcome"]
    assert any(row.get("outcome") == "disconnect" and row.get("committed") is False
               for row in outcomes)


def test_origin_rejection_uses_closed_contract_on_both_routes(http_env, monkeypatch):
    client, _db, _use_provider, _ = http_env
    import app
    with monkeypatch.context() as patch:
        patch.setattr(app, "_widget_origin_forbidden", lambda _client_id: ("blocked", 403))
        json_response = post(client, sid="origin", request_id="json")
        stream_response = post_sse(client, sid="origin", request_id="sse")
    for response in (json_response, stream_response):
        assert response.status_code == 403
        _assert_safe(response.get_json(), stage="transport", code="request_invalid")


def test_sse_ingress_exception_has_safe_trace(http_env, monkeypatch, caplog):
    client, _db, _use_provider, _ = http_env
    import app
    with monkeypatch.context() as patch:
        patch.setattr(app, "resolve_request_client_id", lambda *_args, **_kwargs: (
            _ for _ in ()).throw(RuntimeError("RAW_SECRET_MARKER")))
        response = post_sse(client, sid="private-session", request_id="ingress")
    _assert_safe(response.get_json(), stage="transport", code="unexpected_failure")
    trace_id = response.headers["X-D2-Trace-Id"]
    rows = [getattr(record, "extra_data", {}) for record in caplog.records
            if getattr(record, "extra_data", {}).get("trace_id") == trace_id]
    assert any(row.get("diagnostic_code") == "internal_runtime_error" and
               row.get("stage") == "transport" for row in rows)
    assert all("RAW_SECRET_MARKER" not in str(row) and "private-session" not in str(row)
               for row in rows)


def test_malformed_json_is_request_invalid(http_env):
    client, _db, _use_provider, _ = http_env
    response = client.post("/ask", data="{invalid", content_type="application/json")
    assert response.status_code == 400
    _assert_safe(response.get_json(), stage="transport", code="request_invalid")
