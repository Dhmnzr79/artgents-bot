"""CP5-DIR-B: clinic contacts + CTA label rules on the common D2 route.

D2-012/013/048 narrow slice: tenant contact answers; free-consult CTA label only
when approved fact is active. Not full B12 UI matrix.
"""

from __future__ import annotations

from datetime import date

from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.response_plan import (
    CanonicalContactCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    D2ContactFactBlock,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    SessionKey,
    UiButtonCandidate,
    UiPlanCandidates,
)
from contracts.response_plan_materialization import (
    MaterializationTrace,
    MaterializedResponseOutcome,
)
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.clinic_contact_policies import parse_clinic_contact_facts_from_policies_raw
from core.d2_tenant_snapshot import build_d2_bundle
from core.response_plan_fact_projection import fact_active_as_of
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui

_FREE_CONSULT_FACT_ID = "free_implant_consult"
_FIELD_TO_ATTR = {
    "contact_phone": "phone_display",
    "contact_whatsapp": "whatsapp_display",
    "contact_address": "address_display",
    "contact_hours": "hours_display",
    "contact_parking": "parking_display",
    "contacts": "phone_display",
}
_FIELD_LABEL = {
    "contact_phone": "Телефон",
    "contact_whatsapp": "WhatsApp",
    "contact_address": "Адрес",
    "contact_hours": "Часы работы",
    "contact_parking": "Парковка",
    "contacts": "Телефон",
}


def _policies_raw(snapshot: D2TenantSnapshot) -> dict[str, object]:
    import yaml

    payload = dict(snapshot.files).get("clinic_policies.yaml")
    if payload is None:
        return {}
    value = yaml.safe_load(payload.decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _tone_cta_labels(snapshot: D2TenantSnapshot) -> dict[str, str]:
    import yaml

    payload = dict(snapshot.files).get("tone.yaml")
    if payload is None:
        return {}
    tone = yaml.safe_load(payload.decode("utf-8"))
    if not isinstance(tone, dict):
        return {}
    lead = tone.get("lead")
    if not isinstance(lead, dict):
        return {}
    variants = lead.get("cta_variants")
    if not isinstance(variants, list):
        return {}
    out: dict[str, str] = {}
    for item in variants:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        label = item.get("label")
        if isinstance(key, str) and isinstance(label, str) and key.strip() and label.strip():
            out[key.strip()] = label.strip()
    return out


def _ui_free_book_label(snapshot: D2TenantSnapshot) -> str | None:
    import yaml

    payload = dict(snapshot.files).get("ui.yaml")
    if payload is None:
        return None
    ui = yaml.safe_load(payload.decode("utf-8"))
    if not isinstance(ui, dict):
        return None
    block = ui.get("price_symptom_consult")
    if not isinstance(block, dict):
        return None
    label = block.get("book_label")
    if isinstance(label, str) and "бесплатн" in label.casefold():
        return label.strip()
    return None


def free_consult_fact_active(snapshot: D2TenantSnapshot, *, as_of: date) -> bool:
    """True when free-consult fact is flag-active and within active_from/until."""
    bundle = build_d2_bundle(snapshot)
    fact = bundle.facts.get(_FREE_CONSULT_FACT_ID)
    if fact is None:
        return False
    return fact_active_as_of(fact, as_of)


def resolve_d2_lead_cta_button(
    snapshot: D2TenantSnapshot,
    *,
    as_of: date,
    cta_key: str = "booking",
    prefer_free_consult: bool = False,
) -> UiButtonCandidate | None:
    """D2-013/048: authored CTA label; free wording only with date-active free fact."""
    labels = _tone_cta_labels(snapshot)
    label = labels.get(cta_key) or labels.get("booking")
    button_id = cta_key if cta_key in labels else "booking"
    if prefer_free_consult and free_consult_fact_active(snapshot, as_of=as_of):
        free_label = _ui_free_book_label(snapshot)
        if free_label:
            label = free_label
            button_id = "free_consult"
    if not label:
        return None
    return UiButtonCandidate(
        source_client_id=snapshot.client_id,
        button_id=button_id,
        label=label,
        action_kind="cta",
    )


def build_d2_contact_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    contact_fields: tuple[str, ...],
) -> MaterializedResponseOutcome:
    """Ordinary contact question: tenant contact facts only (not medical terminal).

    Uses ANSWER/standard so the session is not locked into contacts terminal_state.
    Phone is present in text; call button uses action_kind=contact.
    """
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_contact_client_mismatch")
    text, phone = _d2_contact_text(snapshot, contact_fields=contact_fields)
    contact_btn = UiButtonCandidate(
        source_client_id=snapshot.client_id,
        button_id="contact_call",
        label="Позвонить",
        action_kind="contact",
    )
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
        ui_candidates=UiPlanCandidates(buttons=(contact_btn,)),
        transport_kind="blocking",
    )
    composer = ComposerResult(
        route="ANSWER",
        mode="standard",
        patient_text=text,
        code_owned_answer=True,
    )
    resolved = resolve_response_plan(plan, composer)
    # Attach canonical phone for UI projection (resolver standard path omits contact).
    if resolved.ui_plan.contact is None:
        resolved = resolved.model_copy(
            update={
                "ui_plan": resolved.ui_plan.model_copy(
                    update={
                        "contact": CanonicalContactCandidate(
                            source_client_id=snapshot.client_id,
                            phone=phone,
                        )
                    }
                )
            }
        )
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


def build_d2_contact_fact_block(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    request_id: str,
    contact_fields: tuple[str, ...],
) -> tuple[D2ContactFactBlock, UiButtonCandidate, CanonicalContactCandidate]:
    """Make a typed exact-contact part which can compose with a normal D2 answer."""
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_contact_client_mismatch")
    text, phone = _d2_contact_text(snapshot, contact_fields=contact_fields)
    return (
        D2ContactFactBlock(
            request_id=request_id,
            source_client_id=snapshot.client_id,
            display_text=text,
            phone=phone,
        ),
        UiButtonCandidate(
            source_client_id=snapshot.client_id,
            button_id="contact_call",
            label="Позвонить",
            action_kind="contact",
        ),
        CanonicalContactCandidate(source_client_id=snapshot.client_id, phone=phone),
    )


def _d2_contact_text(
    snapshot: D2TenantSnapshot,
    *,
    contact_fields: tuple[str, ...],
) -> tuple[str, str]:
    facts = parse_clinic_contact_facts_from_policies_raw(_policies_raw(snapshot))
    phone = (facts.phone_display or "").strip()
    if not phone:
        raise ValueError("d2_contact_phone_missing")
    wanted = contact_fields or ("contacts",)
    lines: list[str] = []
    for field in wanted:
        attr = _FIELD_TO_ATTR.get(field)
        if attr is None:
            continue
        value = getattr(facts, attr, None)
        if isinstance(value, str) and value.strip():
            title = _FIELD_LABEL.get(field, field)
            lines.append(f"{title}: {value.strip()}")
    if not lines:
        lines.append(f"Телефон: {phone}")
    return "\n".join(dict.fromkeys(lines)), phone
