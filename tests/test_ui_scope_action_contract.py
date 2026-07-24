from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.ui_scope_action import (
    UiScopeAction,
    build_ui_scope_ref,
    is_ui_scope_ref,
    parse_ui_scope_ref,
)


def test_ui_scope_action_contract_valid() -> None:
    ref = build_ui_scope_ref(topic="implantation", extent="one_tooth")
    action = UiScopeAction(extent="one_tooth", topic="implantation", ref=ref)
    assert action.provenance == "ui_scope_ref"
    assert action.topic == "implantation"


def test_ui_scope_action_extra_forbidden() -> None:
    ref = build_ui_scope_ref(topic="implantation", extent="few_teeth")
    with pytest.raises(ValidationError):
        UiScopeAction.model_validate(
            {
                "extent": "few_teeth",
                "topic": "implantation",
                "ref": ref,
                "service_id": "all_on_4",
            }
        )


def test_build_and_parse_ui_scope_ref_roundtrip() -> None:
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    assert is_ui_scope_ref(ref)
    parsed = parse_ui_scope_ref(ref)
    assert parsed is not None
    assert parsed.extent == "full_arch"
    assert parsed.topic == "implantation"
    assert parsed.ref == ref


def test_parse_ui_scope_ref_rejects_malformed() -> None:
    assert parse_ui_scope_ref("target:ui_scope/implantation/bad_extent") is None
    assert parse_ui_scope_ref("price:all_on_4/stages") is None
    assert parse_ui_scope_ref("") is None


def test_ui_scope_action_normalizes_topic() -> None:
    ref = build_ui_scope_ref(topic="Implantation", extent="one_tooth")
    action = UiScopeAction(extent="one_tooth", topic="Implantation", ref=ref)
    assert action.topic == "implantation"
