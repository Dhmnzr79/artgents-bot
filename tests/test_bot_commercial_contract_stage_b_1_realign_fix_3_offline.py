"""FIX-3 — governed UI ingress: label-only clicks skip free-text gates."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import patch

import app as app_module
import config
import pytest
from contracts.local_problem_gate import LocalProblemGateResult
from contracts.ui_scope_action import build_ui_scope_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from orchestration.sales_one_plus_ask_turn import (
    GOVERNED_TYPED_UI_GATE,
    _is_governed_ref_label_only_click,
    orchestrate_sales_one_plus_ask_turn,
)
from session import mem_reset
from tests.test_sales_one_plus_turn import answer_envelope


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_followups"] = [
            {
                "ref": item.ref,
                "label": item.label,
                **({"client_id": item.client_id} if item.client_id else {}),
            }
            for item in items
        ]
        _persist_unlocked(sid, st)



def test_label_only_click_helper() -> None:
    sid = f"fix3-helper-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    mem_reset(sid)
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Вся челюсть"))
    assert _is_governed_ref_label_only_click(ref=ref, q="", sid=sid)
    assert _is_governed_ref_label_only_click(ref=ref, q="Вся челюсть", sid=sid)
    assert not _is_governed_ref_label_only_click(
        ref=ref,
        q="Вся челюсть и ещё вопрос",
        sid=sid,
    )
    other_sid = f"fix3-helper-other-{uuid.uuid4().hex[:8]}"
    mem_reset(other_sid)
    assert not _is_governed_ref_label_only_click(
        ref=ref,
        q="Вся челюсть",
        sid=other_sid,
    )


def test_label_q_skips_local_problem_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}
    gate_calls: list[str] = []

    def _gate(text: str):
        gate_calls.append(text)
        from core.local_problem_gate import decide_local_problem_gate

        return decide_local_problem_gate(text)

    def _orchestrate_sales_fast(**kwargs):
        captured["local_gate_result"] = kwargs.get("local_gate_result")
        return SimpleNamespace(
            kind="service_reply",
            q=kwargs.get("q"),
            sid=kwargs.get("sid"),
            client_id=kwargs.get("client_id"),
            service_payload={"answer": "ok", "meta": {"service_route": "sales_fast"}},
            service_route="sales_fast",
        )

    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.decide_local_problem_gate", _gate)
    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.contacts_intent", lambda _q: False)
    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.handle_flows", lambda **_k: None)
    monkeypatch.setattr(
        "orchestration.sales_one_plus_ask_turn.orchestrate_sales_fast_widget_turn",
        _orchestrate_sales_fast,
    )
    sid = f"fix3-gate-label-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    mem_reset(sid)
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Вся челюсть"))

    with app_module.app.test_request_context():
        from flask import request

        request.ctx = {}
        orchestrate_sales_one_plus_ask_turn(
            {"q": "Вся челюсть", "ref": ref, "sid": sid, "client_id": "demo"},
            resolve_client_id=lambda *_a, **_k: "demo",
            bind_chat_ctx=lambda *_a, **_k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda *_a, **_k: {},
            service_payload=lambda answer, _sid, _cid, **_: {"answer": answer, "meta": {}},
            get_last_content_ui_payload=lambda *_a, **_k: None,
            enqueue_resolver_trace=lambda **_k: None,
        )

    assert gate_calls == []
    result = captured.get("local_gate_result")
    assert isinstance(result, LocalProblemGateResult)
    assert result == GOVERNED_TYPED_UI_GATE


def test_label_plus_extra_text_runs_local_problem_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gate_calls: list[str] = []

    def _gate(text: str):
        gate_calls.append(text)
        from core.local_problem_gate import decide_local_problem_gate

        return decide_local_problem_gate(text)

    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.decide_local_problem_gate", _gate)
    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.contacts_intent", lambda _q: False)
    monkeypatch.setattr("orchestration.sales_one_plus_ask_turn.handle_flows", lambda **_k: None)
    monkeypatch.setattr(
        "orchestration.sales_one_plus_ask_turn.orchestrate_sales_fast_widget_turn",
        lambda **_k: SimpleNamespace(
            kind="service_reply",
            q="",
            sid="",
            client_id="demo",
            service_payload={"answer": "ok", "meta": {}},
            service_route="sales_fast",
        ),
    )
    sid = f"fix3-gate-mixed-{uuid.uuid4().hex[:8]}"
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    mem_reset(sid)
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Вся челюсть"))

    with app_module.app.test_request_context():
        from flask import request

        request.ctx = {}
        orchestrate_sales_one_plus_ask_turn(
            {
                "q": "Вся челюсть и ещё вопрос",
                "ref": ref,
                "sid": sid,
                "client_id": "demo",
            },
            resolve_client_id=lambda *_a, **_k: "demo",
            bind_chat_ctx=lambda *_a, **_k: None,
            resolve_ip=lambda: "127.0.0.1",
            client_txt=lambda *_a, **_k: {},
            service_payload=lambda answer, _sid, _cid, **_: {"answer": answer, "meta": {}},
            get_last_content_ui_payload=lambda *_a, **_k: None,
            enqueue_resolver_trace=lambda **_k: None,
        )

    assert gate_calls == ["Вся челюсть и ещё вопрос"]


@pytest.fixture
def isolated_demo_sqlite(tmp_path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    patch_runtime = patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    patch_session = patch("session.sqlite_path_for_client", _sqlite_path)
    patch_runtime.start()
    patch_session.start()
    from session import bind_session_client

    bind_session_client("demo")
    try:
        yield
    finally:
        patch_session.stop()
        patch_runtime.stop()


def test_scope_label_click_http_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
    isolated_demo_sqlite,
) -> None:
    class _Backend:
        def __init__(self, output: str) -> None:
            self.output = output

        def generate(self, *_a, **_k):
            return self.output

        def generate_stream(self, invocation, on_raw_delta, /):
            on_raw_delta(self.output)
            return None

    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: _Backend(
            answer_envelope(
                "На бесплатной консультации врач подберёт план.",
                commercial_intent="none",
                service_reference_status="none",
            )
        ),
    )
    sid = f"fix3-http-{uuid.uuid4().hex[:8]}"
    client = app_module.app.test_client()
    mem_reset(sid)
    t1 = client.post(
        "/ask",
        json={
            "q": "Сколько стоит имплантация?",
            "sid": sid,
            "client_id": "demo",
        },
    )
    assert t1.status_code == 200
    ref = next(
        str(item.get("ref"))
        for item in (t1.get_json() or {}).get("quick_replies") or []
        if "full_arch" in str(item.get("ref"))
    )
    label = next(
        str(item.get("label"))
        for item in (t1.get_json() or {}).get("quick_replies") or []
        if str(item.get("ref")) == ref
    )
    t2 = client.post(
        "/ask",
        json={"q": label, "ref": ref, "sid": sid, "client_id": "demo"},
    )
    assert t2.status_code == 200
    answer = str((t2.get_json() or {}).get("answer") or "")
    assert "318" in answer.replace("\u00a0", "").replace(" ", "")
    assert "бесплатн" not in answer.casefold() and "консультации врач" not in answer.casefold()
