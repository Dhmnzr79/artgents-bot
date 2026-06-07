"""Tests for PII withholding in observability payloads."""
from __future__ import annotations

from core.observability_pii import (
    PII_WITHHELD_USER,
    is_pii_withheld_route,
    observability_bot_text,
    observability_user_texts,
    scrub_observability_details,
)


def test_lead_flow_withholds_user_text() -> None:
    user, preview, withheld = observability_user_texts(
        "Вася",
        route="lead_flow",
        meta={"lead_flow": True, "lead_step": "name"},
    )
    assert withheld is True
    assert user == PII_WITHHELD_USER
    assert preview == PII_WITHHELD_USER


def test_content_turn_keeps_medical_text() -> None:
    q = "А я боюсь боли"
    user, preview, withheld = observability_user_texts(
        q,
        route="retrieval_chunk",
        meta={},
    )
    assert withheld is False
    assert user == q
    assert preview == q


def test_situation_collect_withholds() -> None:
    assert is_pii_withheld_route("situation_collect", {"situation_collect": True})
    bot = observability_bot_text(
        "Длинный текст про ситуацию пациента",
        route="situation_collect",
        meta={"situation_collect": True},
    )
    assert "не хранится" in bot


def test_scrub_observability_details_defense() -> None:
    out = scrub_observability_details(
        {
            "route": "lead_flow",
            "lead_flow": True,
            "user_text_redacted": "Петр",
            "bot_text_redacted": "Петр, оставьте телефон",
            "preview": "+79991234567",
        }
    )
    assert out["user_text_redacted"] == PII_WITHHELD_USER
    assert out["preview"] == PII_WITHHELD_USER
    assert out["pii_withheld"] is True
