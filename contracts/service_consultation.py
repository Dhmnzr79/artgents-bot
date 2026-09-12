"""Offline contract for one service-owned consultation close (S18, unwired)."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict

from contracts.response_schema import TargetService


def _require_content_ref(value: object) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise ValueError("consultation_content_ref_invalid")
    if "\\" in value or "?" in value or "#" in value or ":" in value:
        raise ValueError("consultation_content_ref_invalid")
    if value.startswith("/") or value.endswith("/") or "//" in value:
        raise ValueError("consultation_content_ref_invalid")
    raw_parts = value.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        raise ValueError("consultation_content_ref_invalid")
    path = PurePosixPath(value)
    if path.as_posix() != value or path.suffix != ".md" or not path.stem:
        raise ValueError("consultation_content_ref_invalid")
    return value


def _normalize_value(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("consultation_value_must_be_string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("consultation_value_empty")
    return normalized


ConsultationContentRef = Annotated[str, BeforeValidator(_require_content_ref)]
ConsultationValueText = Annotated[str, BeforeValidator(_normalize_value)]


class ServiceConsultationValue(BaseModel):
    """One exact Markdown source and its approved consultation value."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    content_ref: ConsultationContentRef
    value: ConsultationValueText


class ServiceConsultationRefError(ValueError):
    """Every consultation source not owned by a supplied service catalog."""

    code = "consultation_content_refs_orphaned"

    def __init__(self, orphan_content_refs: tuple[str, ...]) -> None:
        self.orphan_content_refs = orphan_content_refs
        super().__init__(self.code)


def validate_service_consultation_refs(
    records: tuple[ServiceConsultationValue, ...],
    services: dict[str, TargetService],
) -> None:
    """Require every consultation document to be referenced by a service or option."""

    referenced: set[str] = set()
    for service in services.values():
        if service.content_ref is not None:
            referenced.add(service.content_ref)
        referenced.update(
            option.content_ref
            for option in service.options
            if option.content_ref is not None
        )

    orphaned = tuple(sorted({record.content_ref for record in records} - referenced))
    if orphaned:
        raise ServiceConsultationRefError(orphaned)
