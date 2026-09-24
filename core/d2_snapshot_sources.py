"""Bind one immutable tenant snapshot to the existing isolated D2 sources."""

from __future__ import annotations

from pathlib import Path

import yaml

from contracts.d2_tenant_snapshot import D2ModelView, D2TenantSnapshot
from contracts.one_call_envelope import OneCallEnvelope
from contracts.response_plan import (
    CodeOwnedTerminalCandidate,
    ComposerResult,
    ComposerSelectedRouteAuthority,
    PreComposerPlan,
    PricePlan,
    RouteModePair,
    SessionKey,
    UiButtonCandidate,
    UiPlanCandidates,
    UiQuickReplyCandidate,
    UiVideoCandidate,
    AuthoredServiceAlternativeBlock,
    ServiceOptionEntry,
)
from contracts.response_plan_adapter import ResponsePlanAdapterUiAuthority, ResponsePlanAdapterUiButtonAuthority
from contracts.response_plan_materialization import (
    D2CommercialAuthority,
    D2CommercialPackageAuthority,
    D2CommercialPromoAuthority,
    D2CompatibilityGroupAuthority,
    D2DirectionAuthority,
    D2DirectionPricePresentation,
    D2PartFailureAuthority,
    D2ServiceCommercialProfileAuthority,
    D2SourceUiAuthority,
    D2VolumeChoice,
    MaterializationTrace,
    MaterializedResponseOutcome,
    ResponsePlanMaterializationSources,
)
from contracts.response_plan_post_composer import PostComposerMaterialAuthority, ResponseSituationDelta
from core.d2_tenant_snapshot import build_d2_bundle, build_d2_model_view
from core.clinic_contact_policies import (
    format_manual_contact_phone_suffix,
    parse_clinic_contact_facts_from_policies_raw,
)
from core.response_plan_resolver import resolve_response_plan
from core.response_text_renderer import render_response_text
from core.response_ui_projection import project_response_ui


class D2SnapshotBindingError(ValueError):
    pass


_PRICE_UNAVAILABLE = "К сожалению, у меня пока нет информации о стоимости этой услуги"
_DEFAULT_FOCUS_CLARIFY = "Могу подсказать по услугам, ценам, врачам или записи. Что вас интересует?"
_TYPED_CLARIFY_QUESTIONS = {
    "service": "Какую услугу вы имеете в виду?",
    "term": "Уточните, пожалуйста, что именно вы имеете в виду?",
    "extent": "Уточните, пожалуйста, речь об одном зубе, нескольких зубах или всей челюсти?",
    "jaw": "Уточните, пожалуйста, речь о верхней или нижней челюсти?",
    "stage": "Уточните, пожалуйста, на каком этапе лечения вы сейчас?",
}
_VOLUME_EXTENTS = ("one_tooth", "few_teeth", "full_arch", "unknown")
_DEFAULT_VOLUME_LABELS = {
    "one_tooth": "Один зуб",
    "few_teeth": "Несколько зубов",
    "full_arch": "Вся челюсть",
    "unknown": "Не знаю",
}


def _yaml_file(snapshot: D2TenantSnapshot, name: str) -> dict[str, object]:
    raw = dict(snapshot.files).get(name)
    if raw is None:
        return {}
    value = yaml.safe_load(raw.decode("utf-8"))
    return value if isinstance(value, dict) else {}


def _frontmatter(snapshot: D2TenantSnapshot, ref: str) -> dict[str, object]:
    raw = dict(snapshot.files).get(f"md/{ref}")
    if raw is None or not raw.startswith(b"---"):
        return {}
    end = raw.find(b"\n---", 3)
    if end < 0:
        return {}
    value = yaml.safe_load(raw[4:end].decode("utf-8"))
    return value if isinstance(value, dict) else {}


def build_d2_snapshot_sources(
    snapshot: D2TenantSnapshot,
    *,
    model_view: D2ModelView,
    envelope: OneCallEnvelope,
    session_key: SessionKey,
    transport_kind: str = "blocking",
    shown_secondary_ref_ids: tuple[str, ...] = (),
    shown_promo_fact_ids: tuple[str, ...] = (),
) -> ResponsePlanMaterializationSources:
    """Construct sources only after validating identity and every model-selected ref."""
    if snapshot.client_id != model_view.client_id or snapshot.fingerprint != model_view.fingerprint:
        raise D2SnapshotBindingError("snapshot_view_mismatch")
    # A caller must not be able to retain the public fingerprint while replacing
    # one of the catalog projections that D1R saw.  Rebuild from the captured
    # bytes and compare the whole immutable view, rather than trusting a digest
    # supplied by the caller.
    if model_view != build_d2_model_view(snapshot):
        raise D2SnapshotBindingError("snapshot_view_forged")
    if session_key.client_id != snapshot.client_id:
        raise D2SnapshotBindingError("snapshot_session_mismatch")
    understanding = envelope.request_understanding
    if understanding is None:
        raise D2SnapshotBindingError("request_understanding_required")
    # Wrong/missing content refs are recoverable part failures (D2-078), not
    # snapshot-binding hard errors. Foreign tenant identity stays fatal above.
    # Soft-fail happens in the materializer as d2_content_source_missing.

    # Broad prices require explicit authored direction membership and order.
    configured_topics = {item.topic_id for item in model_view.direction_prices}
    if any(
        request.kind == "price" and request.service_id is None and request.topic_id is not None
        and request.topic_id not in configured_topics
        for request in understanding.requests
    ):
        raise D2SnapshotBindingError("direction_overview_not_configured")

    tone = _yaml_file(snapshot, "tone.yaml")
    ui_yaml = _yaml_file(snapshot, "ui.yaml")
    scope_nav = ui_yaml.get("scope_nav") if isinstance(ui_yaml.get("scope_nav"), dict) else {}
    cta_variants = ((tone.get("lead") or {}) if isinstance(tone.get("lead"), dict) else {}).get("cta_variants", [])
    labels = {str(item.get("key")): str(item.get("label")) for item in cta_variants if isinstance(item, dict)}
    price_label = labels.get("price")
    ui_authority = None
    if price_label:
        ui_authority = ResponsePlanAdapterUiAuthority(
            source_client_id=snapshot.client_id,
            buttons=(ResponsePlanAdapterUiButtonAuthority(source_client_id=snapshot.client_id, button_id="price", label=price_label, action_kind="cta"),),
        )
    videos = (_yaml_file(snapshot, "video_catalog.yaml").get("videos") or {})
    ui_rows: list[D2SourceUiAuthority] = []
    direction_map: dict[str, list[str]] = {}
    for content in snapshot.content:
        meta = _frontmatter(snapshot, content.content_ref)
        topic = meta.get("topic")
        if isinstance(topic, str):
            direction_map.setdefault(topic, []).extend(content.allowed_service_ids)
        quick: list[UiQuickReplyCandidate] = []
        for wanted in meta.get("suggest_h3", []) if isinstance(meta.get("suggest_h3"), list) else []:
            ref = f"a:{wanted}"
            section = next((item for item in content.sections if item.section_ref == ref), None)
            if section is not None:
                heading = section.display_text.splitlines()[0].lstrip("#").strip()
                quick.append(UiQuickReplyCandidate(source_client_id=snapshot.client_id, reply_id=f"{content.content_ref}#{wanted}", label=heading))
        video = None
        key = meta.get("video_key")
        if isinstance(key, str) and isinstance(videos, dict) and key in videos:
            video = UiVideoCandidate(source_client_id=snapshot.client_id, video_id=key)
        cta = None
        cta_key = meta.get("cta_key")
        if meta.get("cta_action") == "lead" and isinstance(cta_key, str) and cta_key in labels:
            cta = UiButtonCandidate(source_client_id=snapshot.client_id, button_id=cta_key, label=labels[cta_key], action_kind="cta")
        ui_rows.append(D2SourceUiAuthority(source_client_id=snapshot.client_id, content_ref=content.content_ref, quick_replies=tuple(quick), video=video, cta=cta))
    directions = tuple(D2DirectionAuthority(source_client_id=snapshot.client_id, topic_id=topic, service_ids=tuple(dict.fromkeys(ids))) for topic, ids in direction_map.items() if ids)
    directions = tuple(item for item in directions if item.topic_id not in configured_topics) + tuple(
        D2DirectionAuthority(source_client_id=snapshot.client_id, topic_id=item.topic_id,
                             service_ids=item.service_ids, ordered_offer_ids=item.offer_ids)
        for item in model_view.direction_prices
    )
    return ResponsePlanMaterializationSources(
        session_key=session_key,
        context_strategy="full_context",
        transport_kind=transport_kind,  # type: ignore[arg-type]
        material_authority=PostComposerMaterialAuthority(source_client_id=snapshot.client_id, bundle=build_d2_bundle(snapshot)),
        d2_published_terms_by_offer={term.offer_id: term for term in model_view.published_terms},
        ui_authority=ui_authority,
        d2_authored_content=snapshot.content,
        d2_directions=directions,
        d2_direction_price_presentations=tuple(
            D2DirectionPricePresentation(
                source_client_id=snapshot.client_id,
                topic_id=item.topic_id,
                introduction_text=item.introduction_text,
                unknown_extent_text=item.unknown_extent_text,
                volume_choices=_volume_choices_for_topic(
                    snapshot.client_id,
                    topic_id=item.topic_id,
                    scope_nav=scope_nav,
                ),
            )
            for item in model_view.direction_prices
        ),
        d2_source_ui=tuple(ui_rows),
        d2_part_failures=(
            D2PartFailureAuthority(source_client_id=snapshot.client_id, message_id="d2-price-unavailable", reason="d2_no_price_candidates", display_text=_PRICE_UNAVAILABLE),
            D2PartFailureAuthority(source_client_id=snapshot.client_id, message_id="d2-price-scope-unavailable", reason="d2_no_scope_price_candidates", display_text=_PRICE_UNAVAILABLE),
        ),
        shown_d2_secondary_ref_ids=shown_secondary_ref_ids,
        shown_promo_fact_ids=shown_promo_fact_ids,
        d2_snapshot_fingerprint=snapshot.fingerprint,
        d2_commercial=_commercial_authority(snapshot.client_id, model_view),
    )


def _volume_choices_for_topic(
    client_id: str,
    *,
    topic_id: str,
    scope_nav: dict[str, object],
) -> tuple[D2VolumeChoice, ...]:
    topic_nav = scope_nav.get(topic_id)
    labels_by_extent: dict[str, str] = dict(_DEFAULT_VOLUME_LABELS)
    if isinstance(topic_nav, dict):
        for extent in _VOLUME_EXTENTS:
            entry = topic_nav.get(extent)
            if isinstance(entry, dict):
                label = entry.get("label")
                if isinstance(label, str) and label.strip():
                    labels_by_extent[extent] = label.strip()
    return tuple(
        D2VolumeChoice(
            extent=extent,  # type: ignore[arg-type]
            candidate=UiQuickReplyCandidate(
                source_client_id=client_id,
                reply_id=f"volume:{topic_id}:{extent}",
                label=labels_by_extent[extent],
            ),
        )
        for extent in _VOLUME_EXTENTS
    )


def _commercial_authority(client_id: str, model_view: D2ModelView) -> D2CommercialAuthority:
    pack = model_view.commercial
    return D2CommercialAuthority(
        source_client_id=client_id,
        promo_facts=tuple(
            D2CommercialPromoAuthority(
                source_client_id=client_id, fact_id=item.fact_id, short_text=item.short_text, full_text=item.full_text,
            )
            for item in pack.promo_facts
        ),
        price_booster_packages=tuple(
            D2CommercialPackageAuthority(
                source_client_id=client_id, package_id=item.package_id, name=item.name, body_text=item.body_text,
            )
            for item in pack.price_booster_packages
        ),
        also_list_packages=tuple(
            D2CommercialPackageAuthority(
                source_client_id=client_id, package_id=item.package_id, name=item.name, body_text=item.body_text,
            )
            for item in pack.also_list_packages
        ),
        service_profiles=tuple(
            D2ServiceCommercialProfileAuthority(
                source_client_id=client_id, service_id=item.service_id, promo_refs=item.promo_refs,
                price_booster_id=item.price_booster_id, also_list_id=item.also_list_id,
            )
            for item in pack.service_profiles
        ),
        incompatibility_groups=tuple(
            D2CompatibilityGroupAuthority(
                source_client_id=client_id, group_id=item.group_id, offer_or_fact_ids=item.offer_or_fact_ids,
                explanation_text=item.explanation_text,
            )
            for item in pack.incompatibility_groups
        ),
    )


def build_d2_focus_clarify_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    clarify_axis: str | None = None,
    service_options: tuple[str, ...] | None = None,
) -> MaterializedResponseOutcome:
    """A10/D2-077: short focus clarify from clinic ui.yaml, no invented price."""
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("clarify_client_mismatch")
    ui_yaml = _yaml_file(snapshot, "ui.yaml")
    clarify = ui_yaml.get("continuation_clarify") if isinstance(ui_yaml.get("continuation_clarify"), dict) else {}
    answer = clarify.get("answer") if isinstance(clarify, dict) else None
    if clarify_axis is not None and clarify_axis not in _TYPED_CLARIFY_QUESTIONS:
        raise D2SnapshotBindingError("clarify_axis_unsupported")
    text = _TYPED_CLARIFY_QUESTIONS[clarify_axis] if clarify_axis is not None else (
        answer.strip() if isinstance(answer, str) and answer.strip() else _DEFAULT_FOCUS_CLARIFY
    )
    guided = ui_yaml.get("guided_menu") if isinstance(ui_yaml.get("guided_menu"), dict) else {}
    quick: list[UiQuickReplyCandidate] = []
    raw_replies = guided.get("quick_replies") if isinstance(guided, dict) else None
    if service_options is not None:
        services = snapshot.bundle.services
        for service_id in service_options:
            service = services.get(service_id)
            if service is None or not service.active:
                raise D2SnapshotBindingError("clarify_service_option_missing")
            quick.append(UiQuickReplyCandidate(
                source_client_id=snapshot.client_id,
                reply_id=f"service:{service_id}",
                label=service.name,
            ))
    elif clarify_axis is None and isinstance(raw_replies, list):
        for item in raw_replies:
            if not isinstance(item, dict):
                continue
            label = item.get("label")
            ref = item.get("ref")
            if isinstance(label, str) and label.strip() and isinstance(ref, str) and ref.strip():
                quick.append(
                    UiQuickReplyCandidate(
                        source_client_id=snapshot.client_id,
                        reply_id=ref.strip(),
                        label=label.strip(),
                    )
                )
            if len(quick) >= 4:
                break
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="CLARIFY", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope="clinic",
        selected_service_id=None,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(quick_replies=tuple(quick)),
        transport_kind="blocking",
    )
    composer = ComposerResult(route="CLARIFY", mode="standard", patient_text=text)
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


def build_d2_other_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
) -> MaterializedResponseOutcome:
    """Clinic-authored general help for non-factual ``other`` model prose."""
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("other_client_mismatch")
    guided = _yaml_file(snapshot, "ui.yaml").get("guided_menu")
    answer = guided.get("answer") if isinstance(guided, dict) else None
    text = answer.strip() if isinstance(answer, str) and answer.strip() else _DEFAULT_FOCUS_CLARIFY
    return _d2_code_owned_answer(session_key=session_key, text=text, route="ANSWER")


def resolve_d2_clarify_service_topic(
    snapshot: D2TenantSnapshot,
    service_options: tuple[str, ...],
) -> str | None:
    """Use exact tenant service-document metadata, never model prose or labels."""
    topics: set[str] = set()
    for service_id in service_options:
        service = snapshot.bundle.services.get(service_id)
        if service is None or not service.active or not service.content_ref:
            return None
        topic = _frontmatter(snapshot, service.content_ref).get("topic")
        if not isinstance(topic, str) or not topic.strip():
            return None
        topics.add(topic)
    return next(iter(topics)) if len(topics) == 1 else None


_INFO_GAP = "К сожалению, у меня пока недостаточно информации по этому вопросу"
_UNKNOWN_REFERENCE_GAP = "У меня нет информации по этому названию в утверждённых материалах клиники."
_UNKNOWN_TERM_CLARIFY = "Уточните, пожалуйста, что вы имеете в виду под этим названием?"
_UNKNOWN_TERM_GAP = _INFO_GAP + ". Могу помочь записаться на консультацию."
_POLICY_CLARIFY = "Уточните, пожалуйста: вопрос про ОМС или ДМС?"
_DEFAULT_MANUAL_CONTACT = (
    "Такой вопрос лучше решить напрямую с клиникой — так будет быстрее и корректнее. "
    "Пожалуйста, позвоните нам."
)


def _clinic_policies_raw(snapshot: D2TenantSnapshot) -> dict[str, object]:
    return _yaml_file(snapshot, "clinic_policies.yaml")


def _manual_contact_text(snapshot: D2TenantSnapshot) -> tuple[str, str | None]:
    """Build the single authored ADMIN stub + optional display phone."""
    raw = _clinic_policies_raw(snapshot)
    template = str(raw.get("manual_contact_template") or "").strip()
    urgent = str(raw.get("manual_contact_urgent_suffix") or "").strip()
    facts = parse_clinic_contact_facts_from_policies_raw(raw)
    phone_suffix = format_manual_contact_phone_suffix(facts)
    if template and "{phone_suffix}" in template:
        text = template.format(phone_suffix=phone_suffix, urgent_suffix=urgent)
    elif template:
        text = template
    else:
        text = _DEFAULT_MANUAL_CONTACT
        if phone_suffix:
            text = f"{text}{phone_suffix}."
        if urgent:
            text = f"{text} {urgent}"
    phone = facts.phone_display.strip() or None
    if phone is None and facts.branches:
        lines = []
        for branch in facts.branches:
            lines.extend(branch.phone_displays)
        phone = lines[0] if lines else None
    return " ".join(text.split()), phone


def build_d2_manual_contact_terminal_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
) -> MaterializedResponseOutcome:
    """B03/D2-023: one authored manual-contact stub for all ADMIN problem cases.

    Current pain, bleeding, complaint, director request — same text. No medical
    advice, prices, promos, follow-up, or video. Future fear stays ordinary ANSWER.
    """
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("manual_contact_client_mismatch")
    text, _phone = _manual_contact_text(snapshot)
    # Phone stays in authored display_text only. Do not attach canonical_contact:
    # resolver would emit a contact_call button, forbidden by D2-023.
    terminal = CodeOwnedTerminalCandidate(
        source_client_id=snapshot.client_id,
        route="ADMIN",
        mode="medical_terminal",
        authority="deterministic_policy_terminal",
        display_text=text,
        canonical_contact=None,
    )
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ADMIN", mode="medical_terminal"),),
            terminal_candidates=(terminal,),
        ),
        response_scope="clinic",
        selected_service_id=None,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        ui_candidates=UiPlanCandidates(),
        transport_kind="blocking",
    )
    composer = ComposerResult(route="ADMIN", mode="medical_terminal", patient_text=None)
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


def _authored_policy_answers(snapshot: D2TenantSnapshot) -> dict[str, str]:
    raw = _clinic_policies_raw(snapshot).get("policies")
    if not isinstance(raw, dict):
        return {}
    out: dict[str, str] = {}
    for key, body in raw.items():
        if not isinstance(key, str) or not isinstance(body, dict):
            continue
        answer = body.get("answer")
        if isinstance(answer, str) and answer.strip():
            out[key] = answer.strip()
    return out


def _authored_service_alternative(
    snapshot: D2TenantSnapshot,
    service_id: str,
) -> tuple[str, tuple[str, ...]] | None:
    """Return (approved_text, alternative_service_ids) from typed rows only."""
    raw = _clinic_policies_raw(snapshot).get("service_alternatives")
    if not isinstance(raw, list):
        return None
    for row in raw:
        if not isinstance(row, dict):
            continue
        requested = str(row.get("requested_service_id") or "").strip()
        if requested != service_id:
            continue
        approved = str(row.get("approved_text") or "").strip()
        alt_raw = row.get("alternative_service_ids")
        alts = (
            [str(item).strip() for item in alt_raw if str(item).strip()]
            if isinstance(alt_raw, list)
            else []
        )
        deduped: list[str] = []
        for alt_id in alts:
            if alt_id == service_id or alt_id in deduped:
                continue
            deduped.append(alt_id)
            if len(deduped) >= 2:
                break
        if approved and deduped:
            return approved, tuple(deduped)
    return None


def build_d2_clinic_policy_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    understanding,
) -> MaterializedResponseOutcome:
    """B10/D2-068: typed policy_ids → authored answers from tenant snapshot.

    Triggers and patient_text matching are never used.
    """
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("policy_client_mismatch")
    answers = _authored_policy_answers(snapshot)
    request = understanding.requests[0]
    inferred: list[str] = list(request.policy_ids)
    if request.payment_scheme_intent == "eligibility_question":
        payment_key = {"oms": "no_oms", "dms": "no_dms"}.get(request.payment_scheme)
        if payment_key and payment_key not in inferred:
            inferred.append(payment_key)
    subjects = {item.subject_id: item for item in understanding.subjects}
    subject = subjects.get(request.subject_id) if request.subject_id else None
    if (
        subject is not None
        and subject.age_group == "child"
        and request.context != "past_history"
        and "no_pediatric_dentistry" not in inferred
        and "no_pediatric_dentistry" in answers
    ):
        inferred.append("no_pediatric_dentistry")

    if not inferred:
        # Ambiguous «по полису?» without typed id/scheme → clarify (B10).
        return _d2_code_owned_answer(
            session_key=session_key,
            text=_POLICY_CLARIFY,
            route="CLARIFY",
        )

    texts: list[str] = []
    unknown = False
    for key in inferred:
        answer = answers.get(key)
        if answer is None:
            unknown = True
            continue
        texts.append(answer)
    if texts:
        return _d2_code_owned_answer(
            session_key=session_key,
            text="\n\n".join(texts),
            route="ANSWER",
        )
    # Unknown policy id or empty pack → honest gap, not yes/no (D2-069).
    assert unknown or not answers
    return _d2_code_owned_answer(
        session_key=session_key,
        text=_INFO_GAP,
        route="ANSWER",
    )


def build_d2_unknown_brand_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    brand_id: str,
) -> MaterializedResponseOutcome:
    """Use an exact authored brand alternative, otherwise an honest information gap."""
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("brand_client_mismatch")
    if brand_id in build_d2_bundle(snapshot).brands.brands:
        raise D2SnapshotBindingError("brand_is_known")
    text = _INFO_GAP
    rows = _clinic_policies_raw(snapshot).get("service_alternatives")
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict) or row.get("suggest_ref") != "implantation__info__implant_systems.md#korotko":
                continue
            keywords = row.get("match_keywords")
            if isinstance(keywords, list) and brand_id.casefold() in {
                str(item).strip().casefold() for item in keywords
            }:
                approved = row.get("note")
                if isinstance(approved, str) and approved.strip():
                    text = approved.strip()
                break
    return _d2_code_owned_answer(session_key=session_key, text=text, route="ANSWER")


def build_d2_unknown_reference_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
) -> MaterializedResponseOutcome:
    """Return the tenant-owned gap for a clearly named absent entity.

    The caller has already received the model's typed ``unresolved`` result.
    This function intentionally neither inspects nor normalizes patient prose.
    """
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("unknown_reference_client_mismatch")
    return _d2_code_owned_answer(
        session_key=session_key,
        text=_UNKNOWN_REFERENCE_GAP,
        route="ANSWER",
    )


def build_d2_brand_policy_response(
    snapshot: D2TenantSnapshot, *, session_key: SessionKey, brand_id: str,
) -> MaterializedResponseOutcome | None:
    """Resolve an explicit tenant brand policy by exact typed ID only."""
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("brand_policy_client_mismatch")
    raw = _clinic_policies_raw(snapshot).get("brand_alternatives")
    if not isinstance(raw, list):
        return None
    for row in raw:
        if not isinstance(row, dict) or row.get("requested_brand_id") != brand_id:
            continue
        text = row.get("approved_text")
        if isinstance(text, str) and text.strip():
            return _d2_code_owned_answer(session_key=session_key, text=text.strip(), route="ANSWER")
    return None


def build_d2_service_availability_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    service_id: str,
) -> MaterializedResponseOutcome:
    """B01/D2-024–025: authored alternative by typed service_id, else info gap.

    Inactive catalog status alone never becomes «не оказываем».
    """
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("availability_client_mismatch")
    authored = _authored_service_alternative(snapshot, service_id)
    if authored is None:
        return _d2_code_owned_answer(
            session_key=session_key,
            text=_INFO_GAP,
            route="ANSWER",
        )
    approved_text, alt_ids = authored
    bundle = build_d2_bundle(snapshot)
    options: list[ServiceOptionEntry] = []
    for alt_id in alt_ids:
        service = bundle.services.get(alt_id)
        if service is None or not service.active:
            raise D2SnapshotBindingError("authored_alternative_unavailable")
        options.append(ServiceOptionEntry(service_id=alt_id, display_name=service.name))
    alt_block = AuthoredServiceAlternativeBlock(
        source_client_id=snapshot.client_id,
        requested_service_id=service_id,
        approved_text=approved_text,
        options=tuple(options),
    )
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route="ANSWER", mode="standard"),),
            terminal_candidates=(),
        ),
        response_scope="service",
        selected_service_id=service_id,
        active_session_service_id=None,
        selected_topic_id=None,
        price_plan=PricePlan(kind="none"),
        authored_service_alternative_block=alt_block,
        ui_candidates=UiPlanCandidates(),
        transport_kind="blocking",
    )
    composer = ComposerResult(
        route="ANSWER",
        mode="standard",
        patient_text=None,
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


def _d2_code_owned_answer(
    *,
    session_key: SessionKey,
    text: str,
    route: str,
) -> MaterializedResponseOutcome:
    plan = PreComposerPlan(
        session_key=session_key,
        context_strategy="full_context",
        route_authority=ComposerSelectedRouteAuthority(
            allowed_route_modes=(RouteModePair(route=route, mode="standard"),),  # type: ignore[arg-type]
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
        route=route,  # type: ignore[arg-type]
        mode="standard",
        patient_text=text,
        code_owned_answer=(route == "ANSWER"),
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


def build_d2_unknown_term_response(
    snapshot: D2TenantSnapshot,
    *,
    session_key: SessionKey,
    already_clarified: bool,
) -> MaterializedResponseOutcome:
    """One clarification, then an honest gap; no term-specific memory or guess."""
    if snapshot.client_id != session_key.client_id:
        raise D2SnapshotBindingError("unknown_term_client_mismatch")
    return _d2_code_owned_answer(
        session_key=session_key,
        text=_UNKNOWN_TERM_GAP if already_clarified else _UNKNOWN_TERM_CLARIFY,
        route="ANSWER" if already_clarified else "CLARIFY",
    )
