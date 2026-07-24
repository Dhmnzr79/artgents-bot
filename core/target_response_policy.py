"""Minimal deterministic target ResponsePolicy builder (S33, offline/unwired)."""

from __future__ import annotations

from contracts.target_response_policy import TargetResponsePolicyRequest
from contracts.target_response_spec import TargetFollowupSource, TargetResponseSpec


class TargetResponsePolicyBuildError(ValueError):
    """Typed failure for a wrong explicit S33 request object."""

    def __init__(self, code: str, value: object) -> None:
        self.code = code
        self.value = value
        super().__init__(f"{code}: {value!r}")


def _followup_source(request: TargetResponsePolicyRequest) -> TargetFollowupSource | None:
    if request.family_price_overview_topic is not None:
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
        family_price_overview_topic=request.family_price_overview_topic,
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
