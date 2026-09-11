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


def test_content_turn_masks_phone_and_email() -> None:
    q = "Пишите me@secret.test или +79001234567 про имплант"
    user, preview, withheld = observability_user_texts(
        q,
        route="retrieval_chunk",
        meta={},
    )
    assert withheld is False
    assert "+79001234567" not in user
    assert "me@secret.test" not in user
    assert "[телефон скрыт]" in user
    assert "[email скрыт]" in user
    assert "имплант" in user


def test_turn_preview_is_not_raw_slice() -> None:
    from core.observability_pii import observability_turn_preview

    q = "Иван, +79001112233, сколько стоит?"
    preview = observability_turn_preview(q, route="retrieval_chunk", meta={})
    assert "+79001112233" not in preview
    assert "Иван" in preview or "сколько" in preview


def test_situation_collect_withholds() -> None:
    assert is_pii_withheld_route("situation_collect", {"situation_collect": True})
    bot = observability_bot_text(
        "Длинный текст про ситуацию пациента",
        route="situation_collect",
        meta={"situation_collect": True},
    )
    assert "не хранится" in bot


def test_content_turn_bot_text_preserves_clinic_contacts() -> None:
    clinic_phone = "+7 (495) 111-22-33"
    clinic_email = "info@clinic-demo.test"
    answer = f"Телефон клиники {clinic_phone}, email {clinic_email}"
    bot = observability_bot_text(answer, route="retrieval_chunk", meta={})
    assert clinic_phone in bot
    assert clinic_email in bot


def test_emit_bot_event_preserves_clinic_contacts_in_bot_text() -> None:
    import logging

    import logging_setup

    clinic_phone = "+7 (495) 111-22-33"
    clinic_email = "info@clinic-demo.test"
    bot_raw = f"Телефон клиники {clinic_phone}, email {clinic_email}"
    details = scrub_observability_details(
        {
            "route": "retrieval_chunk",
            "user_text_redacted": "+79001234567 вопрос",
            "bot_text_redacted": bot_raw,
        }
    )
    row = logging_setup._sanitize({"details": details})
    bot_out = row["details"]["bot_text_redacted"]
    assert clinic_phone in bot_out
    assert clinic_email in bot_out
    assert "+79001234567" not in row["details"]["user_text_redacted"]
    logger = logging.getLogger("test.observability_pii")
    logging_setup.emit_bot_event(
        logger,
        "turn_complete",
        details=details,
    )


def test_scrub_content_route_does_not_mask_bot_contacts() -> None:
    clinic_phone = "+7 (495) 111-22-33"
    bot_raw = f"Звоните {clinic_phone}"
    out = scrub_observability_details(
        {
            "route": "retrieval_chunk",
            "user_text_redacted": "+79001234567 спросить",
            "bot_text_redacted": bot_raw,
        }
    )
    assert "+79001234567" not in out["user_text_redacted"]
    assert clinic_phone in out["bot_text_redacted"]


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
