"""Fail-closed PII strip before pending lead question reaches One Call provider input."""

from __future__ import annotations

from core.user_text_privacy import (
    provider_message_has_substance,
    provider_safe_user_text,
)


def prepare_lead_pending_provider_question(
    raw: str,
    *,
    profile_name: str = "",
) -> str | None:
    source = (raw or "").strip()
    if not source:
        return None
    text = provider_safe_user_text(source, profile_name=profile_name)
    if not provider_message_has_substance(
        text,
        raw_source=source,
        reject_lone_personal_name=True,
    ):
        return None
    return text
