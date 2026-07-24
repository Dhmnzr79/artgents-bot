"""Resolve EffectiveScope from typed UI action and session patient_facts (AC1)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from contracts.effective_scope import EffectiveScope
from contracts.ui_scope_action import ScopeExtent, UiScopeAction
from core.routing_loader import THRESHOLDS


@dataclass(frozen=True, slots=True)
class SessionPatientFacts:
    extent: ScopeExtent
    topic: str
    provenance: str
    ref: str
    set_at_turn: int

    def is_fresh(self, *, session_turn_count: int) -> bool:
        age = max(0, int(session_turn_count) - int(self.set_at_turn))
        return age <= int(THRESHOLDS.follow_up.max_service_focus_turn_age)


def resolve_effective_scope(
    *,
    current_ui_action: UiScopeAction | None,
    session_facts: SessionPatientFacts | None,
    current_topic: str | None,
    session_turn_count: int,
) -> EffectiveScope:
    """Priority: explicit current UiScopeAction > fresh same-topic session > unknown."""

    if current_ui_action is not None:
        return EffectiveScope(
            extent=current_ui_action.extent,
            topic=current_ui_action.topic,
            source="ui_action",
            provenance=current_ui_action.ref,
        )

    if session_facts is None:
        return EffectiveScope()

    topic_eff = str(current_topic or "").strip().lower() or None
    if topic_eff and session_facts.topic != topic_eff:
        return EffectiveScope()

    if not session_facts.is_fresh(session_turn_count=session_turn_count):
        return EffectiveScope()

    return EffectiveScope(
        extent=session_facts.extent,
        topic=session_facts.topic,
        source="session",
        provenance=session_facts.ref,
    )


def session_patient_facts_from_ui_action(
    action: UiScopeAction,
    *,
    set_at_turn: int,
) -> SessionPatientFacts:
    return SessionPatientFacts(
        extent=action.extent,
        topic=action.topic,
        provenance=action.provenance,
        ref=action.ref,
        set_at_turn=int(set_at_turn),
    )


def read_session_patient_facts(raw: object) -> SessionPatientFacts | None:
    if not isinstance(raw, dict):
        return None
    extent = str(raw.get("extent") or "").strip()
    topic = str(raw.get("topic") or "").strip().lower()
    ref = str(raw.get("ref") or "").strip()
    provenance = str(raw.get("provenance") or "").strip() or "ui_scope_ref"
    if extent not in ("one_tooth", "few_teeth", "full_arch") or not topic or not ref:
        return None
    try:
        set_at_turn = int(raw.get("set_at_turn"))
    except (TypeError, ValueError):
        return None
    return SessionPatientFacts(
        extent=extent,  # type: ignore[arg-type]
        topic=topic,
        provenance=provenance,
        ref=ref,
        set_at_turn=set_at_turn,
    )


def patient_facts_payload(facts: SessionPatientFacts) -> dict[str, str | int]:
    return {
        "extent": facts.extent,
        "topic": facts.topic,
        "provenance": facts.provenance,
        "ref": facts.ref,
        "set_at_turn": facts.set_at_turn,
    }
