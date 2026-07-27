"""Shared widget-faithful harness for FINAL_GENERIC_FULLCONTEXT_CONTENT_AUTHORITY."""

from __future__ import annotations

from tests.test_final_fullcontext_dialogue_runtime_convergence_harness import (  # noqa: F401
    BackendPayload,
    MessageBuildingComposerBackend,
    RecordingBoundaryBackend,
    RecordingSemanticBackend,
    assert_materialized_route,
    assert_not_error_route,
    build_frame,
    install_turn_frame,
    orchestrate_http,
    orchestrate_via_app,
    run_runtime_turn,
)

__all__ = [
    "BackendPayload",
    "MessageBuildingComposerBackend",
    "RecordingBoundaryBackend",
    "RecordingSemanticBackend",
    "assert_materialized_route",
    "assert_not_error_route",
    "build_frame",
    "install_turn_frame",
    "orchestrate_http",
    "orchestrate_via_app",
    "run_runtime_turn",
]
