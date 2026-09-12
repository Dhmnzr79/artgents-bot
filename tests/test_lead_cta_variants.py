"""Lead CTA catalog: label + first name prompt."""
from __future__ import annotations

from core.client_config_loader import (
    lead_cta_dict_from_meta,
    load_lead_cta_variants,
    resolve_lead_name_prompt,
    tone_to_txt_dict,
)


def test_load_lead_cta_variants_demo_has_six():
    variants = load_lead_cta_variants("demo")
    keys = {v.key for v in variants}
    assert keys == {"booking", "consult", "callback", "plan", "price", "doctor"}


def test_resolve_lead_name_prompt_by_key():
    prompt = resolve_lead_name_prompt("demo", cta_key="consult")
    assert "обсудим ваш вопрос с врачом" in prompt.lower()


def test_resolve_lead_name_prompt_by_label_backward_compat():
    prompt = resolve_lead_name_prompt("demo", cta_label="Обсудить вопрос")
    assert "обсудим ваш вопрос с врачом" in prompt.lower()


def test_resolve_lead_name_prompt_fallback_to_name_prompt():
    txt = tone_to_txt_dict("demo")
    prompt = resolve_lead_name_prompt("demo", txt=txt)
    assert prompt == txt["lead_name_prompt"]


def test_lead_cta_dict_from_meta_resolves_key_from_label():
    cta = lead_cta_dict_from_meta(
        "demo",
        {"cta_text": "Обсудить вопрос", "cta_action": "lead"},
    )
    assert cta is not None
    assert cta["key"] == "consult"
    assert cta["text"] == "Обсудить вопрос"


def test_lead_cta_dict_from_meta_explicit_key():
    cta = lead_cta_dict_from_meta(
        "demo",
        {"cta_key": "plan", "cta_action": "lead"},
    )
    assert cta == {
        "text": "Составить план лечения",
        "action": "lead",
        "key": "plan",
    }


def test_lead_cta_dict_default_booking_when_no_text():
    cta = lead_cta_dict_from_meta("demo", {"cta_action": "lead"})
    assert cta is not None
    assert cta["key"] == "booking"
    assert cta["text"] == "Записаться на консультацию"
