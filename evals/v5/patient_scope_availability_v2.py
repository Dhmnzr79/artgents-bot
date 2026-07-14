"""Pure A9 v2 availability taxonomy; not wired into the live harness yet."""

from __future__ import annotations

from typing import Any


NOT_APPLICABLE_STATUS = "not_applicable"
PRE_PLANNER_MANUAL_CONTACT_REASON = "pre_planner_manual_contact"
_MANUAL_CONTACT_SERVICE_ROUTE = "ingress_manual_contact"
_RUNTIME_STATUS_PRIORITY = frozenset({"not_available", "degraded"})


def classify_manual_contact_not_applicable(
    response: dict[str, Any],
) -> tuple[str, str] | None:
    """Classify only an intentional pre-planner manual-contact observation gap."""
    if not isinstance(response, dict):
        return None
    meta = response.get("meta")
    if not isinstance(meta, dict):
        return None
    service_route = str(meta.get("service_route") or "").strip().lower()
    if service_route != _MANUAL_CONTACT_SERVICE_ROUTE:
        return None

    if "metadata_first" not in meta:
        return NOT_APPLICABLE_STATUS, PRE_PLANNER_MANUAL_CONTACT_REASON
    metadata_first = meta["metadata_first"]
    if not isinstance(metadata_first, dict):
        return None
    shadow_status = str(
        metadata_first.get("turn_frame_shadow_status") or ""
    ).strip().lower()
    if shadow_status in _RUNTIME_STATUS_PRIORITY:
        return None
    if "turn_frame_shadow" in metadata_first:
        return None
    return NOT_APPLICABLE_STATUS, PRE_PLANNER_MANUAL_CONTACT_REASON
