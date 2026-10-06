"""CP5 off-topic polite refuse on the common D2 route (D2-040 second branch).

Typed empty kind=other (no clinic ids) → authored ui.yaml offtopic answer.
Not spam, not medical terminal, not lead. Session stays open (terminal_state=none).
"""

from __future__ import annotations

import yaml

from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.one_call_envelope import OneCallEnvelope
from contracts.response_plan import (
    ComposerResult,
    ComposerSelectedRouteAuthority,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    SessionKey,
    UiPlanCandidates,
)
from contracts.response_plan_materialization import (
    MaterializationTrace,
    MaterializedResponseOutcome,
)
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui

_DEFAULT_OFFTOPIC = (
    "Я помогаю по вопросам клиники: услуги, цены, подготовка, сроки, запись и контакты. "
    "Если хотите, подскажу по вашему вопросу в этом контексте."
)


def is_d2_offtopic_envelope(envelope: OneCallEnvelope) -> bool:
    """True when the model typed a clinic-empty other request (not garbage spam)."""
    if envelope.route != "ANSWER":
        return False
    if envelope.commercial_intent != "none":
        return False
    if envelope.promotion_scope != "none":
        return False
    understanding = envelope.request_understanding
    if understanding is None or len(understanding.requests) != 1:
        return False
    part = understanding.requests[0]
    if part.kind != "other":
        return False
    if part.service_id is not None or part.topic_id is not None:
        return False
    if part.content_ref is not None or part.content_text is not None:
        return False
    if part.policy_ids or part.contact_fields:
        return False
    if part.content_section_refs or part.content_fallback_section_ref is not None:
        return False
    return True


def _offtopic_answer(snapshot: D2TenantSnapshot) -> str:
    payload = dict(snapshot.files).get("ui.yaml")
    if payload is None:
        return _DEFAULT_OFFTOPIC
    ui = yaml.safe_load(payload.decode("utf-8"))
    if not isinstance(ui, dict):
        return _DEFAULT_OFFTOPIC
    fallback = ui.get("fallback_menu")
    if not isinstance(fallback, dict):
        return _DEFAULT_OFFTOPIC
    block = fallback.get("offtopic")
    if not isinstance(block, dict):
        return _DEFAULT_OFFTOPIC
    answer = block.get("answer")
    if isinstance(answer, str) and answer.strip():
        return " ".join(answer.split())
    return _DEFAULT_OFFTOPIC


def build_d2_offtopic_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
) -> MaterializedResponseOutcome:
    """Authored polite refuse: clinic-scope only; no CTA/price/medical."""
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_offtopic_client_mismatch")
    text = _offtopic_answer(snapshot)
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope="clinic",
        selected_service_id=None,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(),
        transport_kind="blocking",
    )
    composer = ComposerResult(
        route="ANSWER",
        mode="standard",
        patient_text=text,
        code_owned_answer=True,
    )
    resolved = resolve_response_plan(plan, composer)
    return MaterializedResponseOutcome(
        resolved=resolved,
        rendered_text=render_response_text(resolved),
        ui_projection=project_response_ui(resolved),
        materialization_diagnostics=(),
        selection_diagnostics=(),
        adapter_diagnostics=(),
        situation_delta=ResponseSituationDelta(action="keep"),
        trace=MaterializationTrace(None, (), (), ()),
    )
