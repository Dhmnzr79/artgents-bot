"""Typed FullContext presentation decision: choice/secondary/price slots, video, situation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from contracts.target_response_spec import TargetResponseSpec
from contracts.ui_scope_action import is_ui_scope_ref
from contracts.ui_stage_action import is_ui_stage_ref
from core.target_client_ui_nav import TargetNavigationFollowup
from core.target_presentation_source_identity import read_doc_presentation_meta
from core.target_response_followup_materializer import (
    TargetContentFollowup,
    TargetPriceFollowup,
    materialize_target_response_followups,
)
from core.target_response_materialization_plan import TargetResponseMaterializationPlan
from core.target_offline_response_assembly import TargetOfflineResponseMaterials
from core.target_response_followup_policy import TargetResponseFollowupSelection
from core.video_catalog_loader import resolve_video_payload
from core.target_marketing_selector import TargetMarketingSelection

CHOICE_MENU_MAX = 4
SECONDARY_CONTENT_MAX = 2
PRICE_DETAIL_MAX = 2

FollowupChannel = Literal["choice", "content", "price", "none"]


@dataclass(frozen=True, slots=True)
class TargetPresentationCadenceState:
    shown_video_ids: frozenset[str] = frozenset()
    shown_content_followup_refs: frozenset[str] = frozenset()
    shown_price_followup_refs: frozenset[str] = frozenset()
    situation_offered: bool = False


@dataclass(frozen=True, slots=True)
class TargetPresentationCadenceUpdate:
    shown_video_ids: tuple[str, ...] = ()
    shown_content_followup_refs: tuple[str, ...] = ()
    shown_price_followup_refs: tuple[str, ...] = ()
    situation_offered: bool = False


@dataclass(frozen=True, slots=True)
class TargetPresentationDecision:
    quick_replies: tuple[dict[str, str], ...]
    video: dict[str, str] | None
    situation: dict[str, bool | str]
    dropped: tuple[str, ...]
    cadence_update: TargetPresentationCadenceUpdate
    channel: FollowupChannel = "none"


def classify_followup_ref(ref: str) -> FollowupChannel:
    value = str(ref or "").strip()
    if is_ui_scope_ref(value) or is_ui_stage_ref(value):
        return "choice"
    if value.startswith("price:"):
        return "price"
    return "content"


def _qr(label: str, ref: str) -> dict[str, str]:
    return {"label": label, "ref": ref}


def _cap_choice_items(
    navigation: tuple[TargetNavigationFollowup, ...],
    *,
    shown_refs: frozenset[str],
) -> tuple[tuple[dict[str, str], ...], tuple[str, ...]]:
    selected: list[dict[str, str]] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for item in navigation:
        ref = str(item.ref or "").strip()
        if not ref or ref in seen:
            continue
        if classify_followup_ref(ref) != "choice":
            dropped.append(f"choice_invalid_ref:{ref}")
            continue
        seen.add(ref)
        if ref in shown_refs:
            dropped.append(f"choice_already_shown:{ref}")
            continue
        if len(selected) >= CHOICE_MENU_MAX:
            dropped.append(f"choice_over_limit:{ref}")
            continue
        selected.append(_qr(item.label, ref))
    return tuple(selected), tuple(dropped)


def _cap_price_items(
    price_followups: tuple[TargetPriceFollowup, ...],
    *,
    shown_refs: frozenset[str],
) -> tuple[tuple[dict[str, str], ...], tuple[str, ...]]:
    selected: list[dict[str, str]] = []
    dropped: list[str] = []
    seen: set[str] = set()
    for item in price_followups:
        ref = str(item.ref or "").strip()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        if ref in shown_refs:
            dropped.append(f"price_already_shown:{ref}")
            continue
        if len(selected) >= PRICE_DETAIL_MAX:
            dropped.append(f"price_over_limit:{ref}")
            continue
        selected.append(_qr(item.label, ref))
    return tuple(selected), tuple(dropped)


def _content_candidates(
    *,
    md_root: Path | None,
    primary_content_ref: str | None,
    content_followups: tuple[TargetContentFollowup, ...],
) -> tuple[TargetContentFollowup, ...]:
    if content_followups:
        return content_followups
    if not primary_content_ref or md_root is None:
        return ()
    plan = TargetResponseMaterializationPlan(
        service_id=None,
        selected_brand_id=None,
        required_components=("content",),
        unfulfilled_components=(),
        primary_content_ref=primary_content_ref,
        offer_ids=(),
        doctor_ids=(),
        commercial_fact_ids=(),
        external_source_refs=(),
        consultation_content_ref=None,
        cta_key="",
    )
    materials = TargetOfflineResponseMaterials(
        service_id=None,
        service=None,
        selected_brand_id=None,
        brand=None,
        matched_rule_id=None,
        max_options=0,
        offers=(),
        doctors=(),
        selected_content_ref=primary_content_ref,
        marketing_selection=TargetMarketingSelection(
            applied_scenarios=(),
            selected_refs=(),
            amplifier_refs=(),
            cta_key="",
        ),
        commercial_facts=(),
        external_source_refs=(),
        consultation_close=None,
        marketing_slots_used=0,
        amplifier_slots_used=0,
    )
    try:
        bundle = materialize_target_response_followups(
            plan,
            materials,
            md_root=md_root,
        )
    except Exception:
        return ()
    return bundle.content


def _cap_secondary_content(
    *,
    md_root: Path | None,
    client_id: str,
    primary_content_ref: str | None,
    content_followups: tuple[TargetContentFollowup, ...],
    cadence: TargetPresentationCadenceState,
    allow_situation: bool,
) -> tuple[tuple[dict[str, str], ...], dict[str, str] | None, dict[str, bool | str], TargetPresentationCadenceUpdate, tuple[str, ...]]:
    dropped: list[str] = []
    selected: list[dict[str, str]] = []
    shown_video = set(cadence.shown_video_ids)
    shown_content = set(cadence.shown_content_followup_refs)
    video_payload: dict[str, str] | None = None
    situation = {"show": False, "mode": "normal"}
    cadence_video: list[str] = []
    cadence_content: list[str] = []
    situation_offered = cadence.situation_offered

    meta = (
        read_doc_presentation_meta(md_root, primary_content_ref or "")
        if md_root is not None
        else {}
    )
    video_key = str(meta.get("video_key") or "").strip() or None
    situation_allowed = bool(meta.get("situation_allowed"))

    slots = SECONDARY_CONTENT_MAX
    if video_key and video_key not in shown_video:
        resolved = resolve_video_payload(client_id=client_id, video_key=video_key)
        if resolved is not None:
            video_payload = resolved
            cadence_video.append(video_key)
            slots -= 1
        else:
            dropped.append(f"video_invalid:{video_key}")

    candidates = _content_candidates(
        md_root=md_root,
        primary_content_ref=primary_content_ref,
        content_followups=content_followups,
    )
    queue = [item for item in candidates if item.ref not in shown_content]

    for item in queue:
        if slots <= 0:
            dropped.append(f"content_over_limit:{item.ref}")
            continue
        selected.append(_qr(item.label, item.ref))
        cadence_content.append(item.ref)
        slots -= 1

    if (
        allow_situation
        and situation_allowed
        and not situation_offered
        and slots > 0
    ):
        situation = {"show": True, "mode": "normal"}
        situation_offered = True
        slots -= 1

    update = TargetPresentationCadenceUpdate(
        shown_video_ids=tuple(cadence_video),
        shown_content_followup_refs=tuple(cadence_content),
        shown_price_followup_refs=(),
        situation_offered=situation_offered and situation["show"] is True,
    )
    return tuple(selected), video_payload, situation, update, tuple(dropped)


def decide_target_presentation(
    *,
    client_id: str,
    md_root: Path | None,
    spec: TargetResponseSpec,
    navigation_followups: tuple[TargetNavigationFollowup, ...],
    selected_followups: TargetResponseFollowupSelection,
    primary_content_ref: str | None,
    cadence: TargetPresentationCadenceState,
    allow_situation: bool,
    alternative_secondary_override: tuple[object, ...] | None = None,
) -> TargetPresentationDecision:
    """Apply governed slot limits with exactly one navigation channel per response."""

    if alternative_secondary_override:
        from contracts.one_call_presentation_result import PresentationQuickReply

        secondary_qr = tuple(
            {"label": item.label, "ref": item.ref}
            for item in alternative_secondary_override
            if isinstance(item, PresentationQuickReply)
        )
        return TargetPresentationDecision(
            quick_replies=secondary_qr,
            video=None,
            situation={"show": False, "mode": "normal"},
            dropped=tuple(
                f"content_suppressed_by_alternative:{item.ref}"
                for item in selected_followups.content
            ),
            cadence_update=TargetPresentationCadenceUpdate(),
            channel="content",
        )

    all_dropped: list[str] = []
    shown_all = cadence.shown_content_followup_refs | cadence.shown_price_followup_refs

    choice_qr, choice_dropped = _cap_choice_items(
        navigation_followups,
        shown_refs=shown_all,
    )
    all_dropped.extend(choice_dropped)

    price_qr, price_dropped = _cap_price_items(
        selected_followups.price,
        shown_refs=cadence.shown_price_followup_refs,
    )
    all_dropped.extend(price_dropped)

    video: dict[str, str] | None = None
    situation = {"show": False, "mode": "normal"}
    cadence_update = TargetPresentationCadenceUpdate()
    channel: FollowupChannel = "none"
    quick_replies: tuple[dict[str, str], ...] = ()

    if choice_qr:
        channel = "choice"
        quick_replies = choice_qr
        if selected_followups.content:
            for item in selected_followups.content:
                all_dropped.append(f"content_suppressed_by_choice_menu:{item.ref}")
        if price_qr:
            for item in price_qr:
                all_dropped.append(f"price_suppressed_by_choice_menu:{item['ref']}")
    elif price_qr and "price" in spec.required_components:
        channel = "price"
        quick_replies = price_qr
        cadence_update = TargetPresentationCadenceUpdate(
            shown_price_followup_refs=tuple(item["ref"] for item in price_qr),
        )
        if selected_followups.content:
            for item in selected_followups.content:
                all_dropped.append(f"content_suppressed_by_price_channel:{item.ref}")
    else:
        secondary_qr, video, situation, cadence_update, secondary_dropped = _cap_secondary_content(
            md_root=md_root,
            client_id=client_id,
            primary_content_ref=primary_content_ref,
            content_followups=selected_followups.content,
            cadence=cadence,
            allow_situation=allow_situation,
        )
        all_dropped.extend(secondary_dropped)
        if secondary_qr or video is not None or situation.get("show"):
            channel = "content"
            quick_replies = secondary_qr
            cadence_update = TargetPresentationCadenceUpdate(
                shown_video_ids=cadence_update.shown_video_ids,
                shown_content_followup_refs=cadence_update.shown_content_followup_refs,
                shown_price_followup_refs=(),
                situation_offered=cadence_update.situation_offered,
            )
        elif price_qr:
            channel = "price"
            quick_replies = price_qr
            cadence_update = TargetPresentationCadenceUpdate(
                shown_price_followup_refs=tuple(item["ref"] for item in price_qr),
            )
        else:
            if price_qr:
                for item in price_qr:
                    all_dropped.append(f"price_suppressed_no_channel:{item['ref']}")

    return TargetPresentationDecision(
        quick_replies=quick_replies,
        video=video,
        situation=situation,
        dropped=tuple(all_dropped),
        cadence_update=cadence_update,
        channel=channel,
    )
