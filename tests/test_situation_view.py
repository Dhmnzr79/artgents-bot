from __future__ import annotations

from contracts.patient_playbook import PatientOption, PatientOptionsResult
from core.answer_lens import situation_view


def _options_result(*, include_missing: bool = False) -> PatientOptionsResult:
    options = [
        PatientOption(
            service_id="all_on_4",
            display_name="All-on-4",
            role="main_fixed_solution",
            positioning="fixed option",
            priority=100,
        ),
        PatientOption(
            service_id="all_on_6",
            display_name="All-on-6",
            role="stronger_fixed_solution",
            positioning="stronger fixed option",
            priority=90,
        ),
        PatientOption(
            service_id="removable_dentures",
            display_name="Removable dentures",
            role="budget_alternative",
            positioning="budget option",
            priority=60,
        ),
    ]
    if include_missing:
        options.insert(
            1,
            PatientOption(
                service_id="definitely_missing",
                display_name="Missing",
                role="missing_role",
                positioning="missing positioning",
                priority=95,
            ),
        )
    return PatientOptionsResult(
        situation_kind="full_arch_missing",
        patient_scope="full_jaw",
        options=options,
        primary_cta="consult",
        strategy="compare_fixed_and_budget_options",
    )


def test_situation_view_projects_ordered_options_to_service_nodes():
    view = situation_view(_options_result(), "demo")

    assert len(view.items) == 3
    assert [item.node.service_id for item in view.items] == [
        "all_on_4",
        "all_on_6",
        "removable_dentures",
    ]
    assert view.items[0].node.offers
    assert view.items[0].role == "main_fixed_solution"
    assert view.items[1].role == "stronger_fixed_solution"
    assert view.items[2].role == "budget_alternative"
    assert view.situation_kind == "full_arch_missing"
    assert view.patient_scope == "full_jaw"
    assert view.primary_cta == "consult"
    assert view.strategy == "compare_fixed_and_budget_options"


def test_situation_view_skips_missing_service_nodes():
    view = situation_view(_options_result(include_missing=True), "demo")

    assert [item.node.service_id for item in view.items] == [
        "all_on_4",
        "all_on_6",
        "removable_dentures",
    ]
    assert all(item.role != "missing_role" for item in view.items)
