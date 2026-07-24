"""Typed UI scope click contract (AC1)."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ScopeExtent = Literal["one_tooth", "few_teeth", "full_arch"]

UI_SCOPE_REF_PREFIX = "target:ui_scope/"
_UI_SCOPE_REF_RE = re.compile(
    r"^target:ui_scope/(?P<topic>[a-z0-9_]+)/(?P<extent>one_tooth|few_teeth|full_arch)$"
)


class UiScopeAction(BaseModel):
    """Canonical extent from a governed UI ref click; label is not authoritative."""

    model_config = ConfigDict(extra="forbid")

    extent: ScopeExtent
    topic: str = Field(..., min_length=1)
    ref: str = Field(..., min_length=1)
    provenance: Literal["ui_scope_ref"] = "ui_scope_ref"

    @field_validator("topic", mode="after")
    @classmethod
    def _normalize_topic(cls, value: str) -> str:
        topic = str(value).strip().lower()
        if not topic:
            raise ValueError("topic_required")
        return topic


def is_ui_scope_ref(ref: str) -> bool:
    return str(ref or "").strip().startswith(UI_SCOPE_REF_PREFIX)


def build_ui_scope_ref(*, topic: str, extent: ScopeExtent) -> str:
    topic_eff = str(topic).strip().lower()
    if not topic_eff:
        raise ValueError("topic_required")
    return f"{UI_SCOPE_REF_PREFIX}{topic_eff}/{extent}"


def parse_ui_scope_ref(ref: str) -> UiScopeAction | None:
    """Parse governed ref; return None when malformed."""

    ref_eff = str(ref or "").strip()
    match = _UI_SCOPE_REF_RE.match(ref_eff)
    if match is None:
        return None
    return UiScopeAction(
        extent=match.group("extent"),  # type: ignore[arg-type]
        topic=match.group("topic"),
        ref=ref_eff,
    )
