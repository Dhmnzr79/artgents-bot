"""Straight-line offline target response pipeline (S39, unwired)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from contracts.doctor_schema import TargetDoctorCatalog
from contracts.response_schema import ResponseSchemaBundle
from contracts.service_consultation import ServiceConsultationValue
from core.target_composer_executor import (
    TargetComposerBackend,
    TargetComposerTone,
    execute_target_composer,
)
from core.target_composer_request import materialize_target_composer_request
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
    tone: TargetComposerTone,
    composer_backend: TargetComposerBackend,
    semantic_backend: TargetSemanticVerifierBackend,
) -> TargetVerifiedComposedResponse:
    """Materialize, compose and verify one exact target response without wiring it."""

    request = materialize_target_composer_request(
        bound_package,
        bundle,
        doctor_catalog,
        consultation_values,
        user_message=user_message,
        md_root=md_root,
    )
    unverified = execute_target_composer(
        request,
        composer_backend,
        tone=tone,
    )
    return verify_target_composed_response(
        request,
        unverified,
        semantic_backend=semantic_backend,
    )
