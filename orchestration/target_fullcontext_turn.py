"""Target FullContext orchestration hook for /ask when dev flag is ON (S61)."""

from __future__ import annotations

from typing import Any

from contracts.ask_orchestration import AskOrchestrationResult
from core.target_composer_executor import TargetComposerBackend
from core.target_medical_boundary import TargetMedicalBoundaryBackend
from core.target_response_verifier import TargetSemanticVerifierBackend
from core.target_runtime_turn import run_target_fullcontext_runtime_turn


def _default_target_runtime_backends() -> tuple[
    TargetComposerBackend,
    TargetSemanticVerifierBackend,
    TargetMedicalBoundaryBackend,
]:
    from core.target_runtime_llm_backends import (
        TargetRuntimeLiveComposerBackend,
        TargetRuntimeLiveMedicalBoundaryBackend,
        TargetRuntimeLiveSemanticBackend,
    )

    return (
        TargetRuntimeLiveComposerBackend(),
        TargetRuntimeLiveSemanticBackend(),
        TargetRuntimeLiveMedicalBoundaryBackend(),
    )


def orchestrate_target_fullcontext_turn(
    *,
    q: str,
    sid: str,
    client_id: str,
    data: dict[str, Any] | None = None,
    composer_backend: TargetComposerBackend | None = None,
    semantic_backend: TargetSemanticVerifierBackend | None = None,
    boundary_backend: TargetMedicalBoundaryBackend | None = None,
) -> AskOrchestrationResult:
    """Run target-only FullContext path; never falls back to legacy routing."""

    _ = data
    if composer_backend is None or semantic_backend is None or boundary_backend is None:
        live_composer, live_semantic, live_boundary = _default_target_runtime_backends()
        composer_backend = composer_backend or live_composer
        semantic_backend = semantic_backend or live_semantic
        boundary_backend = boundary_backend or live_boundary

    outcome = run_target_fullcontext_runtime_turn(
        client_id=client_id,
        sid=sid,
        user_message=q,
        composer_backend=composer_backend,
        semantic_backend=semantic_backend,
        boundary_backend=boundary_backend,
    )
    payload = outcome.widget.payload
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    route = str(meta.get("service_route") or "target_fullcontext")
    return AskOrchestrationResult(
        kind="service_reply",
        q=q,
        sid=sid,
        client_id=client_id,
        service_payload=payload,
        service_doc_id=None,
        service_track_user=True,
        service_route=route,
    )
