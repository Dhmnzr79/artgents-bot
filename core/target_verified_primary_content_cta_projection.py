"""Post-Verifier CTA projection from validated primary MD frontmatter only."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from core.target_primary_content_cta import resolve_primary_content_cta_key
from core.target_response_verifier import TargetVerifiedComposedResponse

def project_verified_primary_content_cta(
    verified: TargetVerifiedComposedResponse,
    *,
    client_id: str,
    md_root: Path,
) -> TargetVerifiedComposedResponse:
    """Project widget CTA key from validated primary MD only after successful verification."""

    if not isinstance(verified, TargetVerifiedComposedResponse):
        return verified
    if verified.selected_cta_key:
        return verified
    key = resolve_primary_content_cta_key(
        spec=verified.spec,
        primary_content_ref=verified.primary_content_ref,
        client_id=client_id,
        md_root=md_root,
    )
    if key is None:
        return verified
    return replace(verified, selected_cta_key=key)
