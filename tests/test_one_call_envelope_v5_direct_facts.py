"""Production v5 envelope direct_fact_ids contract tests (Checkpoint B1)."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from contracts.one_call_envelope import (
    OneCallEnvelope,
    OneCallEnvelopeReferences,
    required_envelope_field_names,
    required_reference_field_names,
)
from core.one_call_envelope_protocol import (
    MAX_ENVELOPE_UTF8_BYTES,
    OneCallEnvelopeProtocolError,
    dumps_production_envelope,
    parse_production_envelope_json,
    production_envelope_template,
)
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.one_call_prefix_cache import clear_one_call_prefix_cache, get_or_build_stable_prefix
from core.one_call_prefix_input_fingerprint import compute_prefix_input_fingerprint
from core import turn_timing
from core.target_client_data import load_target_client_data
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_EXACT_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_EXACT_CATALOG,
    _EMPTY_REF_CATALOG,
    _PACK_IDENTITY,
    _context,
    answer_envelope,
)


_NIKADENT_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot.from_bundle(
    load_target_client_data("nikadent").bundle
)
_NIKADENT_EXACT_CATALOG = ExactCommercialCatalogSnapshot.from_bundle(
    load_target_client_data("nikadent").bundle
)


def _normalization_codes_from_turn_timing() -> tuple[str, ...]:
    stored = turn_timing.summary_for_turn_complete().get("envelope_input_normalizations")
    if isinstance(stored, list):
        return tuple(str(code) for code in stored)
    return ()


def _parse_envelope_in_request_context(raw: str) -> OneCallEnvelope:
    import app as app_module

    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        return parse_production_envelope_json(
            raw,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_exact_fifteen_key_top_level_closure() -> None:
    assert len(required_envelope_field_names()) == 15
    assert required_envelope_field_names() == frozenset(production_envelope_template().keys())
    assert "references" in required_envelope_field_names()


def test_references_exactly_one_required_sub_key() -> None:
    assert required_reference_field_names() == frozenset({"direct_fact_ids"})


@pytest.mark.parametrize(
    "mutator,code",
    (
        (lambda payload: payload.pop("route"), "missing_fields"),
    ),
)
def test_missing_top_level_field_rejected(mutator, code: str) -> None:
    payload = production_envelope_template()
    mutator(payload)
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_extra_top_level_field_is_normalized() -> None:
    from contracts.one_call_envelope import ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS

    import app as app_module

    payload = production_envelope_template(patient_text="Ответ с лишним полем.")
    payload["extra"] = {"ignored": True}
    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        envelope = parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert envelope.patient_text == "Ответ с лишним полем."
        assert ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS in _normalization_codes_from_turn_timing()


@pytest.mark.parametrize(
    "references,code",
    (
        (None, "references_invalid"),
        ([], "references_invalid"),
        ("x", "references_invalid"),
    ),
)
def test_references_type_rejected(references: object, code: str) -> None:
    payload = production_envelope_template(references=references)
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_missing_nested_direct_fact_ids_rejected() -> None:
    payload = production_envelope_template(references={})
    with pytest.raises(OneCallEnvelopeProtocolError, match="missing_reference_fields"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_unknown_nested_reference_field_rejected() -> None:
    payload = production_envelope_template(
        references={"direct_fact_ids": [], "brand_ids": []},
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="unknown_reference_fields"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


@pytest.mark.parametrize("value", (None, True, "x", {}))
def test_direct_fact_ids_invalid_shape(value: object) -> None:
    payload = production_envelope_template(references={"direct_fact_ids": value})
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_invalid"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


@pytest.mark.parametrize("items", ([" "], [True], [""], ["installment_12", 17], ["installment_12", None]))
def test_direct_fact_ids_item_rejected(items: list[object]) -> None:
    payload = production_envelope_template(references={"direct_fact_ids": items})
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_invalid"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_direct_fact_ids_duplicate_is_normalized() -> None:
    from contracts.one_call_envelope import ENVELOPE_NORMALIZED_DIRECT_FACT_ID_DEDUPED

    import app as app_module

    payload = production_envelope_template(
        patient_text="Ответ с дублем.",
        references={"direct_fact_ids": ["fact_a", "fact_a"]},
    )
    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        envelope = parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )
        assert envelope.patient_text == "Ответ с дублем."
        assert envelope.references.direct_fact_ids == ("fact_a",)
        assert ENVELOPE_NORMALIZED_DIRECT_FACT_ID_DEDUPED in _normalization_codes_from_turn_timing()


def test_empty_direct_fact_ids_accepted() -> None:
    envelope = parse_production_envelope_json(
        answer_envelope("Ответ."),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    assert envelope.references.direct_fact_ids == ()


def test_unknown_current_pack_id_parses_and_preserves_id() -> None:
    payload = production_envelope_template(
        patient_text="Ответ.",
        references={"direct_fact_ids": ["missing_fact_id"]},
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.patient_text == "Ответ."
    assert envelope.references.direct_fact_ids == ("missing_fact_id",)


def test_demo_only_id_under_nikadent_parses_without_rewriting() -> None:
    payload = production_envelope_template(
        patient_text="Про рассрочку.",
        references={"direct_fact_ids": ["installment_12"]},
    )
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_NIKADENT_COMMERCIAL_CATALOG,
    )
    assert envelope.patient_text == "Про рассрочку."
    assert envelope.references.direct_fact_ids == ("installment_12",)
    dumped = envelope.model_dump()
    assert dumped["references"]["direct_fact_ids"] == ("installment_12",)
    assert "text_fact" not in dumped


@pytest.mark.parametrize("route", ("CLARIFY", "ADMIN"))
def test_non_answer_routes_forbid_non_empty_direct_ids(route: str) -> None:
    overrides: dict[str, object] = {
        "route": route,
        "references": {"direct_fact_ids": ["installment_12"]},
    }
    if route == "CLARIFY":
        overrides.update(
            patient_text="Уточните.",
            clarify_axis="extent",
            clarify_service_options=None,
        )
    else:
        overrides.update(patient_text=None, clarify_axis=None, clarify_service_options=None)
    payload = production_envelope_template(**overrides)
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_forbidden_for_route"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_envelope_size_limit_unchanged() -> None:
    huge = "x" * (MAX_ENVELOPE_UTF8_BYTES + 1)
    payload = answer_envelope(huge)
    with pytest.raises(OneCallEnvelopeProtocolError, match="envelope_oversized"):
        parse_production_envelope_json(
            payload,
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_prompt_contract_version_is_six() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 8


def test_prefix_contains_exact_commercial_catalog_with_full_fields() -> None:
    clear_one_call_prefix_cache()
    bundle, _hit = get_or_build_stable_prefix(
        identity=_PACK_IDENTITY,
        cached_full_context=_context(),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        exact_commercial_catalog=_DEMO_EXACT_CATALOG,
    )
    assert "=== EXACT_COMMERCIAL_CATALOG ===" in bundle.stable_prefix
    assert "=== COMMERCIAL_FACT_CATALOG ===" not in bundle.stable_prefix
    assert "installment_12" in bundle.stable_prefix
    assert "text_fact" in bundle.stable_prefix
    assert "all_on_4.jaw.nobel" in bundle.stable_prefix
    assert "billing_unit" in bundle.stable_prefix
    catalog_block = bundle.stable_prefix.split("=== EXACT_COMMERCIAL_CATALOG ===", 1)[1].split(
        "=== APPROVED_MD_CORPUS ===", 1
    )[0]
    assert "428000" in catalog_block


def test_exact_catalog_mutation_changes_fingerprint() -> None:
    corpus = _context()
    fp_a = compute_prefix_input_fingerprint(
        _PACK_IDENTITY,
        corpus,
        _DEMO_CATALOG,
        _DEMO_REF_CATALOG,
        _DEMO_EXACT_CATALOG,
    )
    mutated = ExactCommercialCatalogSnapshot(
        canonical_json='{"facts":[],"offers":[{"offer_id":"x","service_id":"classic","active":true,"price":{"mode":"fixed","amount":1,"currency":"RUB","billing_unit":"tooth"},"package":{"label":"x","includes":[]},"payment_stages":[],"fact_refs":[]}],"services":[]}',
        offer_ids=frozenset({"x"}),
    )
    fp_b = compute_prefix_input_fingerprint(
        _PACK_IDENTITY,
        corpus,
        _DEMO_CATALOG,
        _DEMO_REF_CATALOG,
        mutated,
    )
    assert fp_a != fp_b


def test_production_envelope_helper_default_empty_references() -> None:
    payload = production_envelope_template()
    assert payload["references"] == {"direct_fact_ids": []}
    parsed = json.loads(dumps_production_envelope())
    assert parsed["references"] == {"direct_fact_ids": []}


def test_valid_answer_envelope_parses_direct_ids_in_order() -> None:
    envelope = parse_production_envelope_json(
        dumps_production_envelope(
            patient_text="Условия ниже.",
            commercial_intent="payment",
            references={"direct_fact_ids": ["installment_12", "tax_deduction"]},
        ),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.references.direct_fact_ids == ("installment_12", "tax_deduction")


def test_one_call_envelope_direct_construction_requires_references() -> None:
    with pytest.raises(Exception):
        OneCallEnvelope(
            route="ANSWER",
            service_id=None,
            extent=None,
            jaw=None,
            stage=None,
            scenario="none",
            commercial_intent="none",
            promotion_scope="none",
            clarify_axis=None,
            clarify_service_options=None,
            patient_text="x",
            service_reference_status="none",
            requested_service_id=None,
        )
    env = OneCallEnvelope(
        route="ANSWER",
        service_id=None,
        extent=None,
        jaw=None,
        stage=None,
        scenario="none",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis=None,
        clarify_service_options=None,
        patient_text="x",
        service_reference_status="none",
        requested_service_id=None,
        references=OneCallEnvelopeReferences(direct_fact_ids=()),
    )
    assert env.references.direct_fact_ids == ()


@pytest.mark.parametrize(
    "direct_fact_ids",
    (
        pytest.param([True], id="bool"),
        pytest.param([123], id="int"),
        pytest.param([" "], id="blank"),
        pytest.param(["x", "x"], id="duplicate"),
    ),
)
def test_one_call_envelope_references_rejects_invalid_direct_ids(
    direct_fact_ids: list[object],
) -> None:
    with pytest.raises(ValidationError):
        OneCallEnvelopeReferences(direct_fact_ids=direct_fact_ids)  # type: ignore[arg-type]


def test_one_call_envelope_references_strips_and_preserves_order() -> None:
    refs = OneCallEnvelopeReferences(direct_fact_ids=[" x ", "y"])
    assert refs.direct_fact_ids == ("x", "y")


def test_envelope_normalization_diagnostics_are_request_local() -> None:
    from contracts.one_call_envelope import ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS

    import app as app_module

    clean_payload = production_envelope_template(patient_text="Чистый ответ.")
    noisy_payload = production_envelope_template(patient_text="Ответ с лишним полем.")
    noisy_payload["extra"] = {"ignored": True}
    invalid_payload = production_envelope_template(
        references={"direct_fact_ids": ["installment_12", 17]},
    )

    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        parse_production_envelope_json(
            json.dumps(noisy_payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS in _normalization_codes_from_turn_timing()

        request.ctx = {"turn_t0_monotonic": 0.0}
        parse_production_envelope_json(
            json.dumps(clean_payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert _normalization_codes_from_turn_timing() == ()

        request.ctx = {"turn_t0_monotonic": 0.0}
        parse_production_envelope_json(
            json.dumps(noisy_payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_invalid"):
            parse_production_envelope_json(
                json.dumps(invalid_payload),
                active_service_catalog=_EMPTY_CATALOG,
                service_reference_catalog=_EMPTY_REF_CATALOG,
                commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
            )
        assert _normalization_codes_from_turn_timing() == ()


def test_envelope_normalization_diagnostics_do_not_leak_across_request_contexts() -> None:
    from contracts.one_call_envelope import ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS

    import app as app_module

    payload = production_envelope_template(patient_text="Ответ с лишним полем.")
    payload["extra"] = {"ignored": True}

    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS in _normalization_codes_from_turn_timing()

    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        clean = production_envelope_template(patient_text="Чистый ответ.")
        parse_production_envelope_json(
            json.dumps(clean),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert _normalization_codes_from_turn_timing() == ()


def test_envelope_normalization_cleared_before_early_parse_failures() -> None:
    from contracts.one_call_envelope import ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS

    import app as app_module

    noisy_payload = production_envelope_template(patient_text="Ответ с лишним полем.")
    noisy_payload["extra"] = {"ignored": True}
    clean_payload = production_envelope_template(patient_text="Чистый ответ.")
    oversized = "x" * (MAX_ENVELOPE_UTF8_BYTES + 1)

    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        parse_production_envelope_json(
            json.dumps(noisy_payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert ENVELOPE_NORMALIZED_UNKNOWN_TOP_LEVEL_FIELDS in _normalization_codes_from_turn_timing()

        with pytest.raises(OneCallEnvelopeProtocolError, match="envelope_output_invalid"):
            parse_production_envelope_json(
                None,
                active_service_catalog=_EMPTY_CATALOG,
                service_reference_catalog=_EMPTY_REF_CATALOG,
                commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
            )
        assert _normalization_codes_from_turn_timing() == ()

        with pytest.raises(OneCallEnvelopeProtocolError, match="envelope_empty"):
            parse_production_envelope_json(
                "   ",
                active_service_catalog=_EMPTY_CATALOG,
                service_reference_catalog=_EMPTY_REF_CATALOG,
                commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
            )
        assert _normalization_codes_from_turn_timing() == ()

        with pytest.raises(OneCallEnvelopeProtocolError, match="envelope_oversized"):
            parse_production_envelope_json(
                oversized,
                active_service_catalog=_EMPTY_CATALOG,
                service_reference_catalog=_EMPTY_REF_CATALOG,
                commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
            )
        assert _normalization_codes_from_turn_timing() == ()

        with pytest.raises(OneCallEnvelopeProtocolError, match="json_invalid"):
            parse_production_envelope_json(
                "{not-json",
                active_service_catalog=_EMPTY_CATALOG,
                service_reference_catalog=_EMPTY_REF_CATALOG,
                commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
            )
        assert _normalization_codes_from_turn_timing() == ()

        parse_production_envelope_json(
            json.dumps(clean_payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )
        assert _normalization_codes_from_turn_timing() == ()
