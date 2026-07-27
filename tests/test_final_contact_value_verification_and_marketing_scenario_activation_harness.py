"""Shared widget-faithful harness for contact value + marketing scenario activation."""

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
    pipeline_result_materialized,
    run_runtime_turn,
)
