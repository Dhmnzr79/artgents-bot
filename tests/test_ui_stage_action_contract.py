from __future__ import annotations

import pytest

from contracts.ui_stage_action import (
    UiStageAction,
    build_ui_stage_ref,
    is_ui_stage_ref,
    parse_ui_stage_ref,
)


def test_build_and_parse_ui_stage_ref() -> None:
    ref = build_ui_stage_ref(topic="prosthetics", stage="natural_tooth_present")
    assert ref == "target:ui_stage/prosthetics/natural_tooth_present"
    action = parse_ui_stage_ref(ref)
    assert action is not None
    assert action.stage == "natural_tooth_present"
    assert action.topic == "prosthetics"


def test_malformed_ui_stage_ref_returns_none() -> None:
    assert parse_ui_stage_ref("target:ui_stage/bad") is None
    assert not is_ui_stage_ref("target:ui_scope/implantation/one_tooth")


def test_ui_stage_action_extra_forbidden() -> None:
    with pytest.raises(Exception):
        UiStageAction.model_validate(
            {
                "stage": "implant_placed",
                "topic": "prosthetics",
                "ref": build_ui_stage_ref(topic="prosthetics", stage="implant_placed"),
                "unexpected": True,
            }
        )
