"""CP5-DIR: doctors/protocols (A) + CTA on doctors list (B) on the common D2 route.

D2-035 / D2-055: approved doctor↔service links, one doctor card,
active protocols only (not CT/supporting). No ranking, no price.
DIR-B: doctors_for_service may attach one lead CTA (free label gated by fact).
Protocols stay without CTA.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Literal

from contracts.doctor_schema import TargetDoctor, TargetDoctorCatalog
from contracts.d2_tenant_snapshot import D2TenantSnapshot
from contracts.response_plan import (
    ComposerResult,
    ComposerSelectedRouteAuthority,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    ServiceOptionEntry,
    ServiceOptionsBlock,
    SessionKey,
    UiButtonCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
)
from contracts.response_plan_materialization import (
    MaterializationTrace,
    MaterializedResponseOutcome,
)
from contracts.response_plan_post_composer import ResponseSituationDelta
from core.d2_contacts_cta import resolve_d2_lead_cta_button
from core.d2_tenant_snapshot import build_d2_bundle
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui

DirectoryKind = Literal["doctors_for_service", "doctor_profile", "protocols"]

_PROTOCOL_ROLES = frozenset({"protocol", "advanced_protocol"})
_TOPIC_FAMILY = {
    "implantation": "implantology",
    "prosthetics": "prosthodontics",
}
_SECONDARY_PROTOCOL_CAP = 2
_SERVICE_OPTIONS_CAP = 3


def classify_d2_directory_request(*, part: object, envelope_commercial_intent: str) -> DirectoryKind | None:
    """Return directory kind from typed D1R part shape only (no patient_text regex)."""
    if envelope_commercial_intent != "none":
        return None
    if getattr(part, "kind", None) != "content":
        return None
    content_ref = getattr(part, "content_ref", None)
    topic_id = getattr(part, "topic_id", None)
    service_id = getattr(part, "service_id", None)
    if (
        isinstance(content_ref, str)
        and content_ref.startswith("doctors__doctor__")
        and content_ref.endswith(".md")
        and content_ref != "doctors__doctor__overview.md"
    ):
        return "doctor_profile"
    if topic_id == "doctors" and isinstance(service_id, str) and service_id.strip() and content_ref is None:
        return "doctors_for_service"
    if (
        isinstance(topic_id, str)
        and topic_id.strip()
        and topic_id in _TOPIC_FAMILY
        and service_id is None
        and content_ref is None
    ):
        return "protocols"
    return None


def _doctor_catalog(snapshot: D2TenantSnapshot) -> TargetDoctorCatalog:
    raw = dict(snapshot.files).get("doctor_catalog.json")
    if raw is None:
        raise ValueError("d2_doctor_catalog_missing")
    try:
        payload = json.loads(raw.decode("utf-8"))
        return TargetDoctorCatalog.model_validate(payload)
    except Exception as exc:  # noqa: BLE001 — fail closed to typed route error
        raise ValueError("d2_doctor_catalog_invalid") from exc


def _doctors_for_service(catalog: TargetDoctorCatalog, service_id: str) -> tuple[TargetDoctor, ...]:
    matched: list[TargetDoctor] = []
    for doctor_id in sorted(catalog.doctors):
        doctor = catalog.doctors[doctor_id]
        if service_id in doctor.service_ids:
            matched.append(doctor)
    return tuple(matched)


def _doctor_id_from_content_ref(content_ref: str) -> str:
    return content_ref.removesuffix(".md")


def _protocol_services(snapshot: D2TenantSnapshot, *, topic_id: str) -> tuple[tuple[str, str], ...]:
    family = _TOPIC_FAMILY.get(topic_id)
    if family is None:
        return ()
    bundle = build_d2_bundle(snapshot)
    rows: list[tuple[str, str]] = []
    for service_id, service in sorted(bundle.services.items()):
        if not service.active:
            continue
        if service.family != family:
            continue
        if not _PROTOCOL_ROLES.intersection(service.roles):
            continue
        rows.append((service_id, service.name))
    return tuple(rows)


def _answer(
    *,
    session_key: SessionKey,
    snapshot: D2TenantSnapshot,
    text: str,
    response_scope: str,
    selected_service_id: str | None,
    selected_topic_id: str | None,
    service_options_block: ServiceOptionsBlock | None = None,
    quick_replies: tuple[UiQuickReplyCandidate, ...] = (),
    buttons: tuple[UiButtonCandidate, ...] = (),
) -> MaterializedResponseOutcome:
    if snapshot.client_id != session_key.client_id:
        raise ValueError("d2_directory_client_mismatch")
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope=response_scope,  # type: ignore[arg-type]
        selected_service_id=selected_service_id,
        active_session_service_id=None,
        selected_topic_id=selected_topic_id,
        price_plan=PricePlan(kind="none"),
        service_options_block=service_options_block,
        ui_candidates=UiPlanCandidates(quick_replies=quick_replies, buttons=buttons),
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


def build_d2_directory_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    kind: DirectoryKind,
    as_of: date,
    service_id: str | None = None,
    topic_id: str | None = None,
    content_ref: str | None = None,
) -> MaterializedResponseOutcome:
    """Build one directory answer from tenant snapshot data only."""
    if kind == "doctors_for_service":
        if not service_id:
            raise ValueError("d2_directory_service_required")
        catalog = _doctor_catalog(snapshot)
        doctors = _doctors_for_service(catalog, service_id)
        if not doctors:
            text = (
                "В утверждённых данных клиники нет врачей, "
                "явно привязанных к этой услуге."
            )
        else:
            lines = [
                "По этой услуге в клинике работают специалисты по утверждённым карточкам:"
            ]
            for doctor in doctors:
                lines.append(
                    f"— {doctor.name}, {doctor.position} "
                    f"({doctor.experience_years} лет опыта)"
                )
            text = "\n".join(lines)
        cta = resolve_d2_lead_cta_button(
            snapshot,
            as_of=as_of,
            cta_key="doctor",
            prefer_free_consult=True,
        )
        return _answer(
            session_key=session_key,
            snapshot=snapshot,
            text=text,
            response_scope="service",
            selected_service_id=service_id,
            selected_topic_id="doctors",
            buttons=(cta,) if cta is not None else (),
        )

    if kind == "doctor_profile":
        if not content_ref:
            raise ValueError("d2_directory_content_ref_required")
        catalog = _doctor_catalog(snapshot)
        doctor_id = _doctor_id_from_content_ref(content_ref)
        doctor = catalog.doctors.get(doctor_id)
        if doctor is None:
            text = "В утверждённых данных клиники нет карточки этого врача."
        else:
            text = (
                f"{doctor.name}. {doctor.position}. "
                f"Опыт: {doctor.experience_years} лет."
            )
        return _answer(
            session_key=session_key,
            snapshot=snapshot,
            text=text,
            response_scope="clinic",
            selected_service_id=None,
            selected_topic_id=None,
        )

    if kind == "protocols":
        if not topic_id:
            raise ValueError("d2_directory_topic_required")
        protocols = _protocol_services(snapshot, topic_id=topic_id)
        if not protocols:
            text = (
                "В утверждённых данных клиники нет активных протоколов "
                "для этого направления."
            )
            return _answer(
                session_key=session_key,
                snapshot=snapshot,
                text=text,
                response_scope="topic",
                selected_service_id=None,
                selected_topic_id=topic_id,
            )
        lines = ["Утверждённые активные протоколы направления:"]
        for _service_id, name in protocols:
            lines.append(f"— {name}")
        text = "\n".join(lines)
        option_rows = protocols[:_SERVICE_OPTIONS_CAP]
        options_block = ServiceOptionsBlock(
            source_client_id=snapshot.client_id,
            strategy_reference=f"d2_directory_protocols:{topic_id}",
            options=tuple(
                ServiceOptionEntry(service_id=sid, display_name=name)
                for sid, name in option_rows
            ),
        )
        quick = tuple(
            UiQuickReplyCandidate(
                source_client_id=snapshot.client_id,
                reply_id=f"protocol:{sid}",
                label=name,
            )
            for sid, name in protocols[:_SECONDARY_PROTOCOL_CAP]
        )
        return _answer(
            session_key=session_key,
            snapshot=snapshot,
            text=text,
            response_scope="topic",
            selected_service_id=None,
            selected_topic_id=topic_id,
            service_options_block=options_block,
            quick_replies=quick,
        )

    raise ValueError("d2_directory_kind_unsupported")
