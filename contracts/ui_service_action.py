"""Typed UI service click contract (Stage 5.1B)."""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

UI_SERVICE_REF_PREFIX = "target:ui_service/"
_UI_SERVICE_REF_RE = re.compile(r"^target:ui_service/(?P<service_id>[a-z0-9_]+)$")


class UiServiceAction(BaseModel):
    """Canonical active service from a governed UI ref click; label is not authoritative."""

    model_config = ConfigDict(extra="forbid")

    service_id: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    provenance: str = "ui_service_ref"

    @field_validator("service_id", mode="after")
    @classmethod
    def _normalize_service_id(cls, value: str) -> str:
        token = str(value).strip().lower()
        if not token:
            raise ValueError("service_id_required")
        return token


def is_ui_service_ref(ref: str) -> bool:
    return str(ref or "").strip().startswith(UI_SERVICE_REF_PREFIX)


def build_ui_service_ref(*, service_id: str) -> str:
    token = str(service_id).strip().lower()
    if not token:
        raise ValueError("service_id_required")
    return f"{UI_SERVICE_REF_PREFIX}{token}"


def parse_ui_service_ref(ref: str) -> UiServiceAction | None:
    ref_eff = str(ref or "").strip()
    match = _UI_SERVICE_REF_RE.match(ref_eff)
    if match is None:
        return None
    return UiServiceAction(service_id=match.group("service_id"), ref=ref_eff)
