"""Tests for per-client LLM system prompt."""
from __future__ import annotations

from core.llm_system_prompt import build_base_system


def test_cesi_system_prompt_no_free_consult_marketing():
    prompt = build_base_system("cesi")
    assert "Алина" in prompt
    assert "она бесплатная" not in prompt.lower()
    assert "консультация бесплатна" not in prompt.lower()
    assert "самостоятельные приглашения на консультацию" in prompt.lower()


def test_demo_system_prompt_no_global_free_consult_marketing():
    prompt = build_base_system("demo")
    assert "Надежда" in prompt
    assert "она бесплатная" not in prompt.lower()
    assert "консультация бесплатна" not in prompt.lower()
    assert "только если они уже есть в источнике" in prompt.lower()
