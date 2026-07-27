"""Straight-line offline target response pipeline (S39, unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from contracts.service_consultation import ServiceConsultationValue
from contracts.target_cached_full_context import TargetCachedFullContext
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
    execute_target_composer,
)
from core.target_composer_request import (
    TargetComposerRequest,
    materialize_target_composer_request,
)
from core.target_response_verifier import (
    TargetSemanticVerifierBackend,
    TargetVerifiedComposedResponse,
    verify_target_composed_response,
)
from core.target_spec_offline_response_package import (
    TargetSpecBoundOfflineResponsePackage,
)


def run_target_offline_verified_response_pipeline(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    bundle: ResponseSchemaBundle,
    doctor_catalog: TargetDoctorCatalog,
    consultation_values: Sequence[ServiceConsultationValue],
    *,
    user_message: str,
    md_root: Path,
    cached_full_context: TargetCachedFullContext,
    tone: TargetComposerTone,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
    contact_fields: tuple[str, ...] | None = None,
    client_id: str = "demo",
) -> TargetVerifiedComposedResponse:
    """Materialize, compose and verify one exact target response without wiring it."""

    request = materialize_target_composer_request(
        bound_package,
        bundle,
        doctor_catalog,
        consultation_values,
        user_message=user_message,
        md_root=md_root,
        contact_fields=contact_fields,
        client_id=client_id,
    )
    unverified = execute_target_composer(
        request,
        composer_backend,
        tone=tone,
        cached_full_context=cached_full_context,
    )
    package_primary = bound_package.package.plan.primary_content_ref
    package_used = _used_content_refs_from_package(bound_package, request)
    exact_service_authority = bool(
        bound_package.package.plan.service_id and package_primary
    )
    return verify_target_composed_response(
        request,
        unverified,
        cached_full_context=cached_full_context,
        semantic_backend=semantic_backend,
        navigation_followups=bound_package.package.navigation_followups,
        md_root=md_root,
        primary_content_ref=package_primary,
        used_content_refs=package_used,
        exact_service_authority=exact_service_authority,
        client_id=client_id,
    )


def _used_content_refs_from_package(
    bound_package: TargetSpecBoundOfflineResponsePackage,
    request: TargetComposerRequest,
) -> tuple[str, ...]:
    refs: list[str] = []
    primary = bound_package.package.plan.primary_content_ref
    if primary:
        refs.append(primary)
    for block in request.evidence_blocks:
        ref = str(block.ref or "")
        if ref.startswith("content:"):
            refs.append(ref.removeprefix("content:"))
    return tuple(refs)
