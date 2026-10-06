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

from tests.d2_ci_http import FakeProvider, http_env, begin, send, click, raw, explanation, prompt
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore


@pytest.mark.parametrize('transport', ['json', 'sse'])
@pytest.mark.parametrize('phone', [False, True])
def test_d2_pending_answer_privacy_resume_and_replay(http_env, transport, phone):
    client, db, use, _ = http_env
    fake = use(FakeProvider(''))
    begin(client, fake, phone=phone, transport=transport)
    question = 'Меня зовут Анна, телефон +7 999 123-45-67. Сколько стоит имплантация?'
    pending = send(client, transport, request_id='question', q=question)
    assert len(fake.inputs) == 1
    assert LEAD_PENDING_ANSWER_REF in {q['reply_id'] for q in pending['ui']['quick_replies']}
    fake.raw = raw(explanation('О стоимости расскажем по материалам клиники.'))
    answered = click(client, pending, LEAD_PENDING_ANSWER_REF, request_id='answer', transport=transport)
    assert answered['answer'] == 'О стоимости расскажем по материалам клиники.'
    assert len(fake.inputs) == 2
    text = fake.inputs[-1].user_message + fake.inputs[-1].context.model_dump_json()
    assert 'Сколько стоит имплантация?' in fake.inputs[-1].user_message
    assert 'Анна' not in text and '999 123' not in text and '9991234567' not in text
    with session_client_scope('demo'):
        state = mem_get('cp6a')
        assert state['lead_intent'] == 'paused'
        assert not state['lead_pending_interruption_text']
        if phone:
            assert state['profile']['name'] == 'Анна'
    with D2DialogueStore(db) as store:
        record = store.read(SessionKey(client_id='demo', sid='cp6a'))
        stored = record.model_dump_json()
        assert 'Анна' not in stored
        assert '79991234567' not in re.sub(r'\D', '', stored)
        assert record.state.dialogue_pairs[-1].patient_text == fake.inputs[-1].user_message
    assert click(client, pending, LEAD_PENDING_ANSWER_REF, request_id='answer', transport=transport) == answered
    resumed = click(client, answered, LEAD_RESUME_REF, request_id='resume', transport=transport)
    assert 'телефон' in resumed['answer'].lower() if phone else 'обращ' in resumed['answer'].lower()
    with session_client_scope('demo'):
        assert mem_get('cp6a')['lead_intent'] == ('collecting_phone' if phone else 'collecting_name')
    assert len(fake.inputs) == 2


@pytest.mark.parametrize('transport', ['json', 'sse'])
def test_d2_pending_log_privacy_rejected_click_preserves_state(http_env, monkeypatch, transport):
    client, _, use, _ = http_env
    fake = use(FakeProvider(''))
    begin(client, fake, transport=transport)
    from core import d2_diagnostics as diagnostics
    previews = []
    monkeypatch.setattr(diagnostics, '_write', lambda fields: previews.append(dict(fields)))
    question = 'PRIVATE_PENDING_QUOTE Сколько стоит имплантация?'
    pending = send(client, transport, request_id='question', q=question)
    with session_client_scope('demo'):
        before = dict(mem_get('cp6a'))
    response = (client.post('/ask' if transport == 'json' else '/ask/stream',
                           json={'sid':'cp6a','client_id':'demo','request_id':'stale','q':'',
                                 'ref':LEAD_PENDING_ANSWER_REF,'ui_revision':pending['revision']-1}))
    if transport == 'json':
        assert response.status_code == 400
    else:
        from tests.test_d2_http_contract import sse_events
        assert 'error' in dict(sse_events(response))
    with session_client_scope('demo'):
        assert mem_get('cp6a') == before
    assert len(fake.inputs) == 1
    assert previews
    assert 'PRIVATE_PENDING_QUOTE' not in json.dumps(previews, ensure_ascii=False)


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


@patch("lead_service.leads_mode", return_value="demo_stub")
@patch("lead_service.leads_enabled", return_value=True)
def test_unknown_clinic_403(_e, _m) -> None:
    payload, status = handle_lead({"phone": "+79001112233"}, client_id="unknown-clinic")
    assert status == 403
