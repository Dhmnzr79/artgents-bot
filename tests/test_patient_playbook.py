"""Patient situation marketing playbook (options overview)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import yaml

from contracts.patient_situation import (
    PatientSituationCues,
    PatientSituationResult,
)
from core.patient_playbook import (
    build_patient_options_llm_context,
    load_patient_playbook,
    load_patient_playbook_rules,
    patient_options_quick_replies,
    select_patient_options,
    should_use_patient_options_overview,
)
from core.patient_situation import detect_patient_situation


def test_load_demo_playbook_full_arch():
    playbook = load_patient_playbook("demo")
    assert playbook is not None
    assert "full_arch_missing" in playbook
    rules = load_patient_playbook_rules("demo")
    assert rules is not None
    assert {rule.id for rule in rules} >= {
        "one_tooth_restore",
        "extraction_then_implant_restore",
        "few_teeth_restore",
        "existing_implant_prosthetic_stage",
        "full_arch_restore",
        "upper_full_arch_restore",
        "upper_full_arch_with_bone_deficit",
        "bone_deficit_solution",
    }
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
    assert result.matched_rule_id == "full_arch_restore"
    assert result.option_service_ids[:3] == ["all_on_4", "all_on_6", "removable_dentures"]
    assert "zygomatic_implants" not in result.option_service_ids
    assert "zygomatic_implants" in result.skipped_options
    assert result.strategy == "fixed_implant_first"


def test_one_tooth_restore_uses_demo_playbook_without_extraction_option():
    q = "Что мне подойдёт, если нет одного зуба?"
    situation = detect_patient_situation(q)
    assert situation.kind == "one_tooth_missing"
    assert situation.extent == "one_tooth"

    assert should_use_patient_options_overview(
        q,
        situation,
        decision=None,
        intent="content",
        client_id="demo",
    )
    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "one_tooth_restore"
    assert result.strategy == "one_tooth_implant_first"
    assert result.option_service_ids == ["classic"]
    assert "one_stage" in result.skipped_options


def test_extraction_then_implant_prefers_one_stage_then_classic():
    q = "Нужно удалить зуб и поставить имплант, какие варианты?"
    situation = detect_patient_situation(q)
    assert situation.kind == "extraction_then_implant"

    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "extraction_then_implant_restore"
    assert result.strategy == "extraction_implant_ct_first"
    assert result.option_service_ids[:2] == ["one_stage", "classic"]
    assert "tooth_extraction" in result.option_service_ids


def test_few_teeth_restore_uses_demo_playbook():
    q = "Не хватает нескольких зубов, что лучше поставить?"
    situation = detect_patient_situation(q)
    assert situation.kind == "few_teeth_missing"
    assert situation.extent == "few_teeth"

    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "few_teeth_restore"
    assert result.strategy == "fixed_or_removable_by_defect"
    assert result.option_service_ids[:2] == ["implant_supported_prosthetics", "classic"]


def test_existing_implant_stage_uses_prosthetic_playbook():
    q = "Имплант уже стоит, нужна коронка, что дальше?"
    situation = detect_patient_situation(q)
    assert situation.kind == "existing_implant_prosthetic_stage"
    assert situation.cues.intent == "choose_solution"

    assert should_use_patient_options_overview(
        q,
        situation,
        decision=None,
        intent="content",
        client_id="demo",
    )

    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "existing_implant_prosthetic_stage"
    assert result.strategy == "prosthetic_stage_first"
    assert result.option_service_ids[0] == "implant_supported_prosthetics"


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


def test_upper_jaw_restore_uses_composable_rule():
    q = "Нужно восстановить верхнюю челюсть"
    situation = detect_patient_situation(q)
    assert situation.kind == "upper_jaw_missing_or_complex"
    assert situation.extent == "full_arch"
    assert situation.jaw == "upper"

    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "upper_full_arch_restore"
    assert result.strategy == "upper_jaw_fixed_first"
    assert result.option_service_ids[:3] == ["all_on_4", "all_on_6", "zygomatic_implants"]


def test_upper_jaw_bone_deficit_prefers_complex_rule():
    q = "Нет зубов на верхней челюсти, мало кости, что посоветуете?"
    situation = detect_patient_situation(q)
    assert situation.extent == "full_arch"
    assert situation.jaw == "upper"
    assert "bone_deficit" in situation.modifiers

    result = select_patient_options(situation, q, "demo")

    assert result is not None
    assert result.matched_rule_id == "upper_full_arch_with_bone_deficit"
    assert result.strategy == "upper_jaw_complex_fixed_first"
    assert result.option_service_ids[:2] == ["zygomatic_implants", "all_on_4"]


def test_bone_deficit_advice_can_enter_options_overview_with_service_candidate():
    q = "А если мало кости, то что посоветуете?"
    situation = detect_patient_situation(q)
    assert situation.kind == "bone_deficit_or_grafting"
    assert situation.cues.intent == "choose_solution"

    decision = SimpleNamespace(
        service_id="sinus_lift",
        confidence={"service": 0.95},
        query_mode="specific",
        route_intent="content",
    )

    assert should_use_patient_options_overview(
        q,
        situation,
        decision=decision,
        intent="content",
        client_id="demo",
    )
    result = select_patient_options(situation, q, "demo")
    assert result is not None
    assert result.matched_rule_id == "bone_deficit_solution"
    assert result.strategy == "bone_deficit_ct_first"
    assert result.option_service_ids == ["sinus_lift", "all_on_4", "zygomatic_implants"]


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


def test_patient_options_buttons_open_md_not_price():
    situation = detect_patient_situation("Нужно восстановить всю челюсть, какие варианты?")
    result = select_patient_options(
        situation,
        "Нужно восстановить всю челюсть, какие варианты?",
        "demo",
    )

    assert result is not None
    quick = patient_options_quick_replies(result, client_id="demo")
    refs = [item["ref"] for item in quick]

    assert "implantation__service__all_on_4.md#korotko" in refs
    assert "implantation__service__all_on_6.md#korotko" in refs
    assert all(not ref.startswith("price:") for ref in refs)
    assert all(item.get("source") == "patient_option" for item in quick)
    assert all(not item["label"].startswith("Подробнее про ") for item in quick)
