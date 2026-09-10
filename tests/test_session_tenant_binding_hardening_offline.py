"""Session tenant binding hardening — explicit client scope contract (offline)."""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from pathlib import Path

import pytest

import app as app_module
import config
from session import (
    SessionClientNotBoundError,
    bind_session_client,
    clear_session_client_binding,
    current_session_client_id,
    mem_add_user,
    mem_get,
    mem_reset,
    session_client_scope,
)
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import answer_envelope


def _isolated_sqlite_paths(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    return _sqlite_path, sessions_dir


def _table_count(db_path: Path) -> int:
    if not db_path.is_file():
        return 0
    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return int(row[0]) if row else 0
    finally:
        conn.close()


def _parse_sse_ui_payload(resp) -> dict:
    text = resp.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    return json.loads(match.group(1))


def test_unbound_session_operation_is_fail_closed_without_demo_db(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    clear_session_client_binding()

    with pytest.raises(SessionClientNotBoundError):
        mem_get("unbound-sid")

    assert not (sessions_dir / "demo.db").exists()
    assert _table_count(sessions_dir / "demo.db") == 0


def test_http_missing_client_id_uses_ingress_default_demo(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ demo."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-default-{uuid.uuid4().hex[:8]}"

    resp = app_module.app.test_client().post("/ask", json={"q": "Расскажите о клинике", "sid": sid})
    assert resp.status_code == 200
    payload = resp.get_json()
    assert payload["meta"]["client_id"] == config.DEFAULT_CLIENT_ID
    assert backend.call_count == 1
    assert _table_count(sessions_dir / "demo.db") >= 1

    with session_client_scope(config.DEFAULT_CLIENT_ID):
        assert mem_get(sid).get("hist")


@pytest.mark.parametrize("client_id", ["demo", "nikadent"])
def test_explicit_client_uses_own_sqlite_pack(
    client_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    sid = f"s-pack-{client_id}-{uuid.uuid4().hex[:6]}"
    marker = f"marker-{client_id}-{uuid.uuid4().hex[:6]}"

    with session_client_scope(client_id):
        mem_add_user(sid, marker)

    assert _table_count(sessions_dir / f"{client_id}.db") >= 1
    other = "nikadent" if client_id == "demo" else "demo"
    with session_client_scope(other):
        hist = [str(item.get("content") or "") for item in mem_get(sid).get("hist") or []]
    assert marker not in hist


def test_same_sid_stays_isolated_between_demo_and_nikadent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    sid = f"shared-{uuid.uuid4().hex[:8]}"
    demo_marker = "demo-only-history"
    nika_marker = "nikadent-only-history"

    with session_client_scope("demo"):
        mem_add_user(sid, demo_marker)
    with session_client_scope("nikadent"):
        mem_add_user(sid, nika_marker)

    with session_client_scope("demo"):
        demo_hist = [str(item.get("content") or "") for item in mem_get(sid).get("hist") or []]
    with session_client_scope("nikadent"):
        nika_hist = [str(item.get("content") or "") for item in mem_get(sid).get("hist") or []]

    assert demo_marker in demo_hist
    assert nika_marker not in demo_hist
    assert nika_marker in nika_hist
    assert demo_marker not in nika_hist
    assert _table_count(sessions_dir / "demo.db") >= 1
    assert _table_count(sessions_dir / "nikadent.db") >= 1


def test_sequential_scopes_do_not_leave_stale_demo_binding() -> None:
    clear_session_client_binding()
    with session_client_scope("demo"):
        bind_session_client("demo")
        assert current_session_client_id() == "demo"
    assert current_session_client_id() is None

    with session_client_scope("nikadent"):
        assert current_session_client_id() == "nikadent"
        sid = f"s-seq-{uuid.uuid4().hex[:6]}"
        mem_add_user(sid, "nikadent-turn")
    assert current_session_client_id() is None


def test_exception_inside_scope_restores_previous_binding() -> None:
    clear_session_client_binding()
    with session_client_scope("demo"):
        with pytest.raises(RuntimeError):
            with session_client_scope("nikadent"):
                raise RuntimeError("scope failure")
        assert current_session_client_id() == "demo"
    assert current_session_client_id() is None


def test_nested_scope_restores_outer_client() -> None:
    clear_session_client_binding()
    with session_client_scope("demo"):
        assert current_session_client_id() == "demo"
        with session_client_scope("nikadent"):
            assert current_session_client_id() == "nikadent"
        assert current_session_client_id() == "demo"
    assert current_session_client_id() is None


def test_ask_binds_before_session_write_and_clears_after_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-ask-bind-{uuid.uuid4().hex[:8]}"
    clear_session_client_binding()

    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Расскажите о клинике", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert resp.get_json()["meta"]["client_id"] == "demo"
    assert current_session_client_id() is None
    assert _table_count(sessions_dir / "demo.db") >= 1


def test_ask_stream_worker_binds_and_clears_after_done(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Stream ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-stream-bind-{uuid.uuid4().hex[:8]}"
    clear_session_client_binding()

    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Расскажите о клинике", "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    payload = _parse_sse_ui_payload(resp)
    assert payload["meta"]["client_id"] == "demo"
    assert current_session_client_id() is None
    assert _table_count(sessions_dir / "demo.db") >= 1


def test_unknown_client_rejected_without_demo_session_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    backend = _CountingBackend(answer_envelope("must not run"))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = f"s-unknown-{uuid.uuid4().hex[:8]}"
    clear_session_client_binding()

    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Привет", "sid": sid, "client_id": "not-a-real-clinic"},
    )
    assert resp.status_code == 403
    assert resp.get_json().get("error") == "unknown_client"
    assert backend.call_count == 0
    assert current_session_client_id() is None
    assert _table_count(sessions_dir / "demo.db") == 0


def test_mem_reset_with_explicit_client_id_does_not_require_prebound_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    sid = f"s-reset-{uuid.uuid4().hex[:8]}"
    clear_session_client_binding()

    mem_reset(sid, client_id="demo")
    assert current_session_client_id() is None
    assert _table_count(sessions_dir / "demo.db") == 0

    with session_client_scope("demo"):
        mem_add_user(sid, "hello")
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        assert list(mem_get(sid).get("hist") or []) == []


def test_http_teardown_clears_binding_on_unhandled_request_context_exception() -> None:
    """Flask teardown_request must clear TLS binding when exception escapes request ctx."""
    clear_session_client_binding()
    assert current_session_client_id() is None

    with pytest.raises(RuntimeError, match="unhandled request failure"):
        with app_module.app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "x", "sid": "s-unhandled", "client_id": "nikadent"},
        ):
            from flask import request

            request.ctx = {"turn_t0_monotonic": 0.0}
            bind_session_client("nikadent")
            assert current_session_client_id() == "nikadent"
            raise RuntimeError("unhandled request failure")

    assert current_session_client_id() is None


def test_worker_execution_context_clears_binding_after_inner_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from core.target_sse_worker_context import worker_execution_context

    clear_session_client_binding()
    assert current_session_client_id() is None

    with pytest.raises(RuntimeError, match="worker boom"):
        with worker_execution_context(
            app_module.app,
            request_id="rid-worker",
            sid="s-worker",
            client_id="nikadent",
            turn_t0_monotonic=0.0,
            status_emit=None,
        ):
            assert current_session_client_id() == "nikadent"
            raise RuntimeError("worker boom")

    assert current_session_client_id() is None


def test_worker_execution_context_restores_outer_scope_after_inner_exception() -> None:
    from core.target_sse_worker_context import worker_execution_context

    clear_session_client_binding()
    with session_client_scope("demo"):
        assert current_session_client_id() == "demo"
        with pytest.raises(RuntimeError, match="worker nested boom"):
            with worker_execution_context(
                app_module.app,
                request_id="rid-nested",
                sid="s-nested",
                client_id="nikadent",
                turn_t0_monotonic=0.0,
                status_emit=None,
            ):
                assert current_session_client_id() == "nikadent"
                raise RuntimeError("worker nested boom")
        assert current_session_client_id() == "demo"
    assert current_session_client_id() is None


def test_worker_execution_context_success_leaves_no_stale_binding() -> None:
    from core.target_sse_worker_context import worker_execution_context

    clear_session_client_binding()
    with worker_execution_context(
        app_module.app,
        request_id="rid-ok",
        sid="s-ok",
        client_id="nikadent",
        turn_t0_monotonic=0.0,
        status_emit=None,
    ):
        assert current_session_client_id() == "nikadent"
    assert current_session_client_id() is None


def test_purge_session_observability_does_not_leave_nikadent_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pg_retention import purge_session_observability

    sqlite_path, sessions_dir = _isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))

    sid = f"purge-{uuid.uuid4().hex[:8]}"
    with session_client_scope("nikadent"):
        mem_add_user(sid, "nika marker")
    assert _table_count(sessions_dir / "nikadent.db") >= 1

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, *_a, **_k):
            return self

        def fetchone(self):
            return (1,)

        @property
        def rowcount(self):
            return 1

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: _Conn())

    clear_session_client_binding()
    with session_client_scope("demo"):
        stats = purge_session_observability(
            "postgresql://example",
            sid=sid,
            client_id="nikadent",
        )
        assert stats["found"] is True
        assert stats["sqlite_cleared"] is True
        assert current_session_client_id() == "demo"

    assert current_session_client_id() is None
    with session_client_scope("nikadent"):
        hist = [str(item.get("content") or "") for item in mem_get(sid).get("hist") or []]
    assert hist == []
    assert _table_count(sessions_dir / "demo.db") == 0


def test_purge_session_observability_sqlite_failure_does_not_leave_nikadent_binding(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from pg_retention import purge_session_observability

    class _Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def execute(self, *_a, **_k):
            return self

        def fetchone(self):
            return (1,)

        @property
        def rowcount(self):
            return 1

    class _Conn:
        def cursor(self):
            return _Cursor()

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

    monkeypatch.setattr("psycopg.connect", lambda *_a, **_k: _Conn())

    def _boom_reset(_sid: str, *, client_id: str | None = None):
        raise RuntimeError("sqlite reset failed")

    monkeypatch.setattr("session.mem_reset", _boom_reset)
    clear_session_client_binding()
    stats = purge_session_observability(
        "postgresql://example",
        sid="sid-boom",
        client_id="nikadent",
    )
    assert stats["sqlite_cleared"] is False
    assert current_session_client_id() is None
