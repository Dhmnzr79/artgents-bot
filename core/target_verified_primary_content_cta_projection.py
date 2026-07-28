"""Post-Verifier CTA projection from validated primary MD frontmatter only."""

from __future__ import annotations

import logging
from dataclasses import replace
from pathlib import Path

from contracts.target_response_spec import TargetResponseSpec
from core.client_config_loader import lead_cta_dict_from_meta
from core.target_presentation_source_identity import (
    is_valid_content_ref,
    read_doc_presentation_meta,
)
from core.target_response_verifier import TargetVerifiedComposedResponse

logger = logging.getLogger(__name__)


def _eligible_for_primary_cta_projection(spec: TargetResponseSpec) -> bool:
    if spec.response_mode == "medical_handoff":
        return False
    if spec.service_id is not None:
        return False
    if spec.required_components != ("content",):
        return False
    if spec.allow_cta:
        return False
    return True


def project_verified_primary_content_cta(
    verified: TargetVerifiedComposedResponse,
    *,
    client_id: str,
    md_root: Path,
) -> TargetVerifiedComposedResponse:
    """Project widget CTA key from validated primary MD only after successful verification."""

    if verified.selected_cta_key:
        return verified
    if not _eligible_for_primary_cta_projection(verified.spec):
        return verified

    primary = verified.primary_content_ref
    if not primary:
        logger.warning(
            "primary_cta_projection_skipped missing_primary client_id=%s",
            client_id,
        )
        return verified
    if not is_valid_content_ref(md_root, primary):
        logger.warning(
            "primary_cta_projection_skipped invalid_primary client_id=%s ref=%s",
            client_id,
            primary,
        )
        return verified

    meta = read_doc_presentation_meta(md_root, primary)
    if not meta:
        logger.warning(
            "primary_cta_projection_skipped empty_frontmatter client_id=%s ref=%s",
            client_id,
            primary,
        )
        return verified

    cta = lead_cta_dict_from_meta(client_id, meta)
    if cta is None:
        logger.warning(
            "primary_cta_projection_skipped invalid_cta_metadata client_id=%s ref=%s",
            client_id,
            primary,
        )
        return verified

    key = str(cta.get("key") or "").strip()
    action = str(cta.get("action") or "").strip()
    if action != "lead" or not key:
        logger.warning(
            "primary_cta_projection_skipped unsupported_cta client_id=%s ref=%s action=%s key=%s",
            client_id,
            primary,
            action,
            key,
        )
        return verified

    return replace(verified, selected_cta_key=key)
