"""Load client-owned scope/stage navigation labels from ui.yaml (AC3)."""

from __future__ import annotations

from dataclasses import dataclass

from contracts.target_service_applicability import PatientStage
from contracts.ui_scope_action import ScopeExtent, build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref
from core.client_config_loader import load_ui_raw


@dataclass(frozen=True, slots=True)
class TargetNavigationFollowup:
    label: str
    ref: str


def _label_map(section: object) -> dict[str, str]:
    if not isinstance(section, dict):
        return {}
    labels: dict[str, str] = {}
    for key, value in section.items():
        if isinstance(value, dict):
            label = str(value.get("label") or "").strip()
        else:
            label = str(value or "").strip()
        if label:
            labels[str(key)] = label
    return labels


def load_scope_nav_labels(client_id: str, *, topic: str) -> dict[ScopeExtent, str]:
    ui = load_ui_raw(client_id)
    scope_nav = ui.get("scope_nav") if isinstance(ui.get("scope_nav"), dict) else {}
    topic_block = scope_nav.get(str(topic).strip().lower())
    raw = _label_map(topic_block)
    result: dict[ScopeExtent, str] = {}
    for extent in ("one_tooth", "few_teeth", "full_arch"):
        label = raw.get(extent)
        if label:
            result[extent] = label  # type: ignore[assignment]
    return result


def load_stage_nav_labels(client_id: str, *, topic: str) -> dict[PatientStage, str]:
    ui = load_ui_raw(client_id)
    stage_nav = ui.get("stage_nav") if isinstance(ui.get("stage_nav"), dict) else {}
    topic_block = stage_nav.get(str(topic).strip().lower())
    raw = _label_map(topic_block)
    result: dict[PatientStage, str] = {}
    for stage in ("natural_tooth_present", "extraction_context", "implant_placed"):
        label = raw.get(stage)
        if label:
            result[stage] = label  # type: ignore[assignment]
    return result


def materialize_scope_nav_followups(
    client_id: str,
    *,
    topic: str,
) -> tuple[TargetNavigationFollowup, ...]:
    labels = load_scope_nav_labels(client_id, topic=topic)
    items: list[TargetNavigationFollowup] = []
    for extent in ("one_tooth", "few_teeth", "full_arch"):
        label = labels.get(extent)
        if not label:
            continue
        items.append(
            TargetNavigationFollowup(
                label=label,
                ref=build_ui_scope_ref(topic=topic, extent=extent),
            )
        )
    return tuple(items)


def materialize_stage_nav_followups(
    client_id: str,
    *,
    topic: str,
    stages: tuple[PatientStage, ...],
) -> tuple[TargetNavigationFollowup, ...]:
    labels = load_stage_nav_labels(client_id, topic=topic)
    items: list[TargetNavigationFollowup] = []
    for stage in stages:
        label = labels.get(stage)
        if not label:
            continue
        items.append(
            TargetNavigationFollowup(
                label=label,
                ref=build_ui_stage_ref(topic=topic, stage=stage),
            )
        )
    return tuple(items)
