"""Typed authored service alternative row (Stage 5.1B)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AuthoredServiceAlternative:
    requested_service_id: str
    alternative_service_ids: tuple[str, ...]
    approved_text: str
