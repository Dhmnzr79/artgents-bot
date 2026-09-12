"""Report and artifact writers for architecture comparison LIVE prep."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from evals.v5.arch_compare.arch_compare_contract import BLIND_VARIANTS, CLIENT_ID, CONFIG_IDS, FAKE_PATIENT_TEXT_PREFIX
from evals.v5.arch_compare.arch_compare_live_contract import (
    EVAL_REQUEST_TIMEOUT_SEC,
    FAKE_LIVE_DISCLAIMER,
    OWNER_REVIEW_SCALE_FIELDS,
    PRODUCTION_SLA_REFERENCE_SEC,
)
from evals.v5.arch_compare.arch_compare_live_persistence import PROVIDER_ERROR_REVIEW_TEXT

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9]{8,}"),
    re.compile(r"Authorization:\s*Bearer\s+\S+", re.IGNORECASE),
    re.compile(r"OPENAI_API_KEY\s*=\s*\S+"),
)

_BLIND_REVIEW_HIDDEN_TOKENS = (
    "flash_full",
    "flash_curated",
    "plus_full",
    "plus_curated",
    "context_mode",
    "provider_model_id",
    "presentation_capture_status",
    "qwen3.7-flash",
    "qwen3.7-plus",
    "latency_ms",
    "production_sla",
    "request_timeout_sec",
    FAKE_PATIENT_TEXT_PREFIX,
)


def artifact_dir_for_attempt(artifacts_root: Path, attempt_id: str) -> Path:
    return artifacts_root / attempt_id


def _format_optional_list(values: Any) -> str:
    if not values:
        return "—"
    return ", ".join(str(v) for v in values)


def _format_optional_dict(value: Any) -> str:
    if not value:
        return "—"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _public_review_text(text: str | None, *, code_only: bool, error_code: str | None = None) -> str:
    if error_code:
        return PROVIDER_ERROR_REVIEW_TEXT
    if code_only:
        return "ответ сформирован кодом"
    if not text:
        return "—"
    lines = []
    for line in str(text).splitlines():
        stripped = line.strip()
        if stripped.startswith(FAKE_PATIENT_TEXT_PREFIX):
            continue
        if ":" in stripped and any(config in stripped for config in CONFIG_IDS):
            if stripped.startswith("Ассистент:"):
                continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    return cleaned or "—"


def _public_history_for_review(history: str) -> str:
    if not history:
        return "—"
    patient_lines = [line for line in history.splitlines() if line.startswith("Пациент:")]
    return "\n".join(patient_lines).strip() or "—"


def owner_review_template() -> str:
    lines = [
        "## Шаблон оценки владельца (ручная)",
        "",
        "По каждому сценарию заполните:",
    ]
    for field in OWNER_REVIEW_SCALE_FIELDS:
        lines.append(f"- {field}")
    return "\n".join(lines)


def build_blind_review_markdown(*, attempt_id: str, run_result: dict[str, Any]) -> str:
    from evals.v5.arch_compare.arch_compare_live_report_v2 import build_blind_review_markdown_v2

    return build_blind_review_markdown_v2(
        attempt_id=attempt_id,
        run_result=run_result,
        rebuilt_with_sha=run_result.get("rebuilt_with_sha"),
    )


def build_technical_report_markdown(*, attempt_id: str, run_result: dict[str, Any]) -> str:
    from evals.v5.arch_compare.arch_compare_live_report_v2 import build_technical_report_markdown_v2

    return build_technical_report_markdown_v2(
        attempt_id=attempt_id,
        run_result=run_result,
        rebuilt_with_sha=run_result.get("rebuilt_with_sha"),
    )


def build_blind_review_json(*, attempt_id: str, run_result: dict[str, Any]) -> dict[str, Any]:
    from evals.v5.arch_compare.arch_compare_live_report_v2 import build_blind_review_json_v2

    return build_blind_review_json_v2(attempt_id=attempt_id, run_result=run_result)


def _public_review_payload(run_result: dict[str, Any]) -> list[dict[str, Any]]:
    mapping = run_result.get("blind_variant_mapping") or {}
    structured = run_result.get("structured_turns") or []
    payload: list[dict[str, Any]] = []
    by_scenario: dict[str, list[dict[str, Any]]] = {}
    for row in structured:
        by_scenario.setdefault(str(row["scenario_id"]), []).append(row)
    for scenario_id, rows in by_scenario.items():
        variant_to_config = mapping.get(scenario_id) or {}
        variants: dict[str, Any] = {}
        for variant in BLIND_VARIANTS:
            config_id = variant_to_config.get(variant)
            match = next((r for r in rows if r.get("config_id") == config_id), None)
            code_only = not bool((match or {}).get("provider_turn"))
            variants[variant] = {
                "visible_answer": _public_review_text(
                    (match or {}).get("visible_answer"),
                    code_only=code_only,
                    error_code=(match or {}).get("error_code"),
                ),
                "canonical_price_block": (match or {}).get("canonical_price_block"),
                "service_value_id": (match or {}).get("service_value_id"),
                "service_value_text": (match or {}).get("service_value_text"),
                "promo_fact_ids": (match or {}).get("promo_fact_ids"),
                "amplifier_fact_ids": (match or {}).get("amplifier_fact_ids"),
                "cta_ui_metadata": (match or {}).get("cta_ui_metadata"),
            }
        payload.append({"scenario_id": scenario_id, "variants": variants})
    return payload


def assert_no_secrets_in_text(text: str) -> None:
    for pattern in _SECRET_PATTERNS:
        if pattern.search(text):
            raise RuntimeError("artifact_secret_leak_detected")


def assert_blind_review_secrecy(text: str) -> None:
    lowered = text.casefold()
    for token in _BLIND_REVIEW_HIDDEN_TOKENS:
        if token.casefold() in lowered:
            raise RuntimeError(f"blind_review_secret_leak:{token}")


def persist_live_prep_artifacts(
    *,
    artifacts_root: Path,
    attempt_id: str,
    run_result: dict[str, Any],
    stdout_log: str = "",
) -> dict[str, Path]:
    out_dir = artifact_dir_for_attempt(artifacts_root, attempt_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "attempt_id": attempt_id,
        "measurement_id": run_result.get("measurement_id"),
        "live_prep_measurement_id": run_result.get("live_prep_measurement_id"),
        "mode": run_result.get("mode"),
        "client_id": CLIENT_ID,
        "head_sha": run_result.get("head_sha"),
        "matrix_digest": run_result.get("matrix_digest"),
        "config_digest": run_result.get("config_digest"),
        "call_budget": run_result.get("call_budget"),
        "preflight": run_result.get("preflight"),
        "provider_call_total": run_result.get("provider_call_total"),
        "fake_transport_call_total": run_result.get("fake_transport_call_total"),
        "live_readiness": run_result.get("live_readiness"),
        "disclaimer": run_result.get("disclaimer"),
    }
    schedule = run_result.get("schedule") or {}
    blind_mapping = {
        "attempt_id": attempt_id,
        "mapping": run_result.get("blind_variant_mapping"),
        "note": "closed mapping — not for reviewer markdown",
    }
    blind_review_md = build_blind_review_markdown(attempt_id=attempt_id, run_result=run_result)
    technical_md = build_technical_report_markdown(attempt_id=attempt_id, run_result=run_result)
    blind_review_json = build_blind_review_json(attempt_id=attempt_id, run_result=run_result)

    paths = {
        "dir": out_dir,
        "manifest_json": out_dir / "manifest.json",
        "schedule_json": out_dir / "schedule.json",
        "raw_turns_json": out_dir / "raw_turns.json",
        "structured_turns_json": out_dir / "structured_turns.json",
        "blind_review_md": out_dir / "blind_review.md",
        "blind_review_json": out_dir / "blind_review.json",
        "blind_variant_mapping_json": out_dir / "blind_variant_mapping.json",
        "technical_report_md": out_dir / "technical_report.md",
        "run_stdout_log": out_dir / "run_stdout.log",
    }
    paths["manifest_json"].write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["schedule_json"].write_text(json.dumps(schedule, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    paths["raw_turns_json"].write_text(
        json.dumps(run_result.get("raw_turns") or [], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["structured_turns_json"].write_text(
        json.dumps(run_result.get("structured_turns") or [], ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["blind_review_md"].write_text(blind_review_md, encoding="utf-8")
    paths["blind_review_json"].write_text(
        json.dumps(blind_review_json, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["blind_variant_mapping_json"].write_text(
        json.dumps(blind_mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    paths["technical_report_md"].write_text(technical_md, encoding="utf-8")
    paths["run_stdout_log"].write_text(stdout_log, encoding="utf-8")

    assert_blind_review_secrecy(blind_review_md)
    assert_blind_review_secrecy(paths["blind_review_json"].read_text(encoding="utf-8"))
    for path in paths.values():
        if path.suffix in {".json", ".md", ".log"}:
            assert_no_secrets_in_text(path.read_text(encoding="utf-8"))
    return paths


def finalize_live_artifacts(
    *,
    store,
    run_result: dict[str, Any],
    stdout_log: str = "",
) -> dict[str, Path]:
    out_dir = store.artifact_dir
    blind_mapping = {
        "attempt_id": store.attempt_id,
        "mapping": run_result.get("blind_variant_mapping"),
        "note": "closed mapping — not for reviewer markdown",
    }
    manifest = dict(store.manifest)
    counters = None
    if store.ledger.entries:
        from evals.v5.arch_compare.arch_compare_live_report_v2 import compute_persistence_counters

        counters = compute_persistence_counters(
            ledger=store.ledger.to_dict(),
            structured_turns=store.structured_turns,
            raw_turns=store.raw_turns,
        )
    run_result_with_ledger = dict(run_result)
    run_result_with_ledger["call_ledger"] = store.ledger.to_dict()
    if counters is not None:
        run_result_with_ledger["persistence_counters"] = counters
    blind_review_md = build_blind_review_markdown(attempt_id=store.attempt_id, run_result=run_result_with_ledger)
    technical_md = build_technical_report_markdown(attempt_id=store.attempt_id, run_result=run_result_with_ledger)
    blind_review_json = build_blind_review_json(attempt_id=store.attempt_id, run_result=run_result_with_ledger)

    from evals.v5.arch_compare.arch_compare_live_persistence import atomic_write_json, atomic_write_text

    manifest = dict(store.manifest)
    manifest.update(
        {
            "mode": run_result.get("mode"),
            "status": run_result.get("status"),
            "preflight": run_result.get("preflight"),
            "provider_call_total": run_result.get("provider_call_total"),
            "measurement_error_total": len(run_result.get("measurement_errors") or []),
            "live_readiness": run_result.get("live_readiness"),
        }
    )
    atomic_write_json(out_dir / "manifest.json", manifest)
    atomic_write_json(out_dir / "raw_turns.json", run_result.get("raw_turns") or [])
    atomic_write_json(out_dir / "structured_turns.json", run_result.get("structured_turns") or [])
    atomic_write_text(out_dir / "blind_review.md", blind_review_md)
    atomic_write_json(out_dir / "blind_review.json", blind_review_json)
    atomic_write_json(out_dir / "blind_variant_mapping.json", blind_mapping)
    atomic_write_text(out_dir / "technical_report.md", technical_md)
    atomic_write_text(out_dir / "run_stdout.log", stdout_log)

    assert_blind_review_secrecy(blind_review_md)
    assert_blind_review_secrecy((out_dir / "blind_review.json").read_text(encoding="utf-8"))
    for path in out_dir.glob("*"):
        if path.suffix in {".json", ".md", ".log"}:
            assert_no_secrets_in_text(path.read_text(encoding="utf-8"))

    return {
        "dir": out_dir,
        "manifest_json": out_dir / "manifest.json",
        "schedule_json": out_dir / "schedule.json",
        "call_ledger_json": out_dir / "call_ledger.json",
        "raw_turns_json": out_dir / "raw_turns.json",
        "structured_turns_json": out_dir / "structured_turns.json",
        "blind_review_md": out_dir / "blind_review.md",
        "blind_review_json": out_dir / "blind_review.json",
        "blind_variant_mapping_json": out_dir / "blind_variant_mapping.json",
        "technical_report_md": out_dir / "technical_report.md",
        "run_stdout_log": out_dir / "run_stdout.log",
    }
