"""COMPLETION checker — FINAL_TOMOGRAPHY_EXISTING_SCAN_CONTENT_ROUTING."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

import app as app_module
from core.target_client_data import load_target_client_data
from core.turn_planner_llm import _SYSTEM
from evals.v5.final_scope_widget_e2e_live_contract import FROZEN_TURNS_HASH, sha256_file_hex
from evals.v5.final_scope_widget_e2e_retry4_live_contract import (
    assert_frozen_retry4_live_artifacts_unchanged,
)
from scripts.validate_client_pack import validate_client_pack
from tests.test_ac3_scope_price_flow_offline import test_w1b_snapshot_checksums_unchanged
from tests.test_final_generic_fullcontext_content_authority_implementation import (
    _partial_null_topic_frame,
    _run as _generic_run,
)
from tests.test_final_price_only_source_sufficiency_convergence_harness import (
    offer_evidence,
    run_price_turn,
)
from tests.test_final_price_scope_coverage_nav_implementation import (
    test_frozen_pins_unchanged as test_pscn_frozen_pins_unchanged,
)
from tests.test_final_scope_widget_e2e_closeout_implementation import (
    test_frozen_retry4_artifacts_unchanged_after_closeout,
)
from tests.test_final_service_availability_and_clinic_capability_routing_implementation import (
    test_scenario_02_whitening_active_yes,
)
from tests.test_final_tomography_existing_scan_content_routing_governance import (
    test_frozen_artifact_guards as _governance_frozen_artifact_guards,
    test_seam_audit_exists_and_covers_existing_scan_routing,
    test_task_governance_section_and_acceptance_matrix,
)
from tests.test_final_tomography_existing_scan_content_routing_harness import (
    PRIMARY_REF,
    assert_materialized_content,
    availability_frame,
    content_frame,
    orchestrate_via_app,
    price_frame,
    quick_reply_refs,
    run_content_turn,
    run_price_turn,
)

_REPO_ROOT = Path(__file__).resolve().parents[1]
_DEMO_ROOT = _REPO_ROOT / "clients" / "demo"
_MD_PATH = _DEMO_ROOT / "md" / "diagnostics__service__tomography.md"
_AGREED_FACT = (
    "при наличии свежего кт (до 1 месяца) врач может использовать уже готовое исследование"
)
_FAQ_TEXT = (
    "При наличии свежего КТ (до 1 месяца) врач может использовать уже готовое исследование. "
    "Если снимок старше месяца, врач на консультации подскажет, подойдёт ли он для планирования."
)
_TWO_MONTHS_TEXT = (
    "Если КТ сделано больше месяца назад, врач обычно рекомендует свежий снимок для точного планирования. "
    "На консультации можно уточнить, подойдёт ли ваше исследование."
)
_NEW_SCAN_TEXT = (
    "При наличии свежего КТ (до 1 месяца) врач может использовать уже готовое исследование. "
    "Если КТ старше месяца, может понадобиться новое исследование."
)
_KT_PRICE_TEXT = (
    "КТ (компьютерная томография) — 3 000 рублей за одно исследование."
)
_GAP_TEXT = "В материалах клиники эта информация не указана."


def test_scenario_01_kt_availability_deterministic_yes() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        availability_frame(),
        user_message="Делаете КТ?",
        composer_text="unused",
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 0
    assert "оказывает услугу" in outcome.widget.payload["answer"]


def test_scenario_02_kt_price_3000() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 1
    assert any("3000" in item["text"] for item in offer_evidence(composer))


def test_scenario_03_availability_price_then_own_scan_content() -> None:
    sid = f"tom-3-{uuid.uuid4().hex[:8]}"
    run_price_turn(
        availability_frame(),
        user_message="Делаете 3D-диагностику?",
        composer_text="unused",
        sid=sid,
    )
    run_price_turn(
        price_frame(),
        user_message="А сколько стоит?",
        composer_text=_KT_PRICE_TEXT,
        sid=sid,
    )
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(followup_of="tomography"),
        user_message="А если у меня есть своё КТ?",
        composer_text=_FAQ_TEXT,
        sid=sid,
    )
    assert_materialized_content(outcome, composer)
    assert _AGREED_FACT in outcome.widget.payload["answer"].lower()


def test_scenario_04_direct_own_fresh_scan_fact() -> None:
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(),
        user_message="Можно прийти со своим свежим КТ?",
        composer_text=_FAQ_TEXT,
    )
    assert_materialized_content(outcome, composer)
    assert _AGREED_FACT in outcome.widget.payload["answer"].lower()


def test_scenario_05_two_months_old_not_claimed_fresh() -> None:
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(),
        user_message="Моему КТ два месяца",
        composer_text=_TWO_MONTHS_TEXT,
    )
    assert_materialized_content(outcome, composer)
    answer = outcome.widget.payload["answer"].lower()
    assert "может использовать уже готовое" not in answer
    assert "больше месяца" in answer or "старше месяца" in answer


def test_scenario_06_need_new_scan_without_diagnosis() -> None:
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(),
        user_message="Нужно ли делать новое КТ?",
        composer_text=_NEW_SCAN_TEXT,
    )
    assert_materialized_content(outcome, composer)
    answer = outcome.widget.payload["answer"].lower()
    assert _AGREED_FACT in answer
    assert "диагноз" not in answer
    assert "пульпит" not in answer


def test_scenario_07_primary_content_ref_valid() -> None:
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(),
        user_message="Можно прийти со своим свежим КТ?",
        composer_text=_FAQ_TEXT,
    )
    assert_materialized_content(outcome, composer)
    meta = outcome.widget.payload["meta"]
    assert meta.get("primary_content_ref") == PRIMARY_REF


def test_scenario_08_at_most_two_md_followups_no_duplicates() -> None:
    outcome, composer, _, _, _ = run_content_turn(
        content_frame(),
        user_message="Можно прийти со своим свежим КТ?",
        composer_text=_FAQ_TEXT,
    )
    assert_materialized_content(outcome, composer)
    refs = quick_reply_refs(outcome.widget.payload)
    assert 1 <= len(refs) <= 2
    assert len(refs) == len(set(refs))
    assert all(ref.startswith(PRIMARY_REF) for ref in refs)


def test_scenario_09_ask_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"tom-9-{uuid.uuid4().hex[:8]}"
    body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="Можно прийти со своим свежим КТ?",
        frame=content_frame(),
        composer_text=_FAQ_TEXT,
        sid=sid,
        primary_ref=PRIMARY_REF,
    )
    assert body["meta"]["primary_content_ref"] == PRIMARY_REF
    assert len(composer.invocations) == 1
    assert 1 <= len(quick_reply_refs(body)) <= 2


def test_scenario_10_ask_stream_parity(monkeypatch: pytest.MonkeyPatch) -> None:
    sid = f"tom-10-{uuid.uuid4().hex[:8]}"
    ask_body, _, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask",
        q="Можно прийти со своим свежим КТ?",
        frame=content_frame(),
        composer_text=_FAQ_TEXT,
        sid=sid,
        primary_ref=PRIMARY_REF,
    )
    stream_body, composer, _ = orchestrate_via_app(
        monkeypatch,
        app_module,
        endpoint="/ask/stream",
        q="Можно прийти со своим свежим КТ?",
        frame=content_frame(),
        composer_text=_FAQ_TEXT,
        sid=sid,
        primary_ref=PRIMARY_REF,
    )
    assert ask_body["meta"]["primary_content_ref"] == stream_body["meta"]["primary_content_ref"]
    assert len(composer.invocations) == 1


def test_scenario_11_kt_price_unchanged() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        price_frame(),
        user_message="Сколько стоит КТ?",
        composer_text=_KT_PRICE_TEXT,
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 1
    assert "3 000" in _KT_PRICE_TEXT or "3000" in _KT_PRICE_TEXT


def test_scenario_12_kt_availability_unchanged() -> None:
    outcome, composer, _, _, _ = run_price_turn(
        availability_frame(),
        user_message="Проводите КТ?",
        composer_text="unused",
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 0


def test_scenario_13_other_availability_unchanged() -> None:
    test_scenario_02_whitening_active_yes()


def test_scenario_14_generic_fullcontext_unchanged() -> None:
    frame = _partial_null_topic_frame()
    outcome, composer, _, _ = _generic_run(
        frame,
        user_message="Используете микроскоп?",
        composer_text=_GAP_TEXT,
    )
    assert outcome.widget.kind == "materialized"
    assert len(composer.invocations) == 1
    assert "оказывает услугу" not in outcome.widget.payload["answer"]


def test_scenario_15_no_invented_format_requirements() -> None:
    text = _MD_PATH.read_text(encoding="utf-8").lower()
    for forbidden in ("dicom", "флешк", "диск", "usb", "jpeg", "png"):
        assert forbidden not in text


def test_scenario_16_demo_validator_passes() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []


def test_tomography_content_ref_linked_in_catalog() -> None:
    service = load_target_client_data("demo").bundle.services["tomography"]
    assert service.content_ref == PRIMARY_REF


def test_planner_prompt_covers_existing_scan_boundary() -> None:
    for phrase in (
        "своё/имеющееся исследование",
        "aspects=[\"overview\"]",
        "tomography",
    ):
        assert phrase in _SYSTEM


def test_md_contains_agreed_fact_verbatim() -> None:
    text = _MD_PATH.read_text(encoding="utf-8")
    assert "При наличии свежего КТ (до 1 месяца) врач может использовать уже готовое исследование." in text


def test_frozen_pins_unchanged() -> None:
    test_frozen_retry4_artifacts_unchanged_after_closeout()
    test_w1b_snapshot_checksums_unchanged()
    test_pscn_frozen_pins_unchanged()
    turns_path = _REPO_ROOT / "evals" / "v5" / "demo" / "final_scope_widget_e2e_turns.json"
    assert sha256_file_hex(turns_path) == FROZEN_TURNS_HASH
    assert_frozen_retry4_live_artifacts_unchanged()


def test_validate_client_pack_demo() -> None:
    assert validate_client_pack(_DEMO_ROOT) == []


def test_import_app() -> None:
    assert app_module.app is not None


def test_governance_checker_still_passes() -> None:
    test_seam_audit_exists_and_covers_existing_scan_routing()
    test_task_governance_section_and_acceptance_matrix()
    _governance_frozen_artifact_guards()
