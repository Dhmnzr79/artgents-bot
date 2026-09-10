"""Clean One Call runtime + UI/session/stream contract (offline HTTP/SSE)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest

import app as app_module
import config
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref
from core.provider_call_budget import ProviderCallPolicy, current_provider_call_budget, http_provider_budget_scope
from core.sales_fast_presentation import static_sales_fast_admin_handoff
from core.sales_one_plus_turn import SalesOnePlusBackendFailure
from core.target_contact_authority import canonical_contact_phone
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import (
    sync_session_patient_facts_topic,
    write_session_patient_facts_from_ui_action,
)
from tests.session_binding_test_support import read_target_runtime_session_for
from contracts.ui_scope_action import UiScopeAction
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import mem_get, mem_reset, session_client_scope
from tests.target_runtime_test_support import _seed_followups
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import admin_envelope, answer_envelope

_REPO = Path(__file__).resolve().parents[1]
_LEGACY_MODULE_PATHS = (
    _REPO / "orchestration/pre_resolver_turn.py",
    _REPO / "orchestration/target_fullcontext_turn.py",
)
_FORBIDDEN_IMPORT_PATTERNS = (
    re.compile(r"^\s*from\s+orchestration\.pre_resolver_turn\b", re.M),
    re.compile(r"^\s*from\s+orchestration\.target_fullcontext_turn\b", re.M),
    re.compile(r"^\s*import\s+orchestration\.pre_resolver_turn\b", re.M),
    re.compile(r"^\s*import\s+orchestration\.target_fullcontext_turn\b", re.M),
    re.compile(r"\brun_pre_resolver_turn\s*\("),
    re.compile(r"\borchestrate_target_fullcontext_turn\s*\("),
    re.compile(r"\bLEGACY_EMERGENCY_RUNTIME_ON\b"),
    re.compile(r"\bis_one_call_runtime_locked\s*\("),
)
_ADMIN_QUESTION = "После операции появилось воспаление, подскажите порядок действий"
_FORBIDDEN_ADMIN_MARKERS = ("₽", "скидк", "акци", "принимайте антибиотик", "полоскайте", "@admin")
_UI_SCOPE_REF = build_ui_scope_ref(topic="implantation", extent="one_tooth")
_UI_STAGE_REF = build_ui_stage_ref(topic="prosthetics", stage="implant_placed")
_MALFORMED_UI_REF = "target:ui_scope/implantation/not_an_extent"
_PARKING_QUESTION = "Есть ли парковка?"


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _hist_messages(sid: str, role: str, *, client_id: str = "demo") -> list[str]:
    roles = {role}
    if role == "bot":
        roles.add("assistant")
    with session_client_scope(client_id):
        return [
            str(item.get("content") or "")
            for item in mem_get(sid).get("hist") or []
            if item.get("role") in roles
        ]


def _parse_sse_ui_payload(resp) -> dict:
    text = resp.get_data(as_text=True)
    assert text.count("event: done") == 1
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    return json.loads(match.group(1))


def test_legacy_orchestration_modules_are_absent() -> None:
    for path in _LEGACY_MODULE_PATHS:
        assert not path.is_file(), path.as_posix()


def test_production_http_stack_has_no_forbidden_legacy_symbols() -> None:
    roots = (_REPO / "app.py", _REPO / "config.py", _REPO / "orchestration")
    offenders: list[str] = []
    for root in roots:
        paths = [root] if root.is_file() else sorted(root.rglob("*.py"))
        for path in paths:
            text = path.read_text(encoding="utf-8")
            for pattern in _FORBIDDEN_IMPORT_PATTERNS:
                if pattern.search(text):
                    offenders.append(f"{path.relative_to(_REPO).as_posix()}: {pattern.pattern}")
    assert offenders == []


def test_active_one_call_chain_is_wired_in_app() -> None:
    text = (_REPO / "app.py").read_text(encoding="utf-8")
    assert "orchestrate_sales_one_plus_ask_turn" in text
    assert "_orchestrate_ask_turn_inner" in text
    assert "http_provider_budget_scope" in text
    for symbol in ("run_pre_resolver_turn", "orchestrate_target_fullcontext_turn", "run_planner_turn"):
        assert symbol not in text


def test_ask_semantic_turn_uses_one_call_with_single_backend_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": f"s-a1-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert str(payload.get("answer") or "").strip()
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


def test_ask_stream_semantic_turn_uses_one_call_with_single_done(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Стерильность по протоколу клиники."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Как обеспечивается стерильность?", "sid": f"s-a2-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    assert resp.status_code == 200
    payload = _parse_sse_ui_payload(resp)
    assert backend.call_count == 1
    assert str(payload.get("answer") or "").strip()
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


@pytest.mark.parametrize(
    "env_patch",
    (
        pytest.param({"delenv": "SALES_ONE_PLUS_ON"}, id="missing"),
        pytest.param({"SALES_ONE_PLUS_ON": "0", "config_attr": False}, id="zero"),
        pytest.param({"LEGACY_EMERGENCY_RUNTIME_ON": "1", "config_legacy": True}, id="legacy_emergency"),
    ),
)
def test_env_flags_do_not_switch_http_runtime(
    monkeypatch: pytest.MonkeyPatch,
    env_patch: dict,
) -> None:
    backend = _CountingBackend(answer_envelope("Ответ по материалам клиники."))
    _install_sales_fast_transport(monkeypatch, backend)
    if env_patch.get("delenv"):
        monkeypatch.delenv("SALES_ONE_PLUS_ON", raising=False)
    if "SALES_ONE_PLUS_ON" in env_patch:
        monkeypatch.setenv("SALES_ONE_PLUS_ON", str(env_patch["SALES_ONE_PLUS_ON"]))
        monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", env_patch.get("config_attr", True))
    if env_patch.get("config_legacy"):
        monkeypatch.setattr(config, "LEGACY_EMERGENCY_RUNTIME_ON", True, raising=False)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": f"s-a3-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert resp.get_json()["meta"]["service_route"] == "sales_fast_materialized"


def test_deterministic_parking_uses_zero_backend_calls_and_code_owned_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Игнорируемый model prose о парковке за 1 рубль."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": _PARKING_QUESTION, "sid": f"s-a4-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    answer = str(payload.get("answer") or "")
    assert resp.status_code == 200
    assert backend.call_count == 0
    assert payload["meta"]["service_route"] == "sales_fast_contacts"
    assert "парков" in answer.lower()
    assert "1руб" not in _norm_digits(answer).lower()
    assert "игнорируемый model prose" not in answer.lower()


def test_invalid_envelope_is_fail_closed_with_single_backend_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend("{not-json")
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": f"s-a5-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_error"
    assert payload["meta"].get("target_error_code") == "json_invalid"
    assert str(payload.get("answer") or "").strip()


def test_backend_exception_is_fail_closed_without_second_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(SalesOnePlusBackendFailure("provider_error"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как обеспечивается стерильность?", "sid": f"s-a6-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_error"


def test_backend_timeout_is_fail_closed_without_exceeding_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(TimeoutError("provider timeout"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "Как obеспечивается стerильность?", "sid": f"s-a7-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_error"


def test_admin_semantic_turn_uses_typed_code_owned_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(admin_envelope())
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": _ADMIN_QUESTION, "sid": f"s-a8-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    )
    payload = resp.get_json()
    expected = static_sales_fast_admin_handoff(client_id="demo")
    assert resp.status_code == 200
    assert backend.call_count == 1
    assert payload["meta"]["service_route"] == "sales_fast_admin"
    assert payload.get("answer") == expected
    assert payload.get("offer") is None
    assert payload.get("cta") is None
    answer = str(payload.get("answer") or "").lower()
    for marker in _FORBIDDEN_ADMIN_MARKERS:
        assert marker not in answer


def test_valid_ui_scope_click_persists_patient_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-b9-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=_UI_SCOPE_REF, label="Один зуб"))
    backend = _CountingBackend(answer_envelope("Цена для одного зуба."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "", "ref": _UI_SCOPE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.extent == "one_tooth"
    assert after.patient_facts.ref == _UI_SCOPE_REF


def test_valid_ui_stage_click_persists_stage_topic_and_ref(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-b10-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=_UI_STAGE_REF, label="Имплант установлен"))
    backend = _CountingBackend(answer_envelope("На консультации подберём вариант протезирования."))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "", "ref": _UI_STAGE_REF, "sid": sid, "client_id": "demo"},
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is not None
    assert after.patient_facts.stage == "implant_placed"
    assert after.patient_facts.topic == "prosthetics"
    assert after.patient_facts.ref == _UI_STAGE_REF


def test_malformed_ui_ref_is_fail_closed_without_session_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-b11-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("ignored hostile price 1 ₽"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "", "ref": _MALFORMED_UI_REF, "sid": sid, "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 0
    assert payload["meta"]["service_route"] == "sales_fast_followup_unknown"
    assert read_target_runtime_session_for(sid).patient_facts is None
    assert "1" not in _norm_digits(str(payload.get("answer") or ""))


def test_unshown_ui_ref_is_fail_closed_without_session_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-b12-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("ignored hostile price 1 ₽"))
    _install_sales_fast_transport(monkeypatch, backend)
    resp = app_module.app.test_client().post(
        "/ask",
        json={"q": "", "ref": _UI_SCOPE_REF, "sid": sid, "client_id": "demo"},
    )
    payload = resp.get_json()
    assert resp.status_code == 200
    assert backend.call_count == 0
    assert payload["meta"]["service_route"] == "sales_fast_followup_unknown"
    assert read_target_runtime_session_for(sid).patient_facts is None


def test_ask_and_stream_terminal_payloads_are_equivalent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    envelope = answer_envelope("Цена для одного зуба.")
    client = app_module.app.test_client()

    sid_ask = f"s-b13-ask-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_ask, client_id="demo")
    _seed_followups(sid_ask, TargetRuntimeFollowupItem(ref=_UI_SCOPE_REF, label="Один зуб"))
    ask_backend = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, ask_backend)
    ask_payload = client.post(
        "/ask",
        json={"q": "", "ref": _UI_SCOPE_REF, "sid": sid_ask, "client_id": "demo"},
    ).get_json()

    sid_stream = f"s-b13-stream-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_stream, client_id="demo")
    _seed_followups(sid_stream, TargetRuntimeFollowupItem(ref=_UI_SCOPE_REF, label="Один зуб"))
    stream_backend = _CountingBackend(envelope)
    _install_sales_fast_transport(monkeypatch, stream_backend)
    stream_payload = _parse_sse_ui_payload(
        client.post(
            "/ask/stream",
            json={"q": "", "ref": _UI_SCOPE_REF, "sid": sid_stream, "client_id": "demo"},
        )
    )
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    assert ask_payload.get("meta", {}).get("service_route") == stream_payload.get("meta", {}).get(
        "service_route"
    )
    assert ask_payload.get("offer") == stream_payload.get("offer")
    assert ask_payload.get("cta") == stream_payload.get("cta")
    assert read_target_runtime_session_for(sid_ask).patient_facts == read_target_runtime_session_for(
        sid_stream
    ).patient_facts
    assert ask_backend.call_count == 1
    assert stream_backend.call_count == 1


def test_stream_emits_exactly_one_done_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = _CountingBackend(answer_envelope("Ответ по материалам клиники."))
    _install_sales_fast_transport(monkeypatch, backend)
    text = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": "Как обеспечивается стerильность?", "sid": f"s-b14-{uuid.uuid4().hex[:8]}", "client_id": "demo"},
    ).get_data(as_text=True)
    assert text.count("event: done") == 1
    assert text.count("event: ui") == 1


def test_stream_does_not_double_write_session_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid = f"s-b15-{uuid.uuid4().hex[:8]}"
    mem_reset(sid, client_id="demo")
    backend = _CountingBackend(answer_envelope("Ответ по материалам клиники."))
    _install_sales_fast_transport(monkeypatch, backend)
    question = "Как обеспечивается стерильность?"
    resp = app_module.app.test_client().post(
        "/ask/stream",
        json={"q": question, "sid": sid, "client_id": "demo"},
    )
    text = resp.get_data(as_text=True)
    assert "event: done" in text
    user_msgs = _hist_messages(sid, "user")
    bot_msgs = _hist_messages(sid, "bot")
    assert len(user_msgs) == 1
    assert len(bot_msgs) == 1
    assert user_msgs[0].strip() == question
    assert bot_msgs[0].strip()
    assert resp.get_data(as_text=True) == text
    assert len(_hist_messages(sid, "user")) == 1
    assert len(_hist_messages(sid, "bot")) == 1



def test_sid_isolation_for_ui_scope_patient_facts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sid_a = f"s-b16-a-{uuid.uuid4().hex[:8]}"
    sid_b = f"s-b16-b-{uuid.uuid4().hex[:8]}"
    mem_reset(sid_a, client_id="demo")
    mem_reset(sid_b, client_id="demo")
    _seed_followups(sid_a, TargetRuntimeFollowupItem(ref=_UI_SCOPE_REF, label="Один зуб"))
    backend = _CountingBackend(answer_envelope("Цена для одного зуба."))
    _install_sales_fast_transport(monkeypatch, backend)
    app_module.app.test_client().post(
        "/ask",
        json={"q": "", "ref": _UI_SCOPE_REF, "sid": sid_a, "client_id": "demo"},
    )
    assert read_target_runtime_session_for(sid_a).patient_facts is not None
    assert read_target_runtime_session_for(sid_b).patient_facts is None


def test_reset_clears_patient_facts() -> None:
    sid = f"s-b17-{uuid.uuid4().hex[:8]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        write_session_patient_facts_from_ui_action(
            sid,
            UiScopeAction(extent="one_tooth", topic="implantation", ref=_UI_SCOPE_REF),
        )
        assert read_target_runtime_session_for(sid).patient_facts is not None
        mem_reset(sid, client_id="demo")
        assert read_target_runtime_session_for(sid).patient_facts is None


def test_topic_change_clears_incompatible_patient_scope() -> None:
    sid = f"s-b18-{uuid.uuid4().hex[:8]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        write_session_patient_facts_from_ui_action(
            sid,
            UiScopeAction(extent="one_tooth", topic="implantation", ref=_UI_SCOPE_REF),
        )
        sync_session_patient_facts_topic(sid, current_topic="prosthetics")
        assert read_target_runtime_session_for(sid).patient_facts is None


def test_http_budget_is_one_call_locked() -> None:
    with http_provider_budget_scope(request_id="clean-runtime", sales_one_plus_on=True):
        budget = current_provider_call_budget()
        assert budget is not None
        assert budget.policy == ProviderCallPolicy.ONE_CALL_LOCKED
