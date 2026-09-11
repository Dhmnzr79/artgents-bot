"""Dual-view user text privacy contract (offline)."""

from __future__ import annotations

import json
import time
import uuid

import pytest

from core.user_text_privacy import (
    EMAIL_PLACEHOLDER,
    PHONE_PLACEHOLDER,
    observability_safe_user_text,
    provider_message_has_substance,
    provider_safe_user_text,
    sanitize_dialog_history_for_provider,
)

from orchestration.sales_one_plus_ask_turn import _apply_provider_safe_question

_MARKER_PHONE = "+79991234001"
_MARKER_EMAIL = "marker.pii.t5b@example.test"
_MARKER_NAME = "Анна"
_SUBSTANTIVE = "Сколько стоит имплантация?"


def test_provider_safe_strips_phone_email_and_self_intro() -> None:
    raw = f"Меня зовут {_MARKER_NAME}, {_SUBSTANTIVE} {_MARKER_PHONE} {_MARKER_EMAIL}"
    safe = provider_safe_user_text(raw)
    assert _MARKER_PHONE not in safe
    assert _MARKER_EMAIL not in safe
    assert _MARKER_NAME not in safe
    assert PHONE_PLACEHOLDER in safe
    assert EMAIL_PLACEHOLDER in safe
    assert "имплантац" in safe.lower()


def test_observability_safe_matches_provider_placeholders() -> None:
    raw = f"Пишите {_MARKER_EMAIL} или {_MARKER_PHONE}"
    out = observability_safe_user_text(raw)
    assert _MARKER_PHONE not in out
    assert _MARKER_EMAIL not in out
    assert PHONE_PLACEHOLDER in out
    assert EMAIL_PLACEHOLDER in out


def test_user_history_sanitizes_user_lines_only() -> None:
    clinic_phone = "+7 (495) 123-45-67"
    hist = (
        f"user: звоните {_MARKER_PHONE}\n"
        f"assistant: Телефон клиники {clinic_phone}"
    )
    out = sanitize_dialog_history_for_provider(hist)
    assert _MARKER_PHONE not in out
    assert PHONE_PLACEHOLDER in out
    assert clinic_phone in out


def test_privacy_only_message_has_no_substance() -> None:
    assert not provider_message_has_substance(
        provider_safe_user_text(_MARKER_PHONE),
        raw_source=_MARKER_PHONE,
    )
    assert provider_message_has_substance(
        provider_safe_user_text(f"{_SUBSTANTIVE} {_MARKER_PHONE}"),
        raw_source=f"{_SUBSTANTIVE} {_MARKER_PHONE}",
    )


def test_apply_provider_safe_marks_contact_only_as_privacy_only() -> None:
    safe, privacy_only = _apply_provider_safe_question(_MARKER_PHONE)
    assert privacy_only is True
    assert safe == ""
    safe_email, privacy_email = _apply_provider_safe_question(_MARKER_EMAIL)
    assert privacy_email is True
    assert safe_email == ""


@pytest.mark.parametrize(
    "query",
    ["Гарантия", "Рассрочка", "Седация", "Коронки", "Нужна консультация"],
)
def test_short_clinic_topics_not_privacy_only(query: str) -> None:
    safe, privacy_only = _apply_provider_safe_question(query)
    assert privacy_only is False
    assert provider_message_has_substance(safe, raw_source=query)
    assert query.casefold() in safe.casefold() or safe.casefold() in query.casefold()


def test_self_intro_only_is_privacy_only() -> None:
    safe, privacy_only = _apply_provider_safe_question("Меня зовут Анна")
    assert privacy_only is True
    assert safe == ""


def test_self_intro_with_question_reaches_provider() -> None:
    raw = "Меня зовут Анна, сколько стоит имплантация?"
    safe, privacy_only = _apply_provider_safe_question(raw)
    assert privacy_only is False
    assert _MARKER_NAME not in safe
    assert "имплантац" in safe.lower()


def test_bare_first_name_not_auto_privacy_only() -> None:
    safe, privacy_only = _apply_provider_safe_question("Анна")
    assert privacy_only is False


def test_legacy_multiline_user_hist_sanitized_for_provider() -> None:
    import uuid

    from session import mem_reset, recent_dialog_history_for_provider, session_client_scope

    clinic_phone = "+7 (495) 123-45-67"
    sid = f"t5b-multiline-{uuid.uuid4().hex[:10]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        from session import mem_get

        st = mem_get(sid)
        st["hist"] = [
            {
                "role": "user",
                "content": f"вопрос про имплантацию\n{_MARKER_PHONE}\n{_MARKER_EMAIL}",
            },
            {"role": "assistant", "content": f"Телефон клиники {clinic_phone}"},
        ]
        from session import _persist_unlocked

        _persist_unlocked(sid, st)
        out = recent_dialog_history_for_provider(sid)
    assert _MARKER_PHONE not in out
    assert _MARKER_EMAIL not in out
    assert PHONE_PLACEHOLDER in out
    assert clinic_phone in out


def test_session_hist_stores_provider_safe_not_raw(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from session import mem_add_user, mem_get, mem_reset, session_client_scope

    sid = f"t5b-hist-{uuid.uuid4().hex[:10]}"
    with session_client_scope("demo"):
        mem_reset(sid, client_id="demo")
        mem_add_user(sid, f"Меня зовут {_MARKER_NAME}, {_SUBSTANTIVE} {_MARKER_PHONE}")
        hist = list(mem_get(sid).get("hist") or [])
    assert hist
    content = str(hist[-1].get("content") or "")
    assert _MARKER_PHONE not in content
    assert _MARKER_NAME not in content
    assert "имплантац" in content.lower()


def test_expired_sqlite_session_purged_tenant_scoped() -> None:
    from session import (
        _connect,
        _persist_unlocked,
        bind_session_client,
        mem_get,
        session_client_scope,
    )

    sid = f"t5b-expire-{uuid.uuid4().hex[:10]}"
    with session_client_scope("demo"):
        bind_session_client("demo")
        st = mem_get(sid)
        st["situation_note"] = "SECRET_SITUATION_T5B"
        st["ts"] = time.time() - 7200
        _persist_unlocked(sid, st)
        bind_session_client("demo")
        conn = _connect()
        old = conn.execute(
            "SELECT updated_at FROM sessions WHERE sid=?", (sid,)
        ).fetchone()
        assert old is not None
        conn.execute(
            "UPDATE sessions SET updated_at=? WHERE sid=?",
            (time.time() - 7200, sid),
        )
        from session import _last_session_purge_at, _maybe_purge_idle_sessions

        bind_session_client("demo")
        _last_session_purge_at.clear()
        _maybe_purge_idle_sessions()
        row = conn.execute("SELECT 1 FROM sessions WHERE sid=?", (sid,)).fetchone()
        assert row is None
