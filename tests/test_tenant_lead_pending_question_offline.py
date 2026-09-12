"""CP3.1: lead pending question choice, provider privacy, strict phone (offline)."""

from __future__ import annotations

import json
import re
import subprocess
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

import app as app_module
from core.lead_phone_input import parse_unambiguous_lead_phone
from core.lead_provider_input_privacy import prepare_lead_pending_provider_question
from core.observability_pii import observability_turn_preview
from flow_handlers import handle_flows
from lead_interrupt import (
    LEAD_PENDING_ANSWER_REF,
    LEAD_PENDING_CONTINUE_NAME_REF,
    LEAD_PENDING_RETRY_PHONE_REF,
    LEAD_RESUME_REF,
)
from lead_service import handle_lead
from session import (
    clear_lead_pii,
    exit_lead_flow,
    get_lead_pending_interruption,
    mem_get,
    mem_reset,
    session_client_scope,
    set_lead_intent,
    update_profile,
)
from tests.test_sales_fast_widget_integration import _CountingBackend, _install_sales_fast_transport
from tests.test_sales_one_plus_turn import answer_envelope
from tests.test_tenant_ingress_prod_boundary_offline import (
    _demo_base_url,
    _prod_headers,
    isolated_sqlite_paths,
    prod_tenant_boundary,
)


def _sp(answer, sid, client_id, **kwargs):
    return {
        "answer": answer,
        "quick_replies": list(kwargs.get("quick_replies") or []),
        "meta": {"sid": sid, "client_id": client_id},
    }


def _txt():
    return {
        "lead_name_prompt": "Как к вам можно обращаться?",
        "lead_phone_prompt_tpl": "{name}, оставьте, пожалуйста, номер телефона.",
        "lead_phone_prompt_neutral": (
            "Оставьте, пожалуйста, номер телефона — администратор свяжется с вами, "
            "чтобы подтвердить запись."
        ),
        "lead_phone_retry": "Оставьте телефон.",
    }


_NEUTRAL_PHONE = (
    "Оставьте, пожалуйста, номер телефона — администратор свяжется с вами, "
    "чтобы подтвердить запись."
)


def _flows(
    *,
    sid: str,
    client_id: str = "demo",
    data: dict | None = None,
    q: str = "",
    monkeypatch: pytest.MonkeyPatch | None = None,
    backend: _CountingBackend | None = None,
):
    if monkeypatch is not None and backend is not None:
        _install_sales_fast_transport(monkeypatch, backend)
    with session_client_scope(client_id):
        st = mem_get(sid)
        return handle_flows(
            data=dict(data or {}),
            st=st,
            sid=sid,
            q=q,
            client_id=client_id,
            txt=_txt(),
            service_payload=_sp,
            get_last_content_ui_payload=lambda _s: None,
            get_topic_state=lambda *_a, **_k: {},
        )


def _parse_sse_ui_payload(resp) -> dict:
    text = resp.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    return json.loads(match.group(1))


def test_clean_name_zero_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(sid=sid, data={"q": "Анна"}, q="Анна", monkeypatch=monkeypatch, backend=backend)
    assert backend.call_count == 0
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_phone"
        assert (mem_get(sid).get("profile") or {}).get("name") == "Анна"


def test_accepted_name_not_echoed_in_phone_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": "Анна"},
        q="Анна",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    answer = (result.get("payload") or {}).get("answer") or ""
    assert "Анна" not in answer
    assert _NEUTRAL_PHONE in answer


def test_rare_name_accepted_without_echo(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    rare = "Маолывр"
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": rare},
        q=rare,
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        assert (mem_get(sid).get("profile") or {}).get("name") == rare
    answer = (result.get("payload") or {}).get("answer") or ""
    assert rare not in answer
    assert _NEUTRAL_PHONE in answer


@pytest.mark.parametrize(
    "q",
    [
        "Привет",
        "Шатается имплант",
        "А сколько стоит All-on-4?",
        "Когда можно записаться?",
    ],
)
def test_obvious_non_name_goes_pending(q: str, monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": q},
        q=q,
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        text, step = get_lead_pending_interruption(sid)
        assert step == "collecting_name"
        assert text == q
    answer = (result.get("payload") or {}).get("answer") or ""
    assert "Не получилось распознать это как имя" in answer
    assert f"«{q}»" in answer
    qrs = (result.get("payload") or {}).get("quick_replies") or []
    assert any(r.get("ref") == LEAD_PENDING_ANSWER_REF for r in qrs)
    assert any(r.get("ref") == LEAD_PENDING_CONTINUE_NAME_REF for r in qrs)


def test_name_slot_survives_morph_analyzer_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("core.lead_name_slot.morph_analyzer", lambda: None)
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(
        sid=sid,
        data={"q": "Анна"},
        q="Анна",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    with session_client_scope("demo"):
        assert (mem_get(sid).get("profile") or {}).get("name") == "Анна"


def test_name_slot_survives_morph_parse_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    class _BrokenMorph:
        def parse(self, _word: str):
            raise RuntimeError("morph broken")

    monkeypatch.setattr("core.lead_name_slot.morph_analyzer", lambda: _BrokenMorph())
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(
        sid=sid,
        data={"q": "Дали"},
        q="Дали",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    with session_client_scope("demo"):
        assert (mem_get(sid).get("profile") or {}).get("name") == "Дали"


def test_ambiguous_dali_accepted_not_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": "Дали"},
        q="Дали",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        assert get_lead_pending_interruption(sid) == ("", "")
        assert (mem_get(sid).get("profile") or {}).get("name") == "Дали"
    answer = (result.get("payload") or {}).get("answer") or ""
    assert "Дали" not in answer
    assert _NEUTRAL_PHONE in answer


def test_hyphenated_name_accepted(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(
        sid=sid,
        data={"q": "Анна-Мария"},
        q="Анна-Мария",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "collecting_phone"


def test_clean_phone_submits_zero_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
    _flows(
        sid=sid,
        data={"q": "+7 999 123-45-67"},
        q="+7 999 123-45-67",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        assert mem_get(sid).get("lead_intent") == "submitted"
        assert get_lead_pending_interruption(sid) == ("", "")


def test_price_question_pending_zero_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("answer"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": "А сколько стоит All-on-4?"},
        q="А сколько стоит All-on-4?",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        text, step = get_lead_pending_interruption(sid)
    assert step == "collecting_name"
    assert "All-on-4" in text
    qrs = (result.get("payload") or {}).get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_ANSWER_REF for q in qrs)
    assert any(q.get("ref") == LEAD_PENDING_CONTINUE_NAME_REF for q in qrs)


def test_pending_continue_name_clears_and_reprompts(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(
        sid=sid,
        data={"q": "А сколько стоит All-on-4?"},
        q="А сколько стоит All-on-4?",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_CONTINUE_NAME_REF},
        q="",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        assert get_lead_pending_interruption(sid) == ("", "")
        assert mem_get(sid).get("lead_intent") == "collecting_name"
    assert "Как к вам можно обращаться?" in (result.get("payload") or {}).get("answer", "")


def _seed_collecting_name(sid: str, *, client_id: str = "demo") -> None:
    with session_client_scope(client_id):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")


def test_pending_answer_one_call_and_resume_name(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _sessions_dir = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    gray_calls: list[str] = []

    def _forbid_gray(*_a, **_k):
        gray_calls.append("gray")
        raise AssertionError("gray LLM must not run on PII slot")

    monkeypatch.setattr("llm.classify_lead_turn_gray_zone", _forbid_gray)
    backend = _CountingBackend(answer_envelope("Ответ про All-on-4."))
    _install_sales_fast_transport(monkeypatch, backend)
    client = app_module.app.test_client()
    sid = f"s-pending-name-{uuid.uuid4().hex[:8]}"
    headers = _prod_headers(origin="https://artgents.ru")
    _seed_collecting_name(sid)

    r2 = client.post(
        "/ask",
        json={"q": "А сколько стоит All-on-4?", "sid": sid},
        base_url=_demo_base_url(),
        headers=headers,
    )
    assert r2.status_code == 200
    assert backend.call_count == 0
    qrs = r2.get_json().get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_ANSWER_REF for q in qrs)

    r3 = client.post(
        "/ask",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=_demo_base_url(),
        headers=headers,
    )
    assert r3.status_code == 200
    assert backend.call_count == 1
    assert gray_calls == []
    inv = backend.invocation
    assert inv is not None
    assert "All-on-4" in str(inv.user_message)
    out_qrs = r3.get_json().get("quick_replies") or []
    assert any(q.get("ref") == LEAD_RESUME_REF for q in out_qrs)

    r4 = client.post(
        "/ask",
        json={"ref": LEAD_RESUME_REF, "sid": sid},
        base_url=_demo_base_url(),
        headers=headers,
    )
    assert r4.status_code == 200
    assert backend.call_count == 1
    assert "Как к вам можно обращаться?" in (r4.get_json().get("answer") or "")


def test_phone_question_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
    result = _flows(
        sid=sid,
        data={"q": "А рассрочка есть?"},
        q="А рассрочка есть?",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        _, step = get_lead_pending_interruption(sid)
        assert (mem_get(sid).get("profile") or {}).get("name") == "Анна"
    assert step == "collecting_phone"
    qrs = (result.get("payload") or {}).get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_RETRY_PHONE_REF for q in qrs)


def test_retry_phone_clears_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
    _flows(
        sid=sid,
        data={"q": "А рассрочка есть?"},
        q="А рассрочка есть?",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_RETRY_PHONE_REF},
        q="",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    with session_client_scope("demo"):
        assert get_lead_pending_interruption(sid) == ("", "")
        assert (mem_get(sid).get("profile") or {}).get("name") == "Анна"
    assert "телефона" in (result.get("payload") or {}).get("answer", "").lower()


def test_mixed_phone_not_auto_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: list[dict] = []
    monkeypatch.setattr("lead_service.send_lead_email", lambda **k: sent.append(k) or (True, "email"))
    monkeypatch.setattr("lead_service.leads_mode", lambda _c: "email")
    assert parse_unambiguous_lead_phone("+7 999 123-45-67, а рассрочка есть?") is None
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
    _flows(
        sid=sid,
        data={"q": "+7 999 123-45-67, а рассрочка есть?"},
        q="+7 999 123-45-67, а рассрочка есть?",
        monkeypatch=monkeypatch,
        backend=_CountingBackend(answer_envelope("x")),
    )
    assert sent == []


def test_provider_privacy_strips_contacts() -> None:
    q = prepare_lead_pending_provider_question("Анна, а сколько стоит All-on-4?")
    assert q and "Анна" not in q and "All-on-4" in q
    q2 = prepare_lead_pending_provider_question("Мой номер +79991234567, а рассрочка есть?")
    assert q2 and "7999" not in q2 and "1234567" not in q2 and "рассрочка" in q2.lower()
    assert prepare_lead_pending_provider_question("Анна +79991234567") is None
    assert "**" not in (q2 or "")


@pytest.mark.parametrize(
    "raw",
    [
        "Я Анна, а сколько стоит All-on-4?",
        "Меня зовут Анна, а сколько стоит All-on-4?",
        "Здравствуйте, меня зовут Анна. Сколько стоит All-on-4?",
    ],
)
def test_provider_privacy_name_intro_variants(raw: str) -> None:
    q = prepare_lead_pending_provider_question(raw, profile_name="Анна")
    assert q
    assert "анна" not in q.lower()
    assert "All-on-4" in q


def test_provider_invocation_user_message_strips_phone(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = uuid.uuid4().hex
    _seed_collecting_name(sid)
    with session_client_scope("demo"):
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(
            sid,
            text="+7 999 123-45-67, а рассрочка есть?",
            step="collecting_phone",
        )
        update_profile(sid, name="Анна")
    client = app_module.app.test_client()
    headers = _prod_headers(origin="https://artgents.ru")
    resp = client.post(
        "/ask",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=_demo_base_url(),
        headers=headers,
    )
    assert resp.status_code == 200
    assert backend.call_count == 1
    msg = str(backend.invocation.user_message)
    assert "999" not in msg
    assert "1234567" not in msg
    assert "рассрочка" in msg.lower()


def test_provider_question_not_persisted_in_session(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = uuid.uuid4().hex
    _seed_collecting_name(sid)
    with session_client_scope("demo"):
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(sid, text="А сколько стоит All-on-4?", step="collecting_name")
    client = app_module.app.test_client()
    client.post(
        "/ask",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=_demo_base_url(),
        headers=_prod_headers(origin="https://artgents.ru"),
    )
    with session_client_scope("demo"):
        st = mem_get(sid)
        blob = str(st)
        assert "lead_orchestration_provider_question" not in blob
        assert "All-on-4" not in blob or st.get("lead_pending_interruption_text") == ""


def test_pii_only_pending_answer_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    _flows(
        sid=sid,
        data={"q": "Анна +79991234567"},
        q="Анна +79991234567",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_ANSWER_REF, "q": "подмена"},
        q="подмена",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    assert result is not None
    qrs = (result.get("payload") or {}).get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_CONTINUE_NAME_REF for q in qrs)
    assert not any(q.get("ref") == "lead:pause" for q in qrs)


def test_answer_ref_without_pending_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_ANSWER_REF},
        q="",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    assert result is not None


def test_pending_ref_continue_name_wrong_step_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(sid, text="q?", step="collecting_phone")
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_CONTINUE_NAME_REF},
        q="",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        text, step = get_lead_pending_interruption(sid)
        assert text == "" and step == ""


def test_pending_ref_retry_phone_wrong_step_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(sid, text="q?", step="collecting_name")
    result = _flows(
        sid=sid,
        data={"ref": LEAD_PENDING_RETRY_PHONE_REF},
        q="",
        monkeypatch=monkeypatch,
        backend=backend,
    )
    assert backend.call_count == 0
    with session_client_scope("demo"):
        text, step = get_lead_pending_interruption(sid)
        assert text == "" and step == ""


def test_pending_ref_stale_without_pending_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = _CountingBackend(answer_envelope("x"))
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    for ref in (
        LEAD_PENDING_CONTINUE_NAME_REF,
        LEAD_PENDING_RETRY_PHONE_REF,
        LEAD_PENDING_ANSWER_REF,
    ):
        result = _flows(
            sid=sid,
            data={"ref": ref},
            q="",
            monkeypatch=monkeypatch,
            backend=backend,
        )
        assert backend.call_count == 0
        assert result is not None


def test_pending_tenant_isolation_same_sid(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    sid = "shared-sid-pending"
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(sid, text="demo-only question", step="collecting_name")
    with session_client_scope("nikadent"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
        text, step = get_lead_pending_interruption(sid)
        assert text == ""
        assert step == ""


def test_pending_cleared_on_cancel_submit_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
        from session import set_lead_pending_interruption

        set_lead_pending_interruption(sid, text="q", step="collecting_name")
        exit_lead_flow(sid)
        assert get_lead_pending_interruption(sid) == ("", "")
        set_lead_pending_interruption(sid, text="q2", step="collecting_name")
        clear_lead_pii(sid)
        assert get_lead_pending_interruption(sid) == ("", "")


def test_observability_withholds_pending_user_turn() -> None:
    preview = observability_turn_preview(
        "А сколько стоит All-on-4?",
        route=None,
        meta={"lead_flow": True, "lead_step": "pending_name"},
    )
    assert "All-on-4" not in preview


def test_html_like_pending_shown_literal_in_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = "<script>alert(1)</script>"
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_name")
    result = _flows(
        sid=sid,
        data={"q": raw},
        q=raw,
        monkeypatch=monkeypatch,
        backend=_CountingBackend(answer_envelope("x")),
    )
    answer = (result.get("payload") or {}).get("answer") or ""
    assert raw in answer


@pytest.mark.parametrize("path", ["/ask"])
def test_ask_pending_zero_calls_before_answer(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ."))
    _install_sales_fast_transport(monkeypatch, backend)
    client = app_module.app.test_client()
    sid = f"s-parity-{uuid.uuid4().hex[:8]}"
    headers = _prod_headers(origin="https://artgents.ru")
    base = _demo_base_url()
    _seed_collecting_name(sid)

    pending_resp = client.post(
        path,
        json={"q": "А сколько стоит All-on-4?", "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert backend.call_count == 0
    pending_payload = pending_resp.get_json()
    answer_resp = client.post(
        path,
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert answer_resp.status_code == 200
    answer_payload = answer_resp.get_json()
    assert backend.call_count == 1
    pending_qrs = pending_payload.get("quick_replies") or []
    answer_qrs = answer_payload.get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_ANSWER_REF for q in pending_qrs)
    assert any(q.get("ref") == LEAD_RESUME_REF for q in answer_qrs)


def test_stream_e2e_collecting_name_pending_question(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Ответ про All-on-4."))
    _install_sales_fast_transport(monkeypatch, backend)
    client = app_module.app.test_client()
    sid = f"s-stream-name-{uuid.uuid4().hex[:8]}"
    headers = _prod_headers(origin="https://artgents.ru")
    base = _demo_base_url()
    question = "А сколько стоит All-on-4?"
    _seed_collecting_name(sid)

    pending_resp = client.post(
        "/ask/stream",
        json={"q": question, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert pending_resp.status_code == 200
    assert backend.call_count == 0
    pending_payload = _parse_sse_ui_payload(pending_resp)
    assert question in (pending_payload.get("answer") or "")
    pending_qrs = pending_payload.get("quick_replies") or []
    assert any(q.get("ref") == LEAD_PENDING_ANSWER_REF for q in pending_qrs)
    assert any(q.get("ref") == LEAD_PENDING_CONTINUE_NAME_REF for q in pending_qrs)

    from session import clear_session_store_cache

    clear_session_store_cache()
    with session_client_scope("demo"):
        text, step = get_lead_pending_interruption(sid)
        assert step == "collecting_name"
        assert "All-on-4" in text

    answer_resp = client.post(
        "/ask/stream",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert answer_resp.status_code == 200
    answer_payload = _parse_sse_ui_payload(answer_resp)
    assert answer_payload.get("meta", {}).get("lead_paused") is True
    assert backend.call_count == 1
    answer_qrs = answer_payload.get("quick_replies") or []
    assert any(q.get("ref") == LEAD_RESUME_REF for q in answer_qrs)

    resume_resp = client.post(
        "/ask/stream",
        json={"ref": LEAD_RESUME_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert resume_resp.status_code == 200
    resume_payload = _parse_sse_ui_payload(resume_resp)
    assert backend.call_count == 1
    assert "Как к вам можно обращаться?" in (resume_payload.get("answer") or "")


def test_stream_e2e_collecting_phone_pending_question(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Рассрочка доступна."))
    _install_sales_fast_transport(monkeypatch, backend)
    client = app_module.app.test_client()
    sid = f"s-stream-phone-{uuid.uuid4().hex[:8]}"
    headers = _prod_headers(origin="https://artgents.ru")
    base = _demo_base_url()
    question = "А рассрочка есть?"
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")

    pending_resp = client.post(
        "/ask/stream",
        json={"q": question, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert pending_resp.status_code == 200
    assert backend.call_count == 0
    pending_payload = _parse_sse_ui_payload(pending_resp)
    assert question in (pending_payload.get("answer") or "")
    assert any(
        q.get("ref") == LEAD_PENDING_RETRY_PHONE_REF
        for q in (pending_payload.get("quick_replies") or [])
    )

    answer_resp = client.post(
        "/ask/stream",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert answer_resp.status_code == 200
    _parse_sse_ui_payload(answer_resp)
    assert backend.call_count == 1
    resume_resp = client.post(
        "/ask/stream",
        json={"ref": LEAD_RESUME_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert resume_resp.status_code == 200
    resume_payload = _parse_sse_ui_payload(resume_resp)
    assert "телефона" in (resume_payload.get("answer") or "").lower()


def test_pending_quote_not_in_dialog_history(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("x"))
    _install_sales_fast_transport(monkeypatch, backend)
    question = "А сколько стоит All-on-4?"
    sid = uuid.uuid4().hex
    _seed_collecting_name(sid)
    client = app_module.app.test_client()
    headers = _prod_headers(origin="https://artgents.ru")
    resp = client.post(
        "/ask",
        json={"q": question, "sid": sid},
        base_url=_demo_base_url(),
        headers=headers,
    )
    assert resp.status_code == 200
    with session_client_scope("demo"):
        from session import recent_dialog_history

        joined = recent_dialog_history(sid, max_messages=8)
        assert question not in joined
        assert "All-on-4" not in joined


def test_pending_question_withheld_from_emit_bot_event_details(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("x"))
    _install_sales_fast_transport(monkeypatch, backend)
    captured: list[dict] = []

    def _capture(_logger, _name, *, details=None, **_kw):
        if details:
            captured.append(dict(details))

    monkeypatch.setattr("app.emit_bot_event", _capture)
    question = "А сколько стоит All-on-4?"
    sid = uuid.uuid4().hex
    _seed_collecting_name(sid)
    client = app_module.app.test_client()
    resp = client.post(
        "/ask",
        json={"q": question, "sid": sid},
        base_url=_demo_base_url(),
        headers=_prod_headers(origin="https://artgents.ru"),
    )
    assert resp.status_code == 200
    blob = json.dumps(captured, ensure_ascii=False)
    assert "All-on-4" not in blob


def test_render_bot_answer_html_escapes_markup() -> None:
    script_uri = Path("static/widget/answer_format.js").resolve().as_uri()
    raw = "<script>alert(1)</script>"
    node_code = (
        f"import {{ renderBotAnswerHtml }} from {json.dumps(script_uri)};\n"
        f"const html = renderBotAnswerHtml({json.dumps(raw)});\n"
        "console.log(html);\n"
    )
    result = subprocess.run(
        ["node", "--input-type=module", "-e", node_code],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        pytest.skip(f"node unavailable: {result.stderr}")
    html = result.stdout.strip()
    assert "<script>" not in html.lower()
    assert "alert(1)" in html


def test_worker_context_clears_provider_question_handoff() -> None:
    from core.lead_context import bind_lead_provider_question, take_lead_provider_question
    from core.target_sse_worker_context import worker_execution_context

    sid = uuid.uuid4().hex
    with worker_execution_context(
        app_module.app,
        request_id="req-test",
        sid=sid,
        client_id="demo",
        turn_t0_monotonic=0.0,
        status_emit=None,
    ):
        bind_lead_provider_question("А сколько стоит All-on-4?")
    assert take_lead_provider_question() is None


def test_phone_pending_answer_resume_to_phone_prompt(
    prod_tenant_boundary,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sqlite_path, _ = isolated_sqlite_paths(tmp_path)
    monkeypatch.setattr("session.sqlite_path_for_client", sqlite_path)
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", sqlite_path)
    backend = _CountingBackend(answer_envelope("Рассрочка доступна."))
    _install_sales_fast_transport(monkeypatch, backend)
    sid = uuid.uuid4().hex
    with session_client_scope("demo"):
        mem_reset(sid)
        set_lead_intent(sid, "collecting_phone")
        update_profile(sid, name="Анна")
    client = app_module.app.test_client()
    headers = _prod_headers(origin="https://artgents.ru")
    base = _demo_base_url()
    r1 = client.post(
        "/ask",
        json={"q": "А рассрочка есть?", "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert r1.status_code == 200
    assert backend.call_count == 0
    r2 = client.post(
        "/ask",
        json={"ref": LEAD_PENDING_ANSWER_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert r2.status_code == 200
    assert backend.call_count == 1
    r3 = client.post(
        "/ask",
        json={"ref": LEAD_RESUME_REF, "sid": sid},
        base_url=base,
        headers=headers,
    )
    assert r3.status_code == 200
    assert "телефона" in (r3.get_json().get("answer") or "").lower()


@patch("lead_service.leads_mode", return_value="demo_stub")
@patch("lead_service.leads_enabled", return_value=True)
def test_unknown_clinic_403(_e, _m) -> None:
    payload, status = handle_lead({"phone": "+79001112233"}, client_id="unknown-clinic")
    assert status == 403
