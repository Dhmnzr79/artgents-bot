"""Offline dry-run harness for architecture comparison (0 provider/network calls)."""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from typing import Any

from evals.v5.arch_compare.arch_compare_configs import (
    ArchCompareConfig,
    all_arch_compare_configs,
    assert_config_registry,
)
from evals.v5.arch_compare.arch_compare_contract import (
    BLIND_VARIANTS,
    DRY_RUN_DISCLAIMER,
    EXPECTED_SCENARIO_CONFIG_RESULTS,
    EXPECTED_TURN_CONFIG_RESULTS,
    MEASUREMENT_ID,
)
from evals.v5.arch_compare.arch_compare_fake_transport import (
    ArchCompareFakeTransport,
    build_fake_envelope_json,
    fake_patient_text_for_turn,
)
from evals.v5.arch_compare.arch_compare_matrix import (
    ArchCompareScenarioSpec,
    assert_frozen_matrix_unchanged,
    frozen_matrix_digest,
    parse_scenario_specs,
)
from evals.v5.arch_compare.arch_compare_prompt_build import (
    ArchComparePromptCapture,
    build_dialog_history,
    build_prompt_capture,
)


@dataclass(frozen=True, slots=True)
class ArchCompareTurnConfigResult:
    measurement_id: str
    matrix_digest: str
    config_id: str
    model_role: str
    context_mode: str
    provider_model_id: str | None
    provider_model_id_status: str
    prompt_contract_version: int
    commercial_as_of: str
    scenario_id: str
    turn_id: str
    session_id: str
    ordered_source_refs: tuple[str, ...]
    stable_prefix_hash: str
    dynamic_suffix_hash: str
    content_context_hash: str
    full_context_size: int
    curated_context_size: int | None
    exact_catalog_hash: str
    service_reference_catalog_hash: str
    patient_text: str | None
    visible_answer: str | None
    selected_offer_ids: tuple[str, ...]
    promo_fact_ids: tuple[str, ...]
    amplifier_fact_ids: tuple[str, ...]
    route: str | None
    cta_ui_metadata: dict[str, Any] | None
    provider_call_count: int
    capture_notes: dict[str, str]


def _session_id(scenario_id: str) -> str:
    return f"arch_compare-{scenario_id}"


def _blind_mapping_seed(attempt_id: str) -> str:
    return hashlib.sha256(f"{MEASUREMENT_ID}:{attempt_id}".encode("utf-8")).hexdigest()


def build_blind_variant_mapping(
    *,
    attempt_id: str,
    scenario_ids: tuple[str, ...],
) -> dict[str, dict[str, str]]:
    """Deterministic per-scenario shuffle: variant letter -> config_id (hidden from review)."""

    configs = [row.config_id for row in all_arch_compare_configs()]
    rng = random.Random(_blind_mapping_seed(attempt_id))
    mapping: dict[str, dict[str, str]] = {}
    for scenario_id in scenario_ids:
        shuffled_configs = list(configs)
        rng.shuffle(shuffled_configs)
        mapping[scenario_id] = {
            variant: shuffled_configs[index] for index, variant in enumerate(BLIND_VARIANTS)
        }
    return mapping


def _unavailable_capture(
    *,
    scenario: ArchCompareScenarioSpec,
    turn,
    config: ArchCompareConfig,
    capture: ArchComparePromptCapture,
    matrix_digest_value: str,
    prior_fake_answers: dict[str, str],
) -> ArchCompareTurnConfigResult:
    patient_text = (
        fake_patient_text_for_turn(scenario_id=scenario.scenario_id, turn_id=turn.turn_id)
        if turn.provider_turn
        else None
    )
    return ArchCompareTurnConfigResult(
        measurement_id=MEASUREMENT_ID,
        matrix_digest=matrix_digest_value,
        config_id=config.config_id,
        model_role=config.model_role,
        context_mode=config.context_mode,
        provider_model_id=config.provider_model_id,
        provider_model_id_status=config.provider_model_id_status,
        prompt_contract_version=capture.prompt_contract_version,
        commercial_as_of=capture.commercial_as_of,
        scenario_id=scenario.scenario_id,
        turn_id=turn.turn_id,
        session_id=_session_id(scenario.scenario_id),
        ordered_source_refs=scenario.relevant_source_refs,
        stable_prefix_hash=capture.stable_prefix_hash,
        dynamic_suffix_hash=capture.dynamic_suffix_hash,
        content_context_hash=capture.content_context_hash,
        full_context_size=capture.full_context_size,
        curated_context_size=capture.curated_context_size,
        exact_catalog_hash=capture.exact_catalog_hash,
        service_reference_catalog_hash=capture.service_reference_catalog_hash,
        patient_text=patient_text,
        visible_answer=None,
        selected_offer_ids=capture.selected_offer_ids,
        promo_fact_ids=(),
        amplifier_fact_ids=(),
        route=turn.expected_route_class,
        cta_ui_metadata=None,
        provider_call_count=0,
        capture_notes={
            "visible_answer": "unavailable_offline_dry_run",
            "promo_fact_ids": "unavailable_without_presentation_pass",
            "amplifier_fact_ids": "unavailable_without_presentation_pass",
            "cta_ui_metadata": "unavailable_without_widget_runtime",
            "dialog_history": build_dialog_history(
                scenario=scenario,
                turn=turn,
                prior_turns=prior_fake_answers,
            )
            or "none",
        },
    )


def verify_fake_transport_wiring(
    *,
    scenario: ArchCompareScenarioSpec,
    turn,
    config: ArchCompareConfig,
) -> int:
    """Single local fake-transport invocation; not a provider/network call."""

    if not turn.provider_turn:
        return 0
    transport = ArchCompareFakeTransport()
    envelope = build_fake_envelope_json(
        scenario_id=scenario.scenario_id,
        turn_id=turn.turn_id,
        route=turn.expected_route_class if turn.expected_route_class != "LOCAL" else "ANSWER",
        service_id=turn.expected_service_id,
        commercial_intent=turn.commercial_intent,
        promotion_scope=turn.promotion_scope,
    )
    transport.prepare_turn_envelopes((envelope,))
    response = transport.chat_completions_create(
        model=config.provider_model_id or "arch_compare_fake",
        stream=False,
        messages=[],
    )
    content = response.choices[0].message.content
    expected = fake_patient_text_for_turn(scenario_id=scenario.scenario_id, turn_id=turn.turn_id)
    if expected not in content:
        raise RuntimeError("arch_compare_fake_transport_wiring_mismatch")
    if len(transport.calls) != 1:
        raise RuntimeError("arch_compare_fake_transport_budget_exceeded")
    return 0


def run_arch_compare_dry_run(*, attempt_id: str = "offline_v1") -> dict[str, Any]:
    assert_config_registry()
    assert_frozen_matrix_unchanged()
    matrix_digest_value = frozen_matrix_digest()
    scenarios = parse_scenario_specs()
    scenario_ids = tuple(row.scenario_id for row in scenarios)
    blind_mapping = build_blind_variant_mapping(
        attempt_id=attempt_id,
        scenario_ids=scenario_ids,
    )

    turn_results: list[dict[str, Any]] = []
    scenario_config_results: list[dict[str, Any]] = []
    scenario_results: list[dict[str, Any]] = []
    prior_fake_answers_by_scenario: dict[str, dict[str, str]] = {}

    for scenario in scenarios:
        prior_fake_answers: dict[str, str] = {}
        scenario_turn_rows: list[dict[str, Any]] = []
        for turn in scenario.turns:
            dialog_history = build_dialog_history(
                scenario=scenario,
                turn=turn,
                prior_turns=prior_fake_answers,
            )
            for config in all_arch_compare_configs():
                capture = build_prompt_capture(
                    config=config,
                    scenario=scenario,
                    turn=turn,
                    dialog_history=dialog_history,
                )
                row = _unavailable_capture(
                    scenario=scenario,
                    turn=turn,
                    config=config,
                    capture=capture,
                    matrix_digest_value=matrix_digest_value,
                    prior_fake_answers=prior_fake_answers,
                )
                row_dict = asdict(row)
                scenario_turn_rows.append(row_dict)
                turn_results.append(row_dict)
                if turn is scenario.turns[0]:
                    scenario_config_results.append(
                        {
                            "scenario_id": scenario.scenario_id,
                            "config_id": config.config_id,
                            "turn_id": turn.turn_id,
                            "stable_prefix_hash": capture.stable_prefix_hash,
                            "dynamic_suffix_hash": capture.dynamic_suffix_hash,
                            "content_context_hash": capture.content_context_hash,
                            "exact_catalog_hash": capture.exact_catalog_hash,
                        }
                    )
            if turn.provider_turn:
                prior_fake_answers[turn.turn_id] = fake_patient_text_for_turn(
                    scenario_id=scenario.scenario_id,
                    turn_id=turn.turn_id,
                )
        prior_fake_answers_by_scenario[scenario.scenario_id] = dict(prior_fake_answers)
        scenario_results.append(
            {
                "scenario_id": scenario.scenario_id,
                "turn_count": len(scenario.turns),
                "config_count": len(all_arch_compare_configs()),
                "turns": scenario_turn_rows,
            }
        )

    if len(turn_results) != EXPECTED_TURN_CONFIG_RESULTS:
        raise RuntimeError(
            f"turn_config_result_count_mismatch expected={EXPECTED_TURN_CONFIG_RESULTS} "
            f"actual={len(turn_results)}"
        )
    if len(scenario_config_results) != EXPECTED_SCENARIO_CONFIG_RESULTS:
        raise RuntimeError(
            f"scenario_config_result_count_mismatch expected={EXPECTED_SCENARIO_CONFIG_RESULTS} "
            f"actual={len(scenario_config_results)}"
        )

    return {
        "measurement_id": MEASUREMENT_ID,
        "attempt_id": attempt_id,
        "mode": "offline_fake_dry_run",
        "disclaimer": DRY_RUN_DISCLAIMER,
        "matrix_digest": matrix_digest_value,
        "scenario_count": len(scenarios),
        "turn_count": sum(len(row.turns) for row in scenarios),
        "config_count": len(all_arch_compare_configs()),
        "turn_config_results": EXPECTED_TURN_CONFIG_RESULTS,
        "scenario_config_results": EXPECTED_SCENARIO_CONFIG_RESULTS,
        "provider_call_total": 0,
        "scenario_config_rows": scenario_config_results,
        "blind_variant_mapping": blind_mapping,
        "scenarios": scenario_results,
        "turns": turn_results,
    }
