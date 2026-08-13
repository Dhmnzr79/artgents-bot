"""Minimal session bridge for target FullContext runtime (S61)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from contracts.effective_scope import EffectiveScope
from contracts.turn_frame import TurnFrame
from contracts.ui_scope_action import UiScopeAction
from contracts.ui_stage_action import UiStageAction
from core.routing_loader import THRESHOLDS
from core.target_presentation_decision import TargetPresentationCadenceUpdate
from core.target_response_verifier import TargetVerifiedComposedResponse
from core.target_effective_scope import (
    SessionPatientFacts,
    patient_facts_payload,
    read_session_patient_facts,
    session_patient_facts_from_ui_action,
    session_patient_facts_from_ui_stage_action,
)
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_session_selection import TargetMaterializedSessionSelection
from session import mem_get

_TARGET_SESSION_KEY = "target_runtime_state"
_TARGET_FOLLOWUPS_KEY = "target_runtime_followups"
_PATIENT_FACTS_KEY = "patient_facts"
_SERVICE_FOCUS_KEYS = frozenset(
    {"last_service_id", "last_topic", "last_primary_aspect", "service_focus_set_at_turn"}
)


@dataclass(frozen=True, slots=True)
class ServiceFocusSnapshot:
    service_id: str
    topic: str
    label: str
    last_route: str
    service_focus_age: int


def max_service_focus_turn_age() -> int:
    return int(THRESHOLDS.follow_up.max_service_focus_turn_age)


def compute_service_focus_age(
    *,
    session_turn_count: int,
    service_focus_set_at_turn: int | None,
) -> int | None:
    if service_focus_set_at_turn is None:
        return None
    return max(0, int(session_turn_count) - int(service_focus_set_at_turn))


def read_age_guarded_service_focus(st: dict[str, Any]) -> ServiceFocusSnapshot | None:
    """Canonical product helper: target_runtime_state focus with unified age guard."""
    raw = st.get(_TARGET_SESSION_KEY)
    if not isinstance(raw, dict):
        return None
    service_id = str(raw.get("last_service_id") or "").strip()
    if not service_id:
        return None
    set_at = raw.get("service_focus_set_at_turn")
    if set_at is None:
        return None
    try:
        set_at_turn = int(set_at)
    except (TypeError, ValueError):
        return None
    turn_count = int(st.get("session_turn_count") or 0)
    age = compute_service_focus_age(
        session_turn_count=turn_count,
        service_focus_set_at_turn=set_at_turn,
    )
    if age is None or age > max_service_focus_turn_age():
        return None
    topic = str(raw.get("last_topic") or "unknown").strip().lower() or "unknown"
    return ServiceFocusSnapshot(
        service_id=service_id,
        topic=topic,
        label=service_id,
        last_route="",
        service_focus_age=age,
    )


def focus_dict_from_session_state(st: dict[str, Any]) -> dict[str, str] | None:
    """Age-guarded focus dict for legacy call sites (C2c-correction)."""
    snap = read_age_guarded_service_focus(st)
    if snap is None:
        return None
    return {
        "service_id": snap.service_id,
        "topic": snap.topic,
        "label": snap.label,
        "last_route": snap.last_route,
    }


def clear_target_service_focus(session_id: str) -> None:
    """Clear service focus fields only; preserve shown_* continuity."""
    from session import _lock, _persist_unlocked

    with _lock:
        st = mem_get(session_id)
        raw = st.get(_TARGET_SESSION_KEY)
        if not isinstance(raw, dict):
            return
        updated = {k: v for k, v in raw.items() if k not in _SERVICE_FOCUS_KEYS}
        if updated:
            st[_TARGET_SESSION_KEY] = updated
        else:
            st.pop(_TARGET_SESSION_KEY, None)
        _persist_unlocked(session_id, st)


@dataclass(frozen=True, slots=True)
class TargetRuntimeSessionState:
    last_service_id: str | None
    last_topic: str | None
    last_primary_aspect: str | None
    service_focus_set_at_turn: int | None
    session_turn_count: int
    shown_fact_ids: tuple[str, ...]
    shown_amplifier_refs: tuple[str, ...]
    shown_consultation_value_refs: tuple[str, ...]
    shown_video_ids: tuple[str, ...]
    shown_content_followup_refs: tuple[str, ...]
    shown_price_followup_refs: tuple[str, ...]
    situation_offered: bool
    last_rendered_promo_fact_id: str | None
    followups: tuple[TargetRuntimeFollowupItem, ...]
    patient_facts: SessionPatientFacts | None = None

    def service_focus_age(self) -> int | None:
        return compute_service_focus_age(
            session_turn_count=self.session_turn_count,
            service_focus_set_at_turn=self.service_focus_set_at_turn,
        )

    def is_service_focus_fresh(self) -> bool:
        age = self.service_focus_age()
        if age is None or not self.last_service_id:
            return False
        return age <= max_service_focus_turn_age()


def _merge_unique(*groups: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for item in group:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return tuple(merged)


def read_target_runtime_session(sid: str) -> TargetRuntimeSessionState:
    st = mem_get(sid)
    session_turn_count = int(st.get("session_turn_count") or 0)
    raw = st.get(_TARGET_SESSION_KEY)
    followups_raw = st.get(_TARGET_FOLLOWUPS_KEY)
    followups: tuple[TargetRuntimeFollowupItem, ...] = ()
    if isinstance(followups_raw, list):
        items: list[TargetRuntimeFollowupItem] = []
        for entry in followups_raw:
            if not isinstance(entry, dict):
                continue
            ref = str(entry.get("ref") or "").strip()
            label = str(entry.get("label") or "").strip()
            client_id = str(entry.get("client_id") or "").strip() or None
            if ref:
                items.append(TargetRuntimeFollowupItem(ref=ref, label=label, client_id=client_id))
        followups = tuple(items)
    patient_facts = read_session_patient_facts(st.get(_PATIENT_FACTS_KEY))
    if not isinstance(raw, dict):
        return TargetRuntimeSessionState(
            last_service_id=None,
            last_topic=None,
            last_primary_aspect=None,
            service_focus_set_at_turn=None,
            session_turn_count=session_turn_count,
            shown_fact_ids=(),
            shown_amplifier_refs=(),
            shown_consultation_value_refs=(),
            shown_video_ids=(),
            shown_content_followup_refs=(),
            shown_price_followup_refs=(),
            situation_offered=False,
            last_rendered_promo_fact_id=None,
            followups=followups,
            patient_facts=patient_facts,
        )
    set_at_raw = raw.get("service_focus_set_at_turn")
    set_at: int | None
    try:
        set_at = int(set_at_raw) if set_at_raw is not None else None
    except (TypeError, ValueError):
        set_at = None
    return TargetRuntimeSessionState(
        last_service_id=str(raw.get("last_service_id") or "").strip() or None,
        last_topic=str(raw.get("last_topic") or "").strip() or None,
        last_primary_aspect=str(raw.get("last_primary_aspect") or "").strip() or None,
        service_focus_set_at_turn=set_at,
        session_turn_count=session_turn_count,
        shown_fact_ids=tuple(str(x).strip() for x in raw.get("shown_fact_ids") or [] if str(x).strip()),
        shown_amplifier_refs=tuple(
            str(x).strip() for x in raw.get("shown_amplifier_refs") or [] if str(x).strip()
        ),
        shown_consultation_value_refs=tuple(
            str(x).strip()
            for x in raw.get("shown_consultation_value_refs") or []
            if str(x).strip()
        ),
        shown_video_ids=tuple(
            str(x).strip() for x in raw.get("shown_video_ids") or [] if str(x).strip()
        ),
        shown_content_followup_refs=tuple(
            str(x).strip()
            for x in raw.get("shown_content_followup_refs") or []
            if str(x).strip()
        ),
        shown_price_followup_refs=tuple(
            str(x).strip()
            for x in raw.get("shown_price_followup_refs") or []
            if str(x).strip()
        ),
        situation_offered=bool(raw.get("situation_offered")),
        last_rendered_promo_fact_id=str(raw.get("last_rendered_promo_fact_id") or "").strip() or None,
        followups=followups,
        patient_facts=patient_facts,
    )


def write_session_patient_facts_from_ui_action(
    sid: str,
    action: UiScopeAction,
) -> SessionPatientFacts:
    """Persist canonical extent from explicit UI click; replaces prior extent."""

    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        turn_count = int(st.get("session_turn_count") or 0)
        facts = session_patient_facts_from_ui_action(action, set_at_turn=turn_count)
        st[_PATIENT_FACTS_KEY] = patient_facts_payload(facts)
        _persist_unlocked(sid, st)
        return facts


def write_session_patient_facts_from_ui_stage_action(
    sid: str,
    action: UiStageAction,
    *,
    prior: SessionPatientFacts | None = None,
) -> SessionPatientFacts:
    """Persist canonical stage from explicit UI click; preserve extent when known."""

    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        turn_count = int(st.get("session_turn_count") or 0)
        if prior is None:
            prior = read_session_patient_facts(st.get(_PATIENT_FACTS_KEY))
        facts = session_patient_facts_from_ui_stage_action(
            action,
            set_at_turn=turn_count,
            prior=prior,
        )
        st[_PATIENT_FACTS_KEY] = patient_facts_payload(facts)
        _persist_unlocked(sid, st)
        return facts


def clear_session_patient_facts(sid: str) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        if _PATIENT_FACTS_KEY in st:
            st.pop(_PATIENT_FACTS_KEY, None)
            _persist_unlocked(sid, st)


def sync_session_patient_facts_topic(
    sid: str,
    *,
    current_topic: str | None,
) -> None:
    """Drop carried extent when runtime topic no longer matches session facts."""

    from session import _lock, _persist_unlocked, mem_get

    topic_eff = str(current_topic or "").strip().lower()
    with _lock:
        st = mem_get(sid)
        facts = read_session_patient_facts(st.get(_PATIENT_FACTS_KEY))
        if facts is None:
            return
        if topic_eff and facts.topic != topic_eff:
            st.pop(_PATIENT_FACTS_KEY, None)
            _persist_unlocked(sid, st)


def _apply_a9_patient_facts_to_state(
    st: dict[str, Any],
    *,
    effective_scope: EffectiveScope,
    prior: SessionPatientFacts | None,
    current_topic: str | None,
) -> None:
    from core.target_effective_scope_merge import simulate_session_patient_facts_after_turn

    turn_count = int(st.get("session_turn_count") or 0)
    if prior is None:
        prior = read_session_patient_facts(st.get(_PATIENT_FACTS_KEY))
    sim = simulate_session_patient_facts_after_turn(
        merged=effective_scope,
        prior=prior,
        current_topic=current_topic,
        session_turn_count=turn_count,
    )
    if not sim.wrote or sim.facts is None:
        return
    facts = SessionPatientFacts(
        extent=sim.facts.extent,
        topic=sim.facts.topic,
        provenance=sim.facts.provenance,
        ref=sim.facts.ref,
        set_at_turn=sim.facts.set_at_turn,
        stage=sim.facts.stage,
        stage_ref=sim.facts.stage_ref,
        jaw=sim.facts.jaw,
        reported_context=None,
    )
    st[_PATIENT_FACTS_KEY] = patient_facts_payload(facts)


def write_session_patient_facts_from_a9_materialized(
    sid: str,
    *,
    effective_scope: EffectiveScope,
    prior: SessionPatientFacts | None,
    current_topic: str | None,
) -> None:
    """Persist extent/jaw/stage from A9 merge after materialized turn; never reported_context."""

    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        _apply_a9_patient_facts_to_state(
            st,
            effective_scope=effective_scope,
            prior=prior,
            current_topic=current_topic,
        )
        _persist_unlocked(sid, st)


def write_target_runtime_session_after_materialized(
    sid: str,
    *,
    turn_frame: TurnFrame,
    verified: TargetVerifiedComposedResponse,
    prior: TargetRuntimeSessionState,
    current_selection: TargetMaterializedSessionSelection,
    followups: tuple[TargetRuntimeFollowupItem, ...],
    effective_scope: EffectiveScope | None = None,
    presentation_cadence_update: TargetPresentationCadenceUpdate | None = None,
    availability_status: str | None = None,
) -> None:
    """Persist target continuity only after a successful materialized response."""

    from session import _lock, _persist_unlocked, mem_get

    _ = verified
    shown_fact_ids = _merge_unique(prior.shown_fact_ids, current_selection.shown_fact_ids)
    shown_amplifier_refs = _merge_unique(
        prior.shown_amplifier_refs,
        current_selection.shown_amplifier_refs,
    )
    shown_consultation_value_refs = _merge_unique(
        prior.shown_consultation_value_refs,
        current_selection.shown_consultation_value_refs,
    )
    shown_video_ids = _merge_unique(
        prior.shown_video_ids,
        presentation_cadence_update.shown_video_ids if presentation_cadence_update else (),
    )
    shown_content_followup_refs = _merge_unique(
        prior.shown_content_followup_refs,
        presentation_cadence_update.shown_content_followup_refs
        if presentation_cadence_update
        else (),
    )
    shown_price_followup_refs = _merge_unique(
        prior.shown_price_followup_refs,
        presentation_cadence_update.shown_price_followup_refs
        if presentation_cadence_update
        else (),
    )
    situation_offered = prior.situation_offered or bool(
        presentation_cadence_update and presentation_cadence_update.situation_offered
    )
    last_rendered_promo: str | None = prior.last_rendered_promo_fact_id
    if current_selection.last_rendered_promo_fact_id:
        last_rendered_promo = current_selection.last_rendered_promo_fact_id
    with _lock:
        st = mem_get(sid)
        turn_count = int(st.get("session_turn_count") or 0)
        payload: dict[str, Any] = {
            "shown_fact_ids": list(shown_fact_ids),
            "shown_amplifier_refs": list(shown_amplifier_refs),
            "shown_consultation_value_refs": list(shown_consultation_value_refs),
            "shown_video_ids": list(shown_video_ids),
            "shown_content_followup_refs": list(shown_content_followup_refs),
            "shown_price_followup_refs": list(shown_price_followup_refs),
            "situation_offered": situation_offered,
        }
        if last_rendered_promo is not None:
            payload["last_rendered_promo_fact_id"] = last_rendered_promo
        service_id = str(turn_frame.service_id or "").strip() or None
        if availability_status in {"known_not_offered", "unresolved"}:
            service_id = None
        if service_id:
            payload.update(
                {
                    "last_service_id": service_id,
                    "last_topic": turn_frame.topic,
                    "last_primary_aspect": turn_frame.primary_aspect,
                    "service_focus_set_at_turn": turn_count,
                }
            )
        elif prior.last_service_id:
            payload.update(
                {
                    "last_service_id": prior.last_service_id,
                    "last_topic": prior.last_topic,
                    "last_primary_aspect": prior.last_primary_aspect,
                    "service_focus_set_at_turn": prior.service_focus_set_at_turn,
                }
            )
        st[_TARGET_SESSION_KEY] = payload
        st[_TARGET_FOLLOWUPS_KEY] = [
            {
                "ref": item.ref,
                "label": item.label,
                **({"client_id": item.client_id} if item.client_id else {}),
            }
            for item in followups
            if item.ref
        ]
        if effective_scope is not None:
            _apply_a9_patient_facts_to_state(
                st,
                effective_scope=effective_scope,
                prior=prior.patient_facts,
                current_topic=turn_frame.topic,
            )
        _persist_unlocked(sid, st)
