"""Verifier-independent CTA resolution from primary MD frontmatter."""

from __future__ import annotations

from pathlib import Path

from contracts.target_response_spec import TargetResponseSpec
from core.client_config_loader import lead_cta_dict_from_meta
from core.target_presentation_source_identity import (
    is_valid_content_ref,
    read_doc_presentation_meta,
)


def _eligible_for_primary_cta_projection(spec: TargetResponseSpec) -> bool:
    return (
        spec.response_mode != "medical_handoff"
        and spec.service_id is None
        and spec.required_components == ("content",)
        and not spec.allow_cta
    )


def resolve_primary_content_cta_key(
    *,
    spec: TargetResponseSpec,
    primary_content_ref: str | None,
    client_id: str,
    md_root: Path,
) -> str | None:
    """Resolve an authored primary-document CTA without verifier coupling."""

    if not _eligible_for_primary_cta_projection(spec) or not primary_content_ref:
        return None
    if not is_valid_content_ref(md_root, primary_content_ref):
        return None
    meta = read_doc_presentation_meta(md_root, primary_content_ref)
    if not meta:
        return None
    cta = lead_cta_dict_from_meta(client_id, meta)
    if cta is None:
        return None
    key = str(cta.get("key") or "").strip()
    action = str(cta.get("action") or "").strip()
    return key if action == "lead" and key else None
