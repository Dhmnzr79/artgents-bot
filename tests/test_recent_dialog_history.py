from __future__ import annotations

from session import (
    format_dialog_context_for_understanding,
    mem_add_bot,
    mem_add_user,
    mem_get,
    mem_reset,
    recent_dialog_history,
)


def test_recent_dialog_history_last_six_messages():
    sid = "recent-hist-cap"
    mem_reset(sid)
    for i in range(8):
        mem_add_user(sid, f"user-{i}")
        mem_add_bot(sid, f"bot-{i}")
    hist = recent_dialog_history(sid, max_messages=6)
    lines = [ln for ln in hist.splitlines() if ln.strip()]
    assert len(lines) == 6
    assert "user-5" in hist
    assert "user-7" in hist
    assert "user-0" not in hist
    assert "user-4" not in hist


def test_format_dialog_context_for_understanding_empty():
    assert format_dialog_context_for_understanding("") == ""
    assert format_dialog_context_for_understanding("  ") == ""


def test_format_dialog_context_labels_not_fact_source():
    block = format_dialog_context_for_understanding("user: делаете all-on-4?\nassistant: да")
    assert "не источник фактов" in block
    assert "all-on-4" in block


def test_current_question_not_in_history_before_mem_add_user():
    sid = "hist-no-dup-current"
    mem_reset(sid)
    mem_add_user(sid, "Делаете all-on-4?")
    mem_add_bot(sid, "Да, выполняем All-on-4.")
    current = "а сколько стоит?"
    hist = recent_dialog_history(sid)
    assert current not in hist
    assert "all-on-4" in hist.lower()
    mem_add_user(sid, current)
    st = mem_get(sid)
    assert st["hist"][-1]["content"] == current
