"""Small, closed diagnostic vocabulary for the D2 HTTP boundary."""

from dataclasses import dataclass
from pathlib import Path
import re


_REASONS = {
    "request_invalid", "ui_action_invalid", "request_id_payload_conflict",
    "request_in_progress", "tenant_binding_failed", "provider_failed",
    "parser_invalid_envelope", "d2_gate_rejected", "materializer_failed",
    "store_failed", "transport_failed", "unexpected_failure",
}
_STAGES = {"transport", "tenant_binding", "provider", "parser", "d2_gate", "materializer", "store"}
_CATEGORIES = {"validation", "conflict", "provider", "protocol", "state", "storage", "unexpected"}
_DIAGNOSTIC_CODES = frozenset({
    # Internal, authored invariant names only. Never derive a log field from raw
    # model output, a patient message, or an arbitrary exception string.
    "d2_experiment_single_price_required",
    "d2_experiment_resolved_topic_required",
    "d2_experiment_price_not_resolved",
    "d2_experiment_content_not_resolved",
    "d2_experiment_multipart_not_resolved",
    "d2_experiment_a08_shape_required",
    "d2_experiment_terminal_session_unsupported",
    "d2_experiment_carry_extent_mismatch",
    "d2_content_scope_required",
    "d2_content_service_mismatch",
    "d2_price_scope_required",
    "d2_no_price_candidates",
    "d2_direct_service_scope_invalid",
    "d2_part_failure_authority_missing",
    "d2_content_failure_reason_invalid",
    "d2_treatment_service_topic_mismatch",
    "materialization_client_mismatch",
    "materialization_foreign_material",
    "d2_stale_ui_action",
    "d2_unauthorized_ui_action",
    "d2_ui_section_selection_mismatch",
    "d2_ui_service_selection_unresolved",
    "d2_ui_service_selection_mismatch",
    "json_invalid",
    "json_duplicate_keys",
    "envelope_not_object",
    "envelope_empty",
    "envelope_oversized",
    "envelope_encoding_invalid",
    "request_understanding_invalid",
    "envelope_invariant_violation",
    "missing_fields",
    "unknown_fields",
    "missing_reference_fields",
    "unknown_reference_fields",
    "route_invalid",
    "commercial_intent_invalid",
    "primary_price_request_id_invalid",
    "service_id_inactive",
    "direct_fact_ids_invalid",
    "d2_http_response_choices_missing",
    "d2_http_response_content_missing",
    "d2_prompt_fullcontext_empty",
    "d2_selected_section_pair_required",
    "d2_cp3_provider_budget_exhausted",
    "d2_cp3_response_choices_missing",
    "d2_cp3_response_content_missing",
    "parser_contract_other",
    "provider_contract_other",
    "tenant_snapshot_invalid",
    "sqlite_operational_error",
    "sqlite_error",
    "operation_timeout",
    "connection_error",
    "internal_runtime_error",
    "internal_value_error",
    "internal_exception",
})
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SAFE_SITE = re.compile(r"^[A-Za-z0-9_./-]+:[1-9][0-9]*$")


def safe_diagnostic_code(exc: Exception) -> str | None:
    """Classify internal failures without logging exception text or payloads."""
    import sqlite3

    from core.d2_live_provider import D2LiveProviderError
    from core.d2_tenant_snapshot import D2TenantSnapshotError
    from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError

    if isinstance(exc, OneCallEnvelopeProtocolError):
        code = exc.code.split(":", 1)[0]
        return code if code in _DIAGNOSTIC_CODES else "parser_contract_other"
    if isinstance(exc, D2LiveProviderError):
        code = str(exc)
        return code if code in _DIAGNOSTIC_CODES else "provider_contract_other"
    if isinstance(exc, D2TenantSnapshotError):
        return "tenant_snapshot_invalid"
    if isinstance(exc, sqlite3.OperationalError):
        return "sqlite_operational_error"
    if isinstance(exc, sqlite3.Error):
        return "sqlite_error"
    if isinstance(exc, TimeoutError):
        return "operation_timeout"
    if isinstance(exc, ConnectionError):
        return "connection_error"
    if isinstance(exc, ValueError):
        code = str(exc).split(":", 1)[0]
        return code if code in _DIAGNOSTIC_CODES else "internal_value_error"
    if isinstance(exc, RuntimeError):
        return "internal_runtime_error"
    return "internal_exception"


def safe_failure_site(exc: Exception) -> str | None:
    """Return only a repository file and line, never traceback text or values."""
    frame = exc.__traceback__
    site = None
    while frame is not None:
        try:
            relative = Path(frame.tb_frame.f_code.co_filename).resolve().relative_to(_REPO_ROOT)
            candidate = f"{relative.as_posix()}:{frame.tb_lineno}"
            if _SAFE_SITE.fullmatch(candidate):
                site = candidate
        except ValueError:
            pass
        frame = frame.tb_next
    return site


@dataclass(frozen=True)
class D2OutcomeError(Exception):
    stage: str
    reason_code: str
    category: str
    committed: bool = False
    diagnostic_code: str | None = None
    diagnostic_site: str | None = None

    def __post_init__(self):
        if (self.stage not in _STAGES or self.reason_code not in _REASONS
                or self.category not in _CATEGORIES or self.diagnostic_code not in _DIAGNOSTIC_CODES | {None}
                or (self.diagnostic_site is not None and not _SAFE_SITE.fullmatch(self.diagnostic_site))):
            raise ValueError("invalid_d2_diagnostic_vocabulary")

    def payload(self) -> dict:
        return {
            "error": self.reason_code,
            "stage": self.stage,
            "category": self.category,
            "committed": self.committed,
            "message": "Не удалось обработать запрос. Попробуйте ещё раз.",
        }

    @property
    def http_status(self) -> int:
        if self.reason_code in {"request_id_payload_conflict", "request_in_progress"}:
            return 409
        if self.reason_code in {"request_invalid", "ui_action_invalid", "parser_invalid_envelope", "d2_gate_rejected"}:
            return 400 if self.stage == "transport" or self.reason_code in {"request_invalid", "ui_action_invalid"} else 503
        return 503


def classify_d2_error(exc: Exception, *, stage: str = "d2_gate", committed: bool = False) -> D2OutcomeError:
    """Never use exception messages as public diagnostics."""
    if isinstance(exc, D2OutcomeError):
        return D2OutcomeError(exc.stage, exc.reason_code, exc.category,
                              committed or exc.committed, exc.diagnostic_code, exc.diagnostic_site)
    from core.d2_dialogue_store import D2RequestIdConflict, D2RequestInProgress
    from core.d2_live_provider import D2LiveProviderError
    from core.d2_tenant_snapshot import D2TenantSnapshotError
    from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError
    import sqlite3

    if isinstance(exc, D2RequestIdConflict):
        return D2OutcomeError("store", "request_id_payload_conflict", "conflict", committed)
    if isinstance(exc, D2RequestInProgress):
        return D2OutcomeError("store", "request_in_progress", "conflict", committed)
    if isinstance(exc, D2TenantSnapshotError) or (isinstance(exc, ValueError) and str(exc) == "d2_experiment_tenant_changed"):
        return D2OutcomeError("tenant_binding", "tenant_binding_failed", "state", committed,
                              safe_diagnostic_code(exc), safe_failure_site(exc))
    if isinstance(exc, D2LiveProviderError):
        return D2OutcomeError("provider", "provider_failed", "provider", committed,
                              safe_diagnostic_code(exc), safe_failure_site(exc))
    if isinstance(exc, OneCallEnvelopeProtocolError):
        return D2OutcomeError("parser", "parser_invalid_envelope", "protocol", committed,
                              safe_diagnostic_code(exc), safe_failure_site(exc))
    if isinstance(exc, sqlite3.Error):
        return D2OutcomeError("store", "store_failed", "storage", committed,
                              safe_diagnostic_code(exc), safe_failure_site(exc))
    if isinstance(exc, ValueError):
        message = str(exc)
        if stage == "transport" or message.startswith("d2_request_") or message == "d2_question_invalid":
            return D2OutcomeError("transport", "request_invalid", "validation", committed)
        if message in {"d2_stale_ui_action", "d2_unauthorized_ui_action", "d2_ui_service_selection_unresolved", "d2_ui_service_selection_mismatch"} or message.startswith("d2_ui_"):
            return D2OutcomeError("d2_gate", "ui_action_invalid", "validation", committed,
                                  safe_diagnostic_code(exc), safe_failure_site(exc))
        return D2OutcomeError(stage, "d2_gate_rejected" if stage == "d2_gate" else "unexpected_failure",
                              "validation", committed, safe_diagnostic_code(exc), safe_failure_site(exc))
    return D2OutcomeError(stage, "unexpected_failure", "unexpected", committed,
                          safe_diagnostic_code(exc), safe_failure_site(exc))
