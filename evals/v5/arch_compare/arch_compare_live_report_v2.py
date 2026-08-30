"""Blind/technical report v2 for architecture comparison LIVE (eval-only)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from evals.v5.arch_compare.arch_compare_contract import BLIND_VARIANTS, CLIENT_ID, FAKE_PATIENT_TEXT_PREFIX
from evals.v5.arch_compare.arch_compare_live_contract import (
    EVAL_REQUEST_TIMEOUT_SEC,
    FAKE_LIVE_DISCLAIMER,
    PRODUCTION_SLA_REFERENCE_SEC,
)
from evals.v5.arch_compare.arch_compare_live_persistence import PROVIDER_ERROR_REVIEW_TEXT
from evals.v5.arch_compare.arch_compare_live_report import (
    _BLIND_REVIEW_HIDDEN_TOKENS,
    assert_blind_review_secrecy,
    assert_no_secrets_in_text,
)
from evals.v5.arch_compare.arch_compare_matrix import (
    ArchCompareScenarioSpec,
    ArchCompareTurnSpec,
    parse_scenario_specs,
)
from evals.v5.arch_compare.arch_compare_live_schedule import scenario_for_id
from evals.v5.arch_compare.arch_compare_prompt_build import build_dialog_history

NOT_CAPTURED = "not_captured_in_attempt_02"
PREVIOUS_ANSWER_NOT_CAPTURED = "previous_answer_not_captured"
PROVIDER_COMPLETED_NOT_PERSISTED = "provider_completed_but_result_not_persisted"
UNATTRIBUTED_MODEL_TEXT = "unattributed_model_text"
ORIGIN_NOT_PROVABLE = "origin_not_provable_from_attempt_02_artifacts"

CapturePersistenceStatus = Literal[
    "captured",
    "not_captured_in_attempt_02",
    "provider_completed_but_result_not_persisted",
]

ProvenanceOrigin = Literal[
    "model_direct_fact",
    "model_price_text",
    "code_canonical_fallback",
    "code_multi_offer_block",
    "code_automatic_promo",
    "code_amplifier",
    "code_service_value",
    "code_cta_ui",
    "unattributed_model_text",
    "not_captured_in_attempt_02",
]


@dataclass(frozen=True, slots=True)
class AttemptPersistenceCounters:
    preflight_provider_calls_completed: int
    measurement_provider_calls_completed: int
    measurement_provider_calls_failed: int
    total_provider_call_ordinal: int
    persisted_measurement_results: int
    missing_persisted_results: int
    attempted_measurement_provider_calls: int


def _scenario_index() -> dict[str, ArchCompareScenarioSpec]:
    return {row.scenario_id: row for row in parse_scenario_specs()}


def _turn_spec(scenario: ArchCompareScenarioSpec, turn_id: str) -> ArchCompareTurnSpec | None:
    return next((row for row in scenario.turns if row.turn_id == turn_id), None)


def _persistence_counters_payload(counters: AttemptPersistenceCounters | dict[str, Any] | None) -> dict[str, Any] | None:
    if counters is None:
        return None
    if isinstance(counters, dict):
        return counters
    return asdict(counters)


def _strip_fake_wire_marker(text: str) -> str:
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{FAKE_PATIENT_TEXT_PREFIX}:") or stripped.startswith(FAKE_PATIENT_TEXT_PREFIX):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _blind_safe_patient_text(text: str | None) -> str:
    if not text:
        return "—"
    stripped = str(text).strip()
    if stripped.startswith(f"{FAKE_PATIENT_TEXT_PREFIX}:") or stripped == FAKE_PATIENT_TEXT_PREFIX:
        return "—"
    return stripped


def _blind_safe_visible_answer(
    text: str | None,
    *,
    error_code: str | None = None,
    code_only: bool = False,
) -> str:
    if error_code:
        return PROVIDER_ERROR_REVIEW_TEXT
    if code_only:
        return "ответ сформирован кодом"
    if not text:
        return "—"
    cleaned = _strip_fake_wire_marker(str(text))
    return cleaned or "—"


def _parse_envelope_price_text(raw_model_envelope: str | None) -> str | None | str:
    if not raw_model_envelope:
        return NOT_CAPTURED
    try:
        payload = json.loads(raw_model_envelope)
    except json.JSONDecodeError:
        return NOT_CAPTURED
    if "price_text" not in payload:
        return NOT_CAPTURED
    value = payload.get("price_text")
    if value is None:
        return "null"
    text = str(value).strip()
    return text or "null"


def _sha_provenance_lines(run_result: dict[str, Any], *, rebuilt_with_sha: str | None) -> list[str]:
    source_sha = run_result.get("source_attempt_sha") or NOT_CAPTURED
    rebuild_sha = rebuilt_with_sha or run_result.get("rebuilt_with_sha") or NOT_CAPTURED
    return [
        f"- source_attempt_sha: `{source_sha}`",
        f"- rebuilt_with_sha: `{rebuild_sha}`",
    ]


def _parse_envelope_direct_fact_ids(raw_model_envelope: str | None) -> str | list[str]:
    if not raw_model_envelope:
        return NOT_CAPTURED
    try:
        payload = json.loads(raw_model_envelope)
    except json.JSONDecodeError:
        return NOT_CAPTURED
    refs = payload.get("references") or {}
    if not isinstance(refs, dict) or "direct_fact_ids" not in refs:
        return NOT_CAPTURED
    ids = refs.get("direct_fact_ids") or []
    return list(ids) if ids else "—"


def _matrix_expectation_section(turn: ArchCompareTurnSpec | None) -> dict[str, str]:
    if turn is None:
        return {"expected_service_id": NOT_CAPTURED, "expected_brand": NOT_CAPTURED}
    return {
        "expected_service_id": turn.expected_service_id or "—",
        "expected_brand": turn.expected_brand or "—",
    }


def _captured_precomposer_section(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "availability": NOT_CAPTURED,
            "brand_id": NOT_CAPTURED,
            "selected_offer_ids": NOT_CAPTURED,
        }
    offers = row.get("selected_offer_ids") or []
    return {
        "availability": NOT_CAPTURED,
        "brand_id": NOT_CAPTURED,
        "selected_offer_ids": list(offers) if offers else NOT_CAPTURED,
    }


def _commercial_theme_origin(
    *,
    fact_id: str,
    direct_fact_ids: str | list[str],
    promo_ids: list[str],
    amplifier_ids: list[str],
) -> str:
    if isinstance(direct_fact_ids, list) and fact_id in direct_fact_ids:
        return "model_direct_fact"
    if fact_id in promo_ids:
        return "code_automatic_promo"
    if f"fact:{fact_id}" in amplifier_ids or fact_id in amplifier_ids:
        return "code_amplifier"
    return ORIGIN_NOT_PROVABLE


def _commercial_provenance_section(
    row: dict[str, Any] | None,
    *,
    patient_text: str,
    visible_answer: str,
) -> dict[str, Any]:
    direct_fact_ids = _parse_envelope_direct_fact_ids((row or {}).get("raw_model_envelope"))
    promo_ids = list((row or {}).get("promo_fact_ids") or [])
    amplifier_ids = list((row or {}).get("amplifier_fact_ids") or [])
    direct_commercial = (row or {}).get("materialized_direct_commercial_text")
    themes = {
        "гарантия": ("implant_warranty", ("гарант",)),
        "рассрочка": ("installment_12", ("рассроч",)),
        "налоговый вычет": ("tax_deduction", ("вычет", "налогов")),
        "фиксация стоимости": ("fixed_price", ("фиксир", "договор")),
    }
    theme_rows: dict[str, dict[str, str]] = {}
    for label, (fact_id, markers) in themes.items():
        theme_rows[label] = {
            "patient_text_contains": (
                "да" if any(marker in patient_text.casefold() for marker in markers) else "нет"
            ),
            "visible_answer_contains": (
                "да" if any(marker in visible_answer.casefold() for marker in markers) else "нет"
            ),
            "structured_origin": _commercial_theme_origin(
                fact_id=fact_id,
                direct_fact_ids=direct_fact_ids,
                promo_ids=promo_ids,
                amplifier_ids=amplifier_ids,
            ),
        }
    return {
        "raw_direct_fact_ids": direct_fact_ids,
        "materialized_direct_commercial_text": (
            direct_commercial if direct_commercial is not None else NOT_CAPTURED
        ),
        "code_promo_ids": promo_ids if promo_ids else NOT_CAPTURED,
        "code_amplifier_ids": amplifier_ids if amplifier_ids else NOT_CAPTURED,
        "themes": theme_rows,
    }


def _history_lines_for_turn(
    *,
    scenario: ArchCompareScenarioSpec,
    turn: ArchCompareTurnSpec,
    structured_by_session: dict[str, list[dict[str, Any]]],
    session_id: str | None,
) -> tuple[str, str]:
    prior: dict[str, str] = {}
    if session_id:
        for row in structured_by_session.get(session_id, []):
            turn_id = str(row.get("turn_id") or "")
            patient_text = row.get("patient_text")
            if turn_id and isinstance(patient_text, str) and patient_text.strip():
                prior[turn_id] = patient_text.strip()
    for prior_turn_id in turn.dialog_history_turn_ids:
        if prior_turn_id not in prior:
            return turn.user_message, PREVIOUS_ANSWER_NOT_CAPTURED
    history = build_dialog_history(scenario=scenario, turn=turn, prior_turns=prior)
    if not history.strip():
        return turn.user_message, "—"
    patient_lines = [line for line in history.splitlines() if line.startswith("Пациент:")]
    if not patient_lines:
        return turn.user_message, "—"
    return turn.user_message, "\n".join(patient_lines)


def _code_blocks_section(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "canonical_price_block": NOT_CAPTURED,
            "service_value": NOT_CAPTURED,
            "promo": NOT_CAPTURED,
            "amplifiers": NOT_CAPTURED,
            "cta_ui": NOT_CAPTURED,
        }
    promo_ids = row.get("promo_fact_ids") or []
    amp_ids = row.get("amplifier_fact_ids") or []
    canonical = row.get("canonical_price_block")
    return {
        "canonical_price_block": canonical if canonical else NOT_CAPTURED,
        "service_value": row.get("service_value_text") or row.get("service_value_id") or NOT_CAPTURED,
        "promo": promo_ids if promo_ids else NOT_CAPTURED,
        "amplifiers": amp_ids if amp_ids else NOT_CAPTURED,
        "cta_ui": row.get("cta_ui_metadata") if row.get("cta_ui_metadata") else NOT_CAPTURED,
    }


def _resolved_price_section(row: dict[str, Any] | None) -> dict[str, Any]:
    if row is None:
        return {
            "owner": NOT_CAPTURED,
            "resolved_text": NOT_CAPTURED,
            "diagnostic": NOT_CAPTURED,
            "selected_offer_id": NOT_CAPTURED,
            "multi_offer_ids": NOT_CAPTURED,
        }
    owner = row.get("resolved_price_owner")
    if owner is not None:
        multi_ids = row.get("resolved_multi_offer_ids")
        return {
            "owner": owner,
            "resolved_text": row.get("resolved_price_text") or "—",
            "diagnostic": row.get("resolved_price_diagnostic") or "—",
            "selected_offer_id": row.get("resolved_selected_offer_id") or "—",
            "multi_offer_ids": multi_ids if multi_ids else "—",
        }
    return {
        "owner": NOT_CAPTURED,
        "resolved_text": NOT_CAPTURED,
        "diagnostic": NOT_CAPTURED,
        "selected_offer_id": NOT_CAPTURED,
        "multi_offer_ids": NOT_CAPTURED,
    }


def _persistence_status_for_variant(
    *,
    row: dict[str, Any] | None,
    missing_keys: set[tuple[str, str, str]],
) -> CapturePersistenceStatus:
    if row is not None:
        return "captured"
    return "not_captured_in_attempt_02"


def compute_persistence_counters(
    *,
    ledger: dict[str, Any],
    structured_turns: list[dict[str, Any]],
    raw_turns: list[dict[str, Any]],
) -> AttemptPersistenceCounters:
    calls = ledger.get("calls") or []
    preflight_completed = sum(
        1 for row in calls if row.get("phase") == "preflight" and row.get("status") == "completed"
    )
    measurement_completed = [
        row for row in calls if row.get("phase") == "measurement" and row.get("status") == "completed"
    ]
    measurement_failed = sum(
        1 for row in calls if row.get("phase") == "measurement" and row.get("status") == "failed"
    )
    persisted = len(structured_turns)
    attempted_measurement = len(measurement_completed) + measurement_failed
    missing = max(0, len(measurement_completed) - persisted)
    return AttemptPersistenceCounters(
        preflight_provider_calls_completed=preflight_completed,
        measurement_provider_calls_completed=len(measurement_completed),
        measurement_provider_calls_failed=measurement_failed,
        total_provider_call_ordinal=len(calls),
        persisted_measurement_results=persisted,
        missing_persisted_results=missing,
        attempted_measurement_provider_calls=attempted_measurement,
    )


def _missing_persisted_measurement_keys(
    *,
    ledger: dict[str, Any],
    structured_turns: list[dict[str, Any]],
) -> set[tuple[str, str, str]]:
    persisted = {
        (str(row["scenario_id"]), str(row["turn_id"]), str(row["config_id"]))
        for row in structured_turns
    }
    missing: set[tuple[str, str, str]] = set()
    for call in ledger.get("calls") or []:
        if call.get("phase") != "measurement" or call.get("status") != "completed":
            continue
        key = (
            str(call.get("scenario_id") or ""),
            str(call.get("turn_id") or ""),
            str(call.get("config_id") or ""),
        )
        if key[0] and key not in persisted:
            missing.add(key)
    return missing


def build_blind_review_markdown_v2(
    *,
    attempt_id: str,
    run_result: dict[str, Any],
    rebuilt_with_sha: str | None = None,
) -> str:
    mapping = run_result.get("blind_variant_mapping") or {}
    structured = run_result.get("structured_turns") or []
    status = str(run_result.get("status") or "")
    counters: AttemptPersistenceCounters | None = run_result.get("persistence_counters")
    scenarios = _scenario_index()

    by_scenario: dict[str, list[dict[str, Any]]] = {}
    by_session: dict[str, list[dict[str, Any]]] = {}
    for row in structured:
        scenario_id = str(row["scenario_id"])
        by_scenario.setdefault(scenario_id, []).append(row)
        session_id = str(row.get("session_id") or "")
        if session_id:
            by_session.setdefault(session_id, []).append(row)

    ledger = run_result.get("call_ledger") or {}
    missing_keys = _missing_persisted_measurement_keys(ledger=ledger, structured_turns=structured)

    lines = [
        f"# Architecture compare blind review v2 — `{attempt_id}`",
        "",
        *_sha_provenance_lines(run_result, rebuilt_with_sha=rebuilt_with_sha),
        f"- status: `{status}`",
    ]
    disclaimer = run_result.get("disclaimer")
    if isinstance(disclaimer, str) and disclaimer.strip():
        lines.extend(["", f"> {disclaimer}", ""])
    if counters is not None:
        lines.extend(
            [
                f"- provider_call_ordinal_total: `{counters.total_provider_call_ordinal}`",
                f"- measurement_provider_completed: `{counters.measurement_provider_calls_completed}`",
                f"- persisted_measurement_results: `{counters.persisted_measurement_results}`",
                f"- missing_persisted_results: `{counters.missing_persisted_results}`",
            ]
        )
    lines.append("")
    if status == "INCOMPLETE_FATAL":
        lines.extend(
            [
                "> PARTIAL / НЕПОЛНЫЙ ЗАПУСК — сохранены только завершённые scenario/config.",
                "",
            ]
        )

    for scenario_id in sorted(by_scenario):
        rows = by_scenario[scenario_id]
        scenario = scenarios.get(scenario_id) or scenario_for_id(scenario_id)
        turn_ids: list[str] = []
        for row in rows:
            tid = str(row["turn_id"])
            if tid not in turn_ids:
                turn_ids.append(tid)
        variant_to_config = mapping.get(scenario_id) or {}

        lines.extend([f"## Сценарий `{scenario_id}`", ""])
        for turn_id in turn_ids:
            turn = _turn_spec(scenario, turn_id)
            if turn is None:
                continue
            turn_rows = [r for r in rows if r["turn_id"] == turn_id]
            session_id = str(turn_rows[0].get("session_id") or "") if turn_rows else ""
            question, history = _history_lines_for_turn(
                scenario=scenario,
                turn=turn,
                structured_by_session=by_session,
                session_id=session_id or None,
            )
            lines.extend(
                [
                    f"### Ход `{turn_id}`",
                    "",
                    f"**Настоящий вопрос:** {question}",
                    "",
                    "**Предыдущая история диалога:**",
                    "",
                    history,
                    "",
                ]
            )
            for variant in BLIND_VARIANTS:
                config_id = variant_to_config.get(variant)
                match = next((r for r in turn_rows if r.get("config_id") == config_id), None)
                if match is None and config_id:
                    key = (scenario_id, turn_id, str(config_id))
                    if key in missing_keys:
                        persistence_status: CapturePersistenceStatus = PROVIDER_COMPLETED_NOT_PERSISTED
                    else:
                        persistence_status = "not_captured_in_attempt_02"
                else:
                    persistence_status = _persistence_status_for_variant(
                        row=match,
                        missing_keys=missing_keys,
                    )
                patient_text = _blind_safe_patient_text((match or {}).get("patient_text"))
                visible = _blind_safe_visible_answer(
                    (match or {}).get("visible_answer"),
                    error_code=(match or {}).get("error_code"),
                    code_only=not bool((match or {}).get("provider_turn")),
                )
                price_text = _parse_envelope_price_text((match or {}).get("raw_model_envelope"))
                matrix_expectation = _matrix_expectation_section(turn)
                captured_precomposer = _captured_precomposer_section(match)
                resolved = _resolved_price_section(match)
                code_blocks = _code_blocks_section(match)
                commercial = _commercial_provenance_section(
                    match,
                    patient_text=patient_text if patient_text != "—" else "",
                    visible_answer=visible if visible != "—" else "",
                )

                cta_ui = code_blocks["cta_ui"]
                if cta_ui in (NOT_CAPTURED, "—"):
                    cta_ui_display = cta_ui
                else:
                    cta_ui_display = json.dumps(cta_ui, ensure_ascii=False)
                lines.extend(
                    [
                        f"#### Вариант {variant}",
                        "",
                        f"1. **Сырой patient_text модели:** {patient_text or '—'}",
                        f"2. **Сырой model price_text:** {price_text}",
                        "3. **Matrix expectation (not captured selection):**",
                        f"   - expected_service_id: {matrix_expectation['expected_service_id']}",
                        f"   - expected_brand: {matrix_expectation['expected_brand']}",
                        "4. **Captured precomposer selection:**",
                        f"   - availability: {captured_precomposer['availability']}",
                        f"   - brand_id: {captured_precomposer['brand_id']}",
                        f"   - selected offer IDs: {captured_precomposer['selected_offer_ids']}",
                        "5. **Resolved price:**",
                        f"   - owner: {resolved['owner']}",
                        f"   - resolved text: {resolved['resolved_text']}",
                        f"   - diagnostic: {resolved['diagnostic']}",
                        f"   - selected offer ID: {resolved['selected_offer_id']}",
                        f"   - multi offer IDs: {resolved['multi_offer_ids']}",
                        "6. **Блоки, добавленные кодом:**",
                        f"   - canonical price block: {code_blocks['canonical_price_block']}",
                        f"   - service_value: {code_blocks['service_value']}",
                        f"   - promo IDs: {code_blocks['promo']}",
                        f"   - amplifier IDs: {code_blocks['amplifiers']}",
                        f"   - CTA/UI: {cta_ui_display}",
                        "7. **Commercial provenance (structured only):**",
                        f"   - raw direct_fact_ids: {commercial['raw_direct_fact_ids']}",
                        f"   - materialized direct_commercial_text: {commercial['materialized_direct_commercial_text']}",
                        f"   - code promo IDs: {commercial['code_promo_ids']}",
                        f"   - code amplifier IDs: {commercial['code_amplifier_ids']}",
                    ]
                )
                for theme_label, theme_row in commercial["themes"].items():
                    lines.append(
                        f"   - {theme_label}: patient_text={theme_row['patient_text_contains']}, "
                        f"visible={theme_row['visible_answer_contains']}, "
                        f"origin={theme_row['structured_origin']}"
                    )
                lines.extend(
                    [
                        "8. **Полный итоговый видимый ответ:**",
                        "",
                        visible,
                        "",
                        f"9. **Capture/persistence status:** `{persistence_status}`",
                        "",
                    ]
                )
    return "\n".join(lines)


def build_technical_report_markdown_v2(
    *,
    attempt_id: str,
    run_result: dict[str, Any],
    rebuilt_with_sha: str | None = None,
) -> str:
    structured = run_result.get("structured_turns") or []
    raw_turns = run_result.get("raw_turns") or []
    raw_by_key = {
        (str(r["scenario_id"]), str(r["turn_id"]), str(r["config_id"])): r for r in raw_turns
    }
    counters: AttemptPersistenceCounters | None = run_result.get("persistence_counters")

    lines = [
        f"# Architecture compare technical report v2 — `{attempt_id}`",
        "",
        f"- client: `{CLIENT_ID}`",
        *_sha_provenance_lines(run_result, rebuilt_with_sha=rebuilt_with_sha),
        f"- mode: `{run_result.get('mode')}`",
        f"- status: `{run_result.get('status')}`",
        f"- matrix_digest: `{run_result.get('matrix_digest')}`",
        f"- config_digest: `{run_result.get('config_digest')}`",
        f"- provider_call_total: `{run_result.get('provider_call_total')}`",
        f"- measurement_error_total: `{len(run_result.get('measurement_errors') or [])}`",
        f"- request_timeout_sec: `{EVAL_REQUEST_TIMEOUT_SEC}`",
        f"- production_sla_sec: `{PRODUCTION_SLA_REFERENCE_SEC}`",
        f"- fake_transport_call_total: `{run_result.get('fake_transport_call_total')}`",
        f"- live_readiness: `{(run_result.get('live_readiness') or {}).get('status')}`",
    ]
    if counters is not None:
        lines.extend(
            [
                f"- preflight_provider_calls_completed: `{counters.preflight_provider_calls_completed}`",
                f"- measurement_provider_calls_completed: `{counters.measurement_provider_calls_completed}`",
                f"- measurement_provider_calls_failed: `{counters.measurement_provider_calls_failed}`",
                f"- total_provider_call_ordinal: `{counters.total_provider_call_ordinal}`",
                f"- persisted_measurement_results: `{counters.persisted_measurement_results}`",
                f"- missing_persisted_results: `{counters.missing_persisted_results}`",
            ]
        )
    config_registry = run_result.get("config_registry")
    if config_registry:
        registry_block = json.dumps(config_registry, ensure_ascii=False, indent=2)
    else:
        registry_block = NOT_CAPTURED
    lines.extend(
        [
            "",
            "## Config registry",
            "",
        ]
    )
    if config_registry:
        lines.extend(["```json", registry_block, "```", ""])
    else:
        lines.append(registry_block)
        lines.append("")
    lines.extend(
        [
            "## Preflight",
            "",
            "```json",
            json.dumps(run_result.get("preflight") or {}, ensure_ascii=False, indent=2),
            "```",
            "",
            "## Schedule excerpt",
            "",
            f"scenario_config_jobs: {len((run_result.get('schedule') or {}).get('scenario_config_jobs') or [])}",
            f"turn_config_jobs: {len((run_result.get('schedule') or {}).get('turn_config_jobs') or [])}",
            "",
            "## Turn records",
            "",
        ]
    )
    for row in structured:
        key = (str(row["scenario_id"]), str(row["turn_id"]), str(row["config_id"]))
        raw = raw_by_key.get(key, {})
        token = row.get("token_metadata") or {}
        lines.extend(
            [
                f"### {key[0]} / {key[1]} / {row.get('config_id')}",
                "",
                f"- config_id: `{row.get('config_id')}`",
                f"- provider_model_id: `{row.get('provider_model_id')}`",
                f"- presentation_capture_status: `{row.get('presentation_capture_status')}`",
                f"- latency_ms: `{token.get('latency_ms')}`",
                f"- prompt_tokens: `{token.get('prompt_tokens')}`",
                f"- completion_tokens: `{token.get('completion_tokens')}`",
                f"- provider_error: `{token.get('provider_error')}`",
                f"- production_sla_breached: `{token.get('production_sla_breached')}`",
                f"- capture_status: `captured`",
                f"- persistence_status: `captured`",
                "",
            ]
        )
    if counters and counters.missing_persisted_results:
        lines.extend(["## Missing persisted results", ""])
        ledger = run_result.get("call_ledger") or {}
        missing_keys = _missing_persisted_measurement_keys(
            ledger=ledger,
            structured_turns=structured,
        )
        for scenario_id, turn_id, config_id in sorted(missing_keys):
            call = next(
                (
                    c
                    for c in ledger.get("calls") or []
                    if c.get("scenario_id") == scenario_id
                    and c.get("turn_id") == turn_id
                    and c.get("config_id") == config_id
                ),
                {},
            )
            lines.extend(
                [
                    f"### {scenario_id} / {turn_id} / {config_id}",
                    "",
                    f"- provider_call_ordinal: `{call.get('call_index')}`",
                    f"- provider_status: `{call.get('status')}`",
                    f"- persistence_status: `{PROVIDER_COMPLETED_NOT_PERSISTED}`",
                    "",
                ]
            )
    return "\n".join(lines)


def build_blind_review_json_v2(
    *,
    attempt_id: str,
    run_result: dict[str, Any],
    rebuilt_with_sha: str | None = None,
) -> dict[str, Any]:
    return {
        "attempt_id": attempt_id,
        "report_version": "v2",
        "source_attempt_sha": run_result.get("source_attempt_sha"),
        "rebuilt_with_sha": rebuilt_with_sha or run_result.get("rebuilt_with_sha"),
        "status": run_result.get("status"),
        "persistence_counters": _persistence_counters_payload(run_result.get("persistence_counters")),
        "scenarios": _public_review_payload_v2(run_result),
    }


def _public_review_payload_v2(run_result: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = run_result.get("blind_variant_mapping") or {}
    structured = run_result.get("structured_turns") or []
    scenarios = _scenario_index()
    payload: list[dict[str, Any]] = []
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for row in structured:
        by_scenario.setdefault(str(row["scenario_id"]), []).append(row)
    for scenario_id, rows in by_scenario.items():
        scenario = scenarios.get(scenario_id) or scenario_for_id(scenario_id)
        variant_to_config = mapping.get(scenario_id) or {}
        variants: dict[str, Any] = {}
        for variant in BLIND_VARIANTS:
            config_id = variant_to_config.get(variant)
            match = next((r for r in rows if r.get("config_id") == config_id), None)
            turn = _turn_spec(scenario, str((match or rows[0])["turn_id"]))
            variants[variant] = {
                "patient_text": _blind_safe_patient_text((match or {}).get("patient_text")),
                "model_price_text": _parse_envelope_price_text((match or {}).get("raw_model_envelope")),
                "matrix_expectation": _matrix_expectation_section(turn),
                "captured_precomposer": _captured_precomposer_section(match),
                "resolved_price": _resolved_price_section(match),
                "code_blocks": _code_blocks_section(match),
                "commercial_provenance": _commercial_provenance_section(
                    match,
                    patient_text=_blind_safe_patient_text((match or {}).get("patient_text")),
                    visible_answer=_blind_safe_visible_answer(
                        (match or {}).get("visible_answer"),
                        error_code=(match or {}).get("error_code"),
                        code_only=not bool((match or {}).get("provider_turn")),
                    ),
                ),
                "visible_answer": _blind_safe_visible_answer(
                    (match or {}).get("visible_answer"),
                    error_code=(match or {}).get("error_code"),
                    code_only=not bool((match or {}).get("provider_turn")),
                ),
                "capture_status": "captured" if match else NOT_CAPTURED,
            }
        payload.append({"scenario_id": scenario_id, "variants": variants})
    return payload


def write_rebuilt_reports(
    *,
    output_dir: Path,
    attempt_id: str,
    run_result: dict[str, Any],
    rebuilt_with_sha: str,
) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    run_with_sha = dict(run_result)
    run_with_sha["rebuilt_with_sha"] = rebuilt_with_sha
    blind_md = build_blind_review_markdown_v2(
        attempt_id=attempt_id,
        run_result=run_with_sha,
        rebuilt_with_sha=rebuilt_with_sha,
    )
    technical_md = build_technical_report_markdown_v2(
        attempt_id=attempt_id,
        run_result=run_with_sha,
        rebuilt_with_sha=rebuilt_with_sha,
    )
    blind_json = build_blind_review_json_v2(
        attempt_id=attempt_id,
        run_result=run_with_sha,
        rebuilt_with_sha=rebuilt_with_sha,
    )
    paths = {
        "blind_review_md": output_dir / "blind_review_v2.md",
        "blind_review_json": output_dir / "blind_review_v2.json",
        "technical_report_md": output_dir / "technical_report_v2.md",
        "persistence_summary_json": output_dir / "persistence_summary_v2.json",
    }
    paths["blind_review_md"].write_text(blind_md, encoding="utf-8")
    paths["technical_report_md"].write_text(technical_md, encoding="utf-8")
    paths["blind_review_json"].write_text(
        json.dumps(blind_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary = _persistence_counters_payload(run_result.get("persistence_counters"))
    paths["persistence_summary_json"].write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert_blind_review_secrecy(blind_md)
    assert_blind_review_secrecy(paths["blind_review_json"].read_text(encoding="utf-8"))
    for path in paths.values():
        if path.suffix in {".json", ".md"}:
            assert_no_secrets_in_text(path.read_text(encoding="utf-8"))
    return paths
