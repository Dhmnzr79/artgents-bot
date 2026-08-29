from __future__ import annotations

import json

import pytest

from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError, parse_production_envelope_json, production_envelope_template
from core.sales_one_plus_protocol import (
    SALES_ONE_PLUS_SYSTEM_POLICY,
    SalesOnePlusProtocolError,
    parse_sales_one_plus_output,
)
from tests.test_sales_one_plus_turn import (
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_REF_CATALOG,
    answer_envelope,
    admin_envelope,
)


def test_legacy_line_protocol_answer_and_admin_body_rules() -> None:
    assert parse_sales_one_plus_output("\n@ANSWER\nГотовый ответ") == ("answer", "Готовый ответ")
    assert parse_sales_one_plus_output("@ADMIN\nmodel prose is ignored") == ("admin", None)
    assert parse_sales_one_plus_output("@ANSWER Да, у здания есть парковка") == (
        "answer",
        "Да, у здания есть парковка",
    )
    assert parse_sales_one_plus_output("@ADMIN inline ignored body") == ("admin", None)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "hello",
        "@ANSWER\n  ",
        "@ANSWERABLE",
        "@ANSWERABLE\nbody",
        3,
    ],
)
def test_legacy_line_protocol_rejects_malformed_output(raw: object) -> None:
    with pytest.raises(SalesOnePlusProtocolError):
        parse_sales_one_plus_output(raw)


def test_production_policy_requires_json_only_transport() -> None:
    assert "@ANSWER" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "@ADMIN" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "Return exactly one JSON control envelope" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "route=ADMIN" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "route=CLARIFY" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "Future fears about pain, price, osseointegration, trust, or timing" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "PRE_MODEL_HINTS.ambiguous_scope_hint is true" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "PRE_MODEL_HINTS and recent dialog context are non-authoritative" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "SALES_CONTEXT.needs_admin_quote is true" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "Classify commercial_intent only" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "deterministic code renders those values" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "Marketing promotions" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "A price for several teeth" not in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "deterministic code owns follow-ups, button slots, and CTA" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "Never calculate, multiply, sum, or interpolate prices" in SALES_ONE_PLUS_SYSTEM_POLICY


def test_production_policy_medical_faq_boundary() -> None:
    policy = SALES_ONE_PLUS_SYSTEM_POLICY.casefold()
    assert "complex medical questions" not in policy
    assert "general informational medical faq" in policy
    assert "route=answer grounded in the corpus" in policy
    assert "positive reviews" in policy
    assert "ordinary requests to contact a doctor or staff member are route=answer" in policy
    assert "uncertainty alone is not grounds for admin" in policy
    assert "if the wording does not prove a personal problematic request" in policy


def test_production_policy_grounded_data_gap_rule() -> None:
    policy = SALES_ONE_PLUS_SYSTEM_POLICY.casefold()
    assert "complete clinic data" not in policy
    assert "authoritative supplied data for the current clinic" in SALES_ONE_PLUS_SYSTEM_POLICY
    assert "lacks confirmed information" in policy
    assert "clinic administrator can clarify" in policy
    assert "do not treat missing corpus data alone as route=admin" in policy
    assert "do not use route=clarify when the missing fact cannot be supplied" in policy
    assert "do not invent or borrow another clinic's facts" in policy
    assert "wi-fi" not in policy
    assert "пандус" not in policy


def test_production_policy_preserves_admin_and_medical_faq_boundaries() -> None:
    policy = SALES_ONE_PLUS_SYSTEM_POLICY.casefold()
    assert "route=admin is for problematic or non-conversion requests" in policy
    assert "general informational medical faq" in policy
    assert "route=answer grounded in the corpus" in policy
    assert "do not diagnose, prescribe, or give a personal eligibility verdict" in policy


def test_production_policy_data_gap_is_answer_not_admin_or_clarify() -> None:
    policy = SALES_ONE_PLUS_SYSTEM_POLICY
    assert "route=ANSWER with concise honest patient_text" in policy
    assert "route=CLARIFY only when the answer truly depends on missing service/extent/jaw/stage scope" in policy


def test_pre_flash_hints_expose_ambiguous_scope_without_authoritative_resolution() -> None:
    from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
    from core.sales_fast_strict_evidence import build_pre_flash_prompt_hints
    from core.sales_one_plus_protocol import (
        AUTHORITY_CLIENT_ID_HINT_KEY,
        build_sales_one_plus_dynamic_suffix,
    )

    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        "classic",
        "price",
        "few_teeth",
        "both",
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    _, hints = build_pre_flash_prompt_hints(resolution=resolution, catalog_service_hint=None)
    assert hints.get("ambiguous_scope_hint") is True
    suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=resolution,
        current_strict_facts=(),
        sales_context={**hints, AUTHORITY_CLIENT_ID_HINT_KEY: "demo"},
        user_message="Сколько стоит?",
    )
    assert "ambiguous_scope_hint" in suffix
    assert "EXACT_SALES_RESOLUTION" not in suffix
    assert '"service_id": "classic"' not in suffix.split("resolution_hint", 1)[0]
    assert "<CLINIC_CONTACT_AUTHORITY>" in suffix
    assert "+7 (495) 128-47-60" in suffix
    assert "<PRE_MODEL_HINTS>" in suffix
    assert AUTHORITY_CLIENT_ID_HINT_KEY not in suffix


def test_dynamic_suffix_contact_block_separate_from_pre_model_hints() -> None:
    from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
    from core.sales_one_plus_protocol import (
        AUTHORITY_CLIENT_ID_HINT_KEY,
        build_sales_one_plus_dynamic_suffix,
    )

    unknown = ExactSalesFieldAuthority(authority="unknown", provenance="unknown")
    resolution = ExactSalesResolution(
        None,
        None,
        None,
        None,
        None,
        unknown,
        unknown,
        unknown,
        unknown,
        unknown,
    )
    suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=resolution,
        current_strict_facts=(),
        sales_context={AUTHORITY_CLIENT_ID_HINT_KEY: "nikadent"},
        user_message="Какой телефон филиала на Рябикова?",
    )
    assert suffix.index("<CLINIC_CONTACT_AUTHORITY>") < suffix.index("<PRE_MODEL_HINTS>")
    assert "900 444-69-97" in suffix or "+7 (900) 444-69-97" in suffix
    assert "+7 (495) 128-47-60" not in suffix
    assert '"amount"' not in suffix
    assert '"offer_id"' not in suffix


def test_production_policy_contact_authority_instructions() -> None:
    policy = SALES_ONE_PLUS_SYSTEM_POLICY.casefold()
    assert "clinic_contact_authority" in policy
    assert "do not invent contact fields" in policy
    assert "missing contact data alone does not require route=admin" in policy


def test_production_parser_accepts_valid_answer_envelope() -> None:
    envelope = parse_production_envelope_json(
        answer_envelope("Готовый ответ"),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    assert envelope.route == "ANSWER"
    assert envelope.patient_text == "Готовый ответ"


def test_production_parser_rejects_non_json() -> None:
    with pytest.raises(OneCallEnvelopeProtocolError, match="json_invalid"):
        parse_production_envelope_json(
            "hello",
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_production_parser_rejects_admin_with_patient_text() -> None:
    payload = production_envelope_template(
        route="ADMIN",
        patient_text="nope",
        clarify_axis=None,
        clarify_service_options=None,
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="patient_text_forbidden_for_admin"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_production_parser_accepts_admin_envelope() -> None:
    envelope = parse_production_envelope_json(
        admin_envelope(),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    assert envelope.route == "ADMIN"
