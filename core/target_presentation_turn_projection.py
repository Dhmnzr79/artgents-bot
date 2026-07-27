"""Deterministic TurnFrame → marketing/semantic projection for target runtime."""

from __future__ import annotations

from contracts.target_response_spec import TargetResponseSpec
from contracts.turn_frame import TurnFrame


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


def derive_marketing_scenarios(turn_frame: TurnFrame) -> tuple[str, ...]:
    """Project 0–2 typed scenarios from planner TurnFrame fields only."""

    scenarios: list[str] = []
    if turn_frame.emotion == "fear":
        scenarios.append("pain_fear")
    if turn_frame.emotion == "doubt":
        scenarios.append("doctor_trust")
    if turn_frame.primary_aspect == "price":
        scenarios.append("cost")
    deduped: list[str] = []
    seen: set[str] = set()
    for item in scenarios:
        if item in seen:
            continue
        seen.add(item)
        deduped.append(item)
    return tuple(deduped[:2])


def should_include_initial_marketing_block(
    turn_frame: TurnFrame,
    spec: TargetResponseSpec,
) -> bool:
    """Initial commercial block for ordinary service/content answers, not price/clarify."""

    if turn_frame.needs_clarification:
        return False
    if "price" in spec.required_components and spec.required_components != ("content", "price"):
        return False
    if spec.response_mode not in {"answer", "medical_handoff"}:
        return False
    return True


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
