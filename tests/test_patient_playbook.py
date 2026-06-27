"""Patient situation marketing playbook (options overview)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import yaml

from contracts.patient_situation import (
    PatientSituationCues,
    PatientSituationResult,
)
from core.patient_playbook import (
    build_patient_options_llm_context,
    load_patient_playbook,
    select_patient_options,
    should_use_patient_options_overview,
)
from core.patient_situation import detect_patient_situation


def test_load_demo_playbook_full_arch():
    playbook = load_patient_playbook("demo")
    assert playbook is not None
    assert "full_arch_missing" in playbook
    cfg = playbook["full_arch_missing"]
    assert cfg.strategy == "fixed_implant_first"
    assert not hasattr(cfg, "intro")


def test_yaml_has_no_canned_answer_fields():
    raw = yaml.safe_load(
        Path("clients/demo/patient_playbook.yaml").read_text(encoding="utf-8")
    )
    situation = raw["patient_situations"]["full_arch_missing"]
    assert "intro" not in situation
    assert "closer" not in situation
    for opt in situation["options"]:
        assert "short_text" not in opt


def test_full_arch_missing_selects_priority_order():
    situation = detect_patient_situation("Что делать, если нет зубов вообще?")
    assert situation.kind == "full_arch_missing"
    result = select_patient_options(situation, "Что делать, если нет зубов вообще?", "demo")
    assert result is not None
    assert result.option_service_ids[:3] == ["all_on_4", "all_on_6", "removable_dentures"]
    assert "zygomatic_implants" not in result.option_service_ids
    assert "zygomatic_implants" in result.skipped_options
    assert result.strategy == "fixed_implant_first"


def test_zygomatic_when_upper_jaw_bone_context():
    situation = PatientSituationResult(
        kind="full_arch_missing",
        confidence=0.9,
        source="rule_based",
        patient_scope="full_jaw",
        cues=PatientSituationCues(
            quantity="jaw",
            anatomy=["upper_jaw", "bone"],
            state=["bone_deficit", "missing"],
            intent="choose_solution",
        ),
    )
    result = select_patient_options(
        situation,
        "Нет зубов на верхней челюсти, мало кости — какие варианты?",
        "demo",
    )
    assert result is not None
    assert "zygomatic_implants" in result.option_service_ids


def test_missing_service_id_skipped_fail_open():
    situation = detect_patient_situation("Что делать, если нет зубов вообще?")
    with patch("core.patient_playbook._service_available") as mock_avail:
        mock_avail.side_effect = lambda _cid, sid: sid != "all_on_4"
        result = select_patient_options(situation, "нет зубов вообще", "demo")
    assert result is not None
    assert "all_on_4" not in result.option_service_ids
    assert "all_on_4" in result.skipped_options
    assert result.option_service_ids[0] == "all_on_6"


def test_no_playbook_returns_none():
    with patch("core.patient_playbook.load_patient_playbook", return_value=None):
        situation = detect_patient_situation("Что делать, если нет зубов вообще?")
        assert select_patient_options(situation, "нет зубов", "demo") is None


def test_should_use_overview_for_choose_solution_not_price():
    situation = detect_patient_situation("Что делать, если нет зубов вообще?")
    assert should_use_patient_options_overview(
        "Что делать, если нет зубов вообще?",
        situation,
        decision=None,
        intent="content",
        client_id="demo",
    )
    assert not should_use_patient_options_overview(
        "Сколько стоит All-on-4?",
        detect_patient_situation("Сколько стоит All-on-4?"),
        decision=None,
        intent="price_lookup",
        client_id="demo",
    )


def test_should_not_use_for_specific_service_explain():
    situation = detect_patient_situation("Расскажите про all-on-4")
    assert not should_use_patient_options_overview(
        "Расскажите про all-on-4",
        situation,
        decision=None,
        intent="content",
        client_id="demo",
    )


def test_llm_context_contains_selected_options_not_canned_copy():
    situation = detect_patient_situation("Нужно восстановить всю челюсть, какие варианты?")
    result = select_patient_options(situation, "Нужно восстановить всю челюсть, какие варианты?", "demo")
    assert result is not None
    ctx = build_patient_options_llm_context(result, client_id="demo")
    assert ctx["strategy"] == "fixed_implant_first"
    opts = ctx["selected_options"]
    assert len(opts) >= 3
    assert opts[0]["service_id"] == "all_on_4"
    assert opts[0]["role"] == "main_fixed_solution"
    assert opts[0]["positioning"] == "primary"
    assert "display_name" in opts[0]
    assert "intro" not in ctx
    assert "closer" not in ctx
    assert "short_text" not in opts[0]
