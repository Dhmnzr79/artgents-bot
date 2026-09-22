"""Bind one immutable tenant snapshot to the existing isolated D2 sources."""

from __future__ import annotations

from pathlib import Path

import yaml

from contracts.d2_tenant_snapshot import D2ModelView, D2TenantSnapshot
from contracts.one_call_envelope import OneCallEnvelope
from contracts.response_plan import SessionKey, UiButtonCandidate, UiQuickReplyCandidate, UiVideoCandidate
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
    ResponsePlanMaterializationSources,
)
from core.d2_tenant_snapshot import build_d2_bundle, build_d2_model_view
from contracts.response_plan_post_composer import PostComposerMaterialAuthority


class D2SnapshotBindingError(ValueError):
    pass


_PRICE_UNAVAILABLE = "К сожалению, у меня пока нет информации о стоимости этой услуги"
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
    by_ref = {item.content_ref: item for item in snapshot.content}
    for request in understanding.requests:
        if request.kind != "content" or request.content_ref is None:
            continue
        authority = by_ref.get(request.content_ref)
        if authority is None:
            raise D2SnapshotBindingError("content_ref_unavailable")
        available = {section.section_ref for section in authority.sections}
        if any(ref not in available for ref in request.content_section_refs):
            raise D2SnapshotBindingError("content_section_ref_unavailable")
        metadata = _frontmatter(snapshot, request.content_ref)
        document_topic = metadata.get("topic")
        if request.topic_id is not None and document_topic != request.topic_id:
            raise D2SnapshotBindingError("content_topic_scope_unavailable")
        if request.service_id is not None and request.service_id not in authority.allowed_service_ids:
            raise D2SnapshotBindingError("content_service_scope_unavailable")

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
