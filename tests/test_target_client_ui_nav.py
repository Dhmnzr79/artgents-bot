from __future__ import annotations

from core.target_client_ui_nav import (
    load_scope_nav_labels,
    load_stage_nav_labels,
    materialize_scope_nav_followups,
)


def test_demo_scope_nav_labels_loaded() -> None:
    labels = load_scope_nav_labels("demo", topic="implantation")
    assert labels["one_tooth"] == "Один зуб"
    assert labels["few_teeth"] == "Несколько зубов"
    assert labels["full_arch"] == "Вся челюсть"


def test_demo_stage_nav_labels_loaded() -> None:
    labels = load_stage_nav_labels("demo", topic="prosthetics")
    assert labels["natural_tooth_present"] == "Свой зуб сохранился"
    assert labels["implant_placed"] == "Имплант установлен"


def test_materialize_scope_nav_followups_has_three_extents() -> None:
    followups = materialize_scope_nav_followups("demo", topic="implantation")
    assert len(followups) == 3
    refs = {item.ref for item in followups}
    assert refs == {
        "target:ui_scope/implantation/one_tooth",
        "target:ui_scope/implantation/few_teeth",
        "target:ui_scope/implantation/full_arch",
    }
