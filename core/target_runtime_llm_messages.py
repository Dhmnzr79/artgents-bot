"""Shared LLM message builders for target runtime backends (S61)."""

from __future__ import annotations

import json

from core.target_composer_executor import TargetComposerInvocation
from core.target_response_verifier import TargetSemanticVerifierInvocation

_COMPOSER_USER_TEMPLATE = (
    "Compose the patient-facing answer using the inputs below.\n\n"
    "Return strict JSON only: "
    '{"answer":"<text>","source_identity":{"primary_content_ref":"<md or null>",'
    '"used_content_refs":["<md filenames>"]}}\n\n'
    "CACHED_FULL_CONTEXT:\n{cached_full_context}\n\n"
    "RESPONSE_DIRECTIVES_JSON:\n{response_directives_json}\n\n"
    "GOVERNED_ACTION_CONTEXT_JSON:\n{governed_action_context_json}\n\n"
    "PRIMARY_EVIDENCE_JSON:\n{primary_evidence_json}\n\n"
    "USER_MESSAGE:\n{user_message}"
)

_VERIFIER_USER_TEMPLATE = (
    "Assess the candidate answer using the inputs below.\n\n"
    "CACHED_FULL_CONTEXT:\n{cached_full_context}\n\n"
    "RESPONSE_SPEC_JSON:\n{response_spec_json}\n\n"
    "PRIMARY_EVIDENCE_JSON:\n{primary_evidence_json}\n\n"
    "CANDIDATE_TEXT:\n{candidate_text}\n\n"
    "Return JSON only: "
    '{{"issues":[{{"kind":"<unsupported_clinic_claim|personal_medical_conclusion|'
    "material_external_medical_claim|minor_external_detail>\","
    '"offending_span":"<exact substring from candidate>"}}]}}'
)

_BOUNDARY_USER_TEMPLATE = (
    "Classify this patient message for medical boundary.\n\n"
    "Return JSON with exactly two fields:\n"
    '- "decision": "none" or "medical_handoff"\n'
    '- "confidence": number from 0.0 to 1.0\n\n'
    "Patient message:\n{message}"
)


def build_composer_sdk_messages(
    invocation: TargetComposerInvocation,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": invocation.system_policy},
        {
            "role": "user",
            "content": _COMPOSER_USER_TEMPLATE.format(
                cached_full_context=invocation.cached_full_context,
                response_directives_json=invocation.response_directives_json,
                governed_action_context_json=(
                    invocation.governed_action_context_json or "null"
                ),
                primary_evidence_json=invocation.primary_evidence_json,
                user_message=invocation.user_message,
            ),
        },
    ]


def build_verifier_sdk_messages(
    invocation: TargetSemanticVerifierInvocation,
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": invocation.system_policy},
        {
            "role": "user",
            "content": _VERIFIER_USER_TEMPLATE.format(
                cached_full_context=invocation.cached_full_context,
                response_spec_json=invocation.response_spec_json,
                primary_evidence_json=invocation.primary_evidence_json,
                candidate_text=invocation.candidate_text,
            ),
        },
    ]


def build_boundary_sdk_messages(*, system_policy: str, user_message: str) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": system_policy},
        {
            "role": "user",
            "content": _BOUNDARY_USER_TEMPLATE.format(message=user_message[:900]),
        },
    ]


def parse_verifier_assessment_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("semantic_not_object")
    if set(payload.keys()) != {"issues"}:
        raise ValueError("semantic_field_mismatch")
    return json.loads(json.dumps(payload, ensure_ascii=False))
