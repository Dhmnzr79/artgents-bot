"""Frozen capability probe templates (Stage 3B honest probes)."""

from __future__ import annotations

from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from core.one_call_closed_envelope_validation import sample_valid_json_mode_envelope
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from evals.v5.one_call_flash_capability_contract import FROZEN_CAPABILITY_CASES

_MINIMAL_VALID_JSON_EXAMPLE = sample_valid_json_mode_envelope()

JSON_MODE_CAPABILITY_PROBE_USER = (
    "Capability probe: respond with one JSON object using json_object response format.\n"
    "Use exactly these 9 keys and no others:\n"
    "- route: ANSWER | ADMIN | CLARIFY\n"
    "- service_id: string or null\n"
    "- extent: one_tooth | few_teeth | full_arch | null\n"
    "- jaw: upper | lower | both | null\n"
    "- stage: string or null\n"
    "- scenario: pain_fear | cost | time | doctor_trust | result_reliability | none\n"
    "- clarify_axis: service | extent | jaw | stage | null\n"
    "- clarify_service_options: array of 2-3 service_id strings or null\n"
    "- patient_text: string or null\n"
    "Rules:\n"
    "- ANSWER requires non-empty patient_text; clarify_axis and clarify_service_options must be null.\n"
    "- ADMIN forbids patient_text, clarify_axis, and clarify_service_options.\n"
    "- CLARIFY requires patient_text and clarify_axis; service axis needs 2-3 service_id options.\n"
    f"Valid minimal JSON example:\n{_MINIMAL_VALID_JSON_EXAMPLE}\n"
    "Return only the JSON object for this capability probe."
)

LEGACY_CAPABILITY_PROBE_USER = (
    "Capability probe for production @ANSWER/@ADMIN line protocol.\n"
    "First non-empty line must be exactly @ANSWER or @ADMIN.\n"
    "If @ANSWER, the following lines must contain non-empty patient-facing text.\n"
    "If @ADMIN, hand off to administrator; following body is ignored.\n"
    "Respond in Russian with a minimal valid example for this probe."
)

_CACHE_COLD_USER_MESSAGE = "Сколько стоит имплантация одного зуба?"
_CACHE_REPEAT_USER_MESSAGE = "Есть ли рассрочка на имплантацию?"


def _capability_resolution() -> ExactSalesResolution:
    authority = ExactSalesFieldAuthority(authority="unknown", provenance="capability_probe")
    return ExactSalesResolution(
        None,
        None,
        None,
        None,
        None,
        authority,
        authority,
        authority,
        authority,
        authority,
    )


def _capability_sales_context() -> dict[str, object]:
    return {
        "cta": "lead",
        "needs_admin_quote": False,
        "allow_price": True,
    }


def build_cache_cold_dynamic_suffix() -> str:
    return build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=_capability_resolution(),
        current_strict_facts=(),
        sales_context=_capability_sales_context(),
        user_message=_CACHE_COLD_USER_MESSAGE,
    )


def build_cache_repeat_dynamic_suffix() -> str:
    return build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=_capability_resolution(),
        current_strict_facts=(),
        sales_context=_capability_sales_context(),
        user_message=_CACHE_REPEAT_USER_MESSAGE,
    )


def probe_template_for_case_id(case_id: str) -> str:
    if case_id == "cache_cold":
        return build_cache_cold_dynamic_suffix()
    if case_id == "cache_repeat":
        return build_cache_repeat_dynamic_suffix()
    if case_id in ("json_mode_blocking", "json_mode_streaming"):
        return JSON_MODE_CAPABILITY_PROBE_USER
    return LEGACY_CAPABILITY_PROBE_USER


def probe_templates_document() -> dict[str, str]:
    return {case.case_id: probe_template_for_case_id(case.case_id) for case in FROZEN_CAPABILITY_CASES}
