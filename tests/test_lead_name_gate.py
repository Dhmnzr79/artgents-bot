"""Lead-flow name extraction and rejection (no LLM)."""
from __future__ import annotations

from lead_interrupt import detect_lead_interrupt, looks_like_slot_answer
from name_gate import accept_lead_name, hard_reject_lead_name
from session import extract_name


def test_accept_real_names() -> None:
    cases = [
        ("ПЕТР", "Петр"),
        ("петр", "Петр"),
        ("Петр", "Петр"),
        ("Абубакир", "Абубакир"),
        ("Мария Ивановна", "Мария Ивановна"),
        ("Семен Михайлович Попов", "Семен Михайлович Попов"),
        ("John", "John"),
        ("mary ann", "Mary Ann"),
        ("Мария?", "Мария"),
        ("меня зовут Олег", "Олег"),
        ("я Анна", "Анна"),
    ]
    for raw, expected in cases:
        assert accept_lead_name(raw) == expected, raw


def test_reject_symptoms_questions_garbage() -> None:
    rejected = [
        "болит зуб",
        "а какой адрес?",
        "all-on-4 делаете?",
        "бирбылыблы",
        "12345",
        "расскажите про импланты",
        "сколько стоит",
        "не знаю",
    ]
    for raw in rejected:
        assert accept_lead_name(raw) is None, raw
        assert hard_reject_lead_name(raw) or accept_lead_name(raw) is None


def test_three_word_fio_via_extract_name() -> None:
    name = extract_name("Семен Михайлович Попов")
    assert name == "Семен Михайлович Попов"


def test_slot_vs_interrupt_name_step() -> None:
    assert looks_like_slot_answer("Мария", "collecting_name")
    assert looks_like_slot_answer("Мария?", "collecting_name")
    assert not looks_like_slot_answer("болит зуб", "collecting_name")
    assert not looks_like_slot_answer("Я передумал", "collecting_name")
    assert detect_lead_interrupt("А какой адрес?", resume_step="collecting_name") == "contacts"
    assert detect_lead_interrupt("болит зуб", resume_step="collecting_name") == "pain"
    assert detect_lead_interrupt("бирбылыблы", resume_step="collecting_name") is None


def test_accept_lead_name_rejects_refusal_phrases() -> None:
    from name_gate import accept_lead_name

    assert accept_lead_name("Я передумал") is None
    assert accept_lead_name("Не хочу") is None
    assert accept_lead_name("я не буду") is None
    assert accept_lead_name("я Анна") == "Анна"
    assert accept_lead_name("Мария") == "Мария"
