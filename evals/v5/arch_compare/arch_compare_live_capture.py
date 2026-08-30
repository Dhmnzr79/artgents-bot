"""Structured turn capture for architecture comparison LIVE prep (eval-only)."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from evals.v5.arch_compare.arch_compare_configs import ArchCompareConfig
from evals.v5.arch_compare.arch_compare_contract import FAKE_PATIENT_TEXT_PREFIX
from evals.v5.arch_compare.arch_compare_live_boundary import (
    capture_code_only_boundary,
    capture_provider_turn_boundary,
)
from evals.v5.arch_compare.arch_compare_matrix import ArchCompareScenarioSpec, ArchCompareTurnSpec
from evals.v5.arch_compare.arch_compare_prompt_build import (
    ArchComparePromptCapture,
    build_dialog_history,
)


@dataclass(frozen=True, slots=True)
class ArchCompareStructuredTurnCapture:
    attempt_id: str
    scenario_id: str
    turn_id: str
    config_id: str
    session_id: str
    provider_turn: bool
    provider_model_id: str | None
    raw_model_envelope: str | None
    patient_text: str | None
    route: str | None
    selected_offer_ids: tuple[str, ...]
    canonical_price_block: str | None
    promo_fact_ids: tuple[str, ...]
    promo_fact_texts: tuple[str, ...]
    amplifier_fact_ids: tuple[str, ...]
    amplifier_fact_texts: tuple[str, ...]
    service_value_id: str | None
    service_value_text: str | None
    cta_ui_metadata: dict[str, Any]
    visible_answer: str | None
    presentation_capture_status: str | None
    dialog_history_before: str
    dialog_history_after: str
    stable_prefix_hash: str
    dynamic_suffix_hash: str
    content_context_hash: str
    exact_catalog_hash: str
    provider_call_count: int
    token_metadata: dict[str, Any]
    error_code: str | None
    degraded_flags: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def fake_live_patient_text(
    *,
    attempt_id: str,
    scenario_id: str,
    turn_id: str,
    config_id: str,
) -> str:
    return f"{FAKE_PATIENT_TEXT_PREFIX}:{attempt_id}:{scenario_id}:{turn_id}:{config_id}"


def build_structured_capture(
    *,
    attempt_id: str,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    config: ArchCompareConfig,
    session_id: str,
    dialog_history_before: str,
    dialog_history_after: str,
    envelope_json: str | None,
    patient_text: str | None,
    prompt_capture: ArchComparePromptCapture,
    provider_call_count: int,
    token_metadata: dict[str, Any] | None = None,
    error_code: str | None = None,
    degraded_flags: tuple[str, ...] = (),
) -> ArchCompareStructuredTurnCapture:
    boundary_fields: dict[str, Any]
    if turn.provider_turn and envelope_json and patient_text:
        boundary = capture_provider_turn_boundary(
            envelope_json=envelope_json,
            scenario=scenario,
            turn=turn,
            patient_text=patient_text,
            session_id=session_id,
        )
        boundary_fields = boundary.to_structured_fields()
    elif not turn.provider_turn:
        boundary = capture_code_only_boundary(turn=turn, session_id=session_id)
        boundary_fields = boundary.to_structured_fields()
    else:
        raise RuntimeError("structured_capture_missing_boundary_inputs")

    return ArchCompareStructuredTurnCapture(
        attempt_id=attempt_id,
        scenario_id=scenario.scenario_id,
        turn_id=turn.turn_id,
        config_id=config.config_id,
        session_id=session_id,
        provider_turn=turn.provider_turn,
        provider_model_id=config.provider_model_id if turn.provider_turn else None,
        raw_model_envelope=envelope_json,
        patient_text=boundary_fields.get("patient_text", patient_text),
        route=boundary_fields.get("route", turn.expected_route_class),
        selected_offer_ids=prompt_capture.selected_offer_ids,
        canonical_price_block=boundary_fields.get("canonical_price_block"),
        promo_fact_ids=boundary_fields.get("promo_fact_ids", ()),
        promo_fact_texts=boundary_fields.get("promo_fact_texts", ()),
        amplifier_fact_ids=boundary_fields.get("amplifier_fact_ids", ()),
        amplifier_fact_texts=boundary_fields.get("amplifier_fact_texts", ()),
        service_value_id=boundary_fields.get("service_value_id"),
        service_value_text=boundary_fields.get("service_value_text"),
        cta_ui_metadata=boundary_fields.get("cta_ui_metadata", {}),
        visible_answer=boundary_fields.get("visible_answer"),
        presentation_capture_status=boundary_fields.get("presentation_capture_status"),
        dialog_history_before=dialog_history_before,
        dialog_history_after=dialog_history_after,
        stable_prefix_hash=prompt_capture.stable_prefix_hash,
        dynamic_suffix_hash=prompt_capture.dynamic_suffix_hash,
        content_context_hash=prompt_capture.content_context_hash,
        exact_catalog_hash=prompt_capture.exact_catalog_hash,
        provider_call_count=provider_call_count,
        token_metadata=token_metadata or {},
        error_code=error_code,
        degraded_flags=degraded_flags,
    )


def build_structured_capture_for_provider_error(
    *,
    attempt_id: str,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    config: ArchCompareConfig,
    session_id: str,
    dialog_history_before: str,
    prompt_capture: ArchComparePromptCapture,
    provider_call_count: int,
    error_code: str,
    error_type: str,
    token_metadata: dict[str, Any] | None = None,
) -> ArchCompareStructuredTurnCapture:
    from evals.v5.arch_compare.arch_compare_live_persistence import PROVIDER_ERROR_REVIEW_TEXT

    return ArchCompareStructuredTurnCapture(
        attempt_id=attempt_id,
        scenario_id=scenario.scenario_id,
        turn_id=turn.turn_id,
        config_id=config.config_id,
        session_id=session_id,
        provider_turn=True,
        provider_model_id=config.provider_model_id,
        raw_model_envelope=None,
        patient_text=None,
        route=turn.expected_route_class,
        selected_offer_ids=prompt_capture.selected_offer_ids,
        canonical_price_block=None,
        promo_fact_ids=(),
        promo_fact_texts=(),
        amplifier_fact_ids=(),
        amplifier_fact_texts=(),
        service_value_id=None,
        service_value_text=None,
        cta_ui_metadata={},
        visible_answer=PROVIDER_ERROR_REVIEW_TEXT,
        presentation_capture_status="provider_error",
        dialog_history_before=dialog_history_before,
        dialog_history_after=dialog_history_before,
        stable_prefix_hash=prompt_capture.stable_prefix_hash,
        dynamic_suffix_hash=prompt_capture.dynamic_suffix_hash,
        content_context_hash=prompt_capture.content_context_hash,
        exact_catalog_hash=prompt_capture.exact_catalog_hash,
        provider_call_count=provider_call_count,
        token_metadata=token_metadata or {},
        error_code=error_code,
        degraded_flags=(error_type,),
    )


def build_dialog_history_for_session(
    *,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    prior_answers: dict[str, str],
) -> str:
    return build_dialog_history(scenario=scenario, turn=turn, prior_turns=prior_answers)
