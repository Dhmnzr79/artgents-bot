from __future__ import annotations

import pytest
from pydantic import ValidationError

from contracts.effective_scope import EffectiveScope
from core.target_effective_scope import (
    SessionPatientFacts,
    resolve_effective_scope,
    session_patient_facts_from_ui_action,
)
from contracts.ui_scope_action import UiScopeAction, build_ui_scope_ref


def _action(*, topic: str = "implantation", extent: str = "one_tooth") -> UiScopeAction:
    ref = build_ui_scope_ref(topic=topic, extent=extent)  # type: ignore[arg-type]
    return UiScopeAction(extent=extent, topic=topic, ref=ref)  # type: ignore[arg-type]


def test_effective_scope_contract_unknown_defaults() -> None:
    scope = EffectiveScope()
    assert scope.extent == "unknown"
    assert scope.source == "unknown"


def test_effective_scope_contract_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        EffectiveScope.model_validate({"extent": "one_tooth", "service_id": "all_on_4"})


def test_resolve_effective_scope_unknown_without_inputs() -> None:
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=None,
        current_topic="implantation",
        session_turn_count=1,
    )
    assert scope.extent == "unknown"
    assert scope.source == "unknown"


def test_current_ui_action_beats_session() -> None:
    session = session_patient_facts_from_ui_action(
        _action(extent="full_arch"),
        set_at_turn=1,
    )
    scope = resolve_effective_scope(
        current_ui_action=_action(extent="one_tooth"),
        session_facts=session,
        current_topic="implantation",
        session_turn_count=3,
    )
    assert scope.extent == "one_tooth"
    assert scope.source == "ui_action"


def test_fresh_same_topic_session_carry() -> None:
    session = session_patient_facts_from_ui_action(
        _action(extent="few_teeth"),
        set_at_turn=2,
    )
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=session,
        current_topic="implantation",
        session_turn_count=3,
    )
    assert scope.extent == "few_teeth"
    assert scope.source == "session"


def test_topic_change_blocks_session_carry() -> None:
    session = session_patient_facts_from_ui_action(
        _action(topic="implantation", extent="one_tooth"),
        set_at_turn=1,
    )
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=session,
        current_topic="prosthetics",
        session_turn_count=3,
    )
    assert scope.extent == "unknown"
    assert scope.source == "unknown"


def test_stale_session_facts_not_carried() -> None:
    session = SessionPatientFacts(
        extent="one_tooth",
        topic="implantation",
        provenance="ui_scope_ref",
        ref=build_ui_scope_ref(topic="implantation", extent="one_tooth"),
        set_at_turn=0,
    )
    assert session.is_fresh(session_turn_count=99) is False
    scope = resolve_effective_scope(
        current_ui_action=None,
        session_facts=session,
        current_topic="implantation",
        session_turn_count=99,
    )
    assert scope.source == "unknown"
