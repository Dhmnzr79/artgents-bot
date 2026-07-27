"""Deterministic TurnFrame → marketing/semantic projection for target runtime."""

from __future__ import annotations

from collections.abc import Sequence

from contracts.target_response_spec import TargetResponseSpec
from contracts.turn_frame import TurnFrame
from core.target_contact_authority import contact_fields_from_turn_aspects
from core.target_fullcontext_content_package import is_fullcontext_service_optional_spec


def resolve_target_semantic_context(
    turn_frame: TurnFrame,
    spec: TargetResponseSpec,
) -> str:
    """Map price/doctors/service/default without regex on user text."""

    if turn_frame.primary_aspect == "price" or "price" in spec.required_components:
        return "price"
    if turn_frame.topic == "doctors" or spec.required_components == ("doctors",):
        return "doctors"
    if turn_frame.service_id or spec.service_id:
        return "service"
    return "default"


def contact_fields_from_turn_frame(turn_frame: TurnFrame) -> tuple[str, ...] | None:
    """Return typed contact fields when planner classified a direct contact question."""

    aspects = tuple(turn_frame.aspects)
    primary = turn_frame.primary_aspect
    if not any(
        aspect in aspects or aspect == primary
        for aspect in (
            "contacts",
            "contact_phone",
            "contact_address",
            "contact_parking",
            "contact_hours",
            "contact_whatsapp",
        )
    ):
        return None
    fields = contact_fields_from_turn_aspects(aspects, primary_aspect=primary)
    return tuple(fields) if fields else None


def contact_aspect_from_turn_frame(turn_frame: TurnFrame) -> str | None:
    """Legacy coarse contact aspect for package wiring."""

    if contact_fields_from_turn_frame(turn_frame) is None:
        return None
    return "contacts"


def marketing_scenarios_from_turn_frame(turn_frame: TurnFrame) -> tuple[str, ...]:
    """Validated planner-owned marketing scenarios (0–2)."""

    return tuple(turn_frame.marketing_scenarios)


def should_include_initial_marketing_block(
    turn_frame: TurnFrame,
    spec: TargetResponseSpec,
) -> bool:
    """Initial commercial block for ordinary service/content answers, not price/clarify."""

    if turn_frame.needs_clarification:
        return False
    if contact_fields_from_turn_frame(turn_frame) is not None:
        return False
    if "price" in spec.required_components and spec.required_components != ("content", "price"):
        return False
    if spec.response_mode not in {"answer", "medical_handoff"}:
        return False
    if is_fullcontext_service_optional_spec(spec):
        return False
    if not spec.allow_marketing_facts:
        return False
    return True


def resolve_bound_marketing_flags(
    turn_frame: TurnFrame,
    bound_spec: TargetResponseSpec,
    *,
    boundary_allows_marketing: bool,
    brand_term: str | None,
    marketing_scenarios: Sequence[str],
) -> tuple[bool, tuple[str, ...], str | None]:
    """Intersect turn-level marketing intent with final bound spec permissions."""

    if not boundary_allows_marketing:
        return False, (), None
    include_initial_block = should_include_initial_marketing_block(turn_frame, bound_spec)
    if not include_initial_block:
        return False, (), None
    scenarios = tuple(marketing_scenarios) if marketing_scenarios else ()
    resolved_brand = brand_term if include_initial_block else None
    return include_initial_block, scenarios, resolved_brand


def provisional_spec_from_turn_frame(
    turn_frame: TurnFrame,
    *,
    allowed_topics: tuple[str, ...],
    tone_key: str = "commercial_warm",
) -> TargetResponseSpec:
    """Approximate bound spec from TurnFrame for pre-pipeline presentation gates."""

    if turn_frame.primary_aspect == "price" or "price" in turn_frame.aspects:
        required_components: tuple[str, ...] = ("price",)
    elif (
        turn_frame.topic == "doctors"
        or turn_frame.primary_aspect == "doctors"
        or "doctors" in turn_frame.aspects
    ):
        required_components = ("doctors",)
    else:
        required_components = ("content",)
    return TargetResponseSpec(
        response_mode="answer",
        service_id=turn_frame.service_id,
        tone_key=tone_key,
        allowed_topics=allowed_topics,
        required_components=required_components,  # type: ignore[arg-type]
    )
