"""Strict local phone-slot check for lead flow (not semantic classification)."""

from __future__ import annotations

import re

from session import normalize_phone

_LETTERS_RX = re.compile(r"[A-Za-z\u0400-\u04FF\u0451\u0401]")


def parse_unambiguous_lead_phone(text: str) -> str | None:
    """Accept only phone-shaped input without letters (mixed FAQ+phone → None)."""
    raw = (text or "").strip()
    if not raw:
        return None
    if _LETTERS_RX.search(raw):
        return None
    return normalize_phone(raw)
