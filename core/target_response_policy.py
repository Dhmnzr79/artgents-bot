"""Minimal deterministic target ResponsePolicy builder (S33, offline/unwired)."""

from __future__ import annotations

from contracts.answer_plan import AspectKind
from contracts.target_response_length_profile import TargetResponseLengthProfile
from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetFollowupSource, TargetResponseSpec
from contracts.target_response_stage import is_scope_aware_price_stage


class TargetResponsePolicyBuildError(ValueError):
    """Typed failure for a wrong explicit S33 request object."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _followup_source(request: TargetResponsePolicyRequest) -> TargetFollowupSource | None:
    if request.scope_price_topic is not None and request.response_stage is None:
        return None
    if is_scope_aware_price_stage(request.response_stage):
        if request.response_stage in {"broad_family_price", "stage_clarify"}:
            return None
        if request.response_stage in {"scoped_family_price", "concrete_service_price"}:
            return "price"
        return None
    if request.response_mode in {"clarify", "defer"}:
        return None
    if request.primary_component in {"content", "price"}:
        return request.primary_component
    if request.primary_component == "doctors":
        return None
    if "content" in request.requested_components:
        return "content"
    if "price" in request.requested_components:
        return "price"
    return None


def broad_family_price_directive_overlay(
    response_stage: str | None,
    *,
    family_only: bool = False,
) -> dict[str, object]:
    if response_stage != "broad_family_price":
        return {}
    overlay: dict[str, object] = {
        "broad_family_price_compact": True,
        "max_price_anchors": 1 if family_only else 4,
        "omit_sections": (
            "payment_stages",
            "package_composition",
            "long_bonus_lists",
        ),
        "include_scale_clarify": not family_only,
    }
    if family_only:
        overlay["family_only_broad_price"] = True
    return overlay


def data_gap_protocol_unconfirmed_directive_overlay(
    response_stage: str | None,
    *,
    protocol_unconfirmed: bool = False,
) -> dict[str, object]:
    if response_stage != "data_gap" or not protocol_unconfirmed:
        return {}
    return {
        "data_gap_protocol_unconfirmed": True,
        "answer_mode": "topic_confirmed_protocol_not_priced_separately",
    }


def stage_clarify_directive_overlay(response_stage: str | None) -> dict[str, object]:
    if response_stage != "stage_clarify":
        return {}
    return {
        "stage_clarify_concise": True,
        "answer_mode": "short_stage_question_only",
    }


def build_target_response_spec(
    request: TargetResponsePolicyRequest,
) -> TargetResponseSpec:
    """Build one canonical spec while deriving only its follow-up family."""

    if type(request) is not TargetResponsePolicyRequest:
        raise TargetResponsePolicyBuildError(
            "response_policy_request_invalid",
            request,
        )
    return TargetResponseSpec(
        response_mode=request.response_mode,
        service_id=request.service_id,
        response_stage=request.response_stage,
        scope_price_topic=request.scope_price_topic,
        tone_key=request.tone_key,
        allowed_topics=request.allowed_topics,
        forbidden_topics=request.forbidden_topics,
        required_fact_ids=request.required_fact_ids,
        required_components=request.requested_components,
        followup_source=_followup_source(request),
        allow_marketing_facts=request.allow_marketing_facts,
        allow_consultation_close=request.allow_consultation_close,
        allow_cta=request.allow_cta,
    )


def select_target_response_length_profile(
    spec: TargetResponseSpec,
    *,
    aspects: tuple[AspectKind, ...] = (),
    aspects_valid: bool = True,
    marketing_scenarios: tuple[str, ...] = (),
    needs_clarification: bool = False,
) -> TargetResponseLengthProfile:
    """Single canonical producer (PERF-5, corrected) for the adaptive answer-length
    profile.

    Reads only already-existing structured signals -- no regex, no phrase list, no
    new classifier, no second router, no signal derived from the user's raw question
    length. ``aspects``/``aspects_valid``/``marketing_scenarios``/
    ``needs_clarification`` are optional because ``TargetResponseSpec`` alone (the one
    contract available at every real call site today) already carries
    ``response_mode``/``response_stage``/``required_components``/
    ``required_fact_ids``/``allow_marketing_facts`` -- callers that also have a real
    TurnFrame-derived aspect/marketing-scenario signal (the production seam,
    ``core/target_turn_frame_bound_response.py``) pass it explicitly; callers that do
    not still get a safe, correct profile.

    ``aspects_valid`` mirrors ``turn_frame.field_meta.aspects.status == "valid"`` --
    when the aspect signal itself is missing/defaulted/invalid, both the comparison
    and the simple_faq branches are gated off (an untrusted or absent aspect list must
    never be read as "no comparison" or "exactly one confirmed aspect"). ``simple_faq``
    additionally requires exactly one aspect (``len(aspects) == 1``), matching the
    owner's exact "one informational aspect, proven" requirement -- multiple aspects,
    zero aspects, or an invalid aspect signal all fall through to
    ``standard_information``, never guessed.

    Any ambiguity falls through to ``standard_information`` -- never guessed.
    """

    if type(spec) is not TargetResponseSpec:
        raise TargetResponsePolicyBuildError("response_length_profile_spec_invalid", spec)

    if (
        spec.response_mode == "clarify"
        or spec.response_stage == "stage_clarify"
        or needs_clarification
    ):
        return "clarification_concise"
    if spec.response_stage == "broad_family_price":
        return "broad_price_overview"
    if spec.response_stage == "scoped_family_price":
        return "scoped_price"
    if spec.response_stage == "concrete_service_price":
        if aspects_valid and "comparison" in aspects:
            return "comparison_or_complex"
        return "scoped_price"
    if aspects_valid and "comparison" in aspects:
        return "comparison_or_complex"
    if marketing_scenarios and spec.required_components == ("content",):
        return "marketing_concern"
    if (
        spec.response_stage is None
        and spec.required_components == ("content",)
        and not spec.allow_marketing_facts
        and not marketing_scenarios
        and len(spec.required_fact_ids) <= 1
        and aspects_valid
        and len(aspects) == 1
    ):
        return "simple_faq"
    return "standard_information"
