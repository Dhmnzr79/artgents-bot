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
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.one_call_prefix_cache import clear_one_call_prefix_cache, get_or_build_stable_prefix
from core.one_call_prefix_input_fingerprint import compute_prefix_input_fingerprint
from core.target_client_data import load_target_client_data
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_REF_CATALOG,
    _PACK_IDENTITY,
    _context,
    answer_envelope,
)


_NIKADENT_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot.from_bundle(
    load_target_client_data("nikadent").bundle
)


def test_exact_fourteen_key_top_level_closure() -> None:
    assert len(required_envelope_field_names()) == 14
    assert required_envelope_field_names() == frozenset(production_envelope_template().keys())
    assert "references" in required_envelope_field_names()


def test_references_exactly_one_required_sub_key() -> None:
    assert required_reference_field_names() == frozenset({"direct_fact_ids"})


@pytest.mark.parametrize(
    "mutator,code",
    (
        (lambda payload: payload.pop("route"), "missing_fields"),
        (lambda payload: payload.update(extra="x"), "unknown_fields"),
    ),
)
def test_missing_and_extra_top_level_rejected(mutator, code: str) -> None:
    payload = production_envelope_template()
    mutator(payload)
    with pytest.raises(OneCallEnvelopeProtocolError, match=code):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


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


@pytest.mark.parametrize("items", ([" "], [True], [""], ["a", "a"]))
def test_direct_fact_ids_item_and_duplicate_rejected(items: list[object]) -> None:
    payload = production_envelope_template(references={"direct_fact_ids": items})
    pattern = "direct_fact_id_duplicate" if items == ["a", "a"] else "direct_fact_ids_invalid"
    with pytest.raises(OneCallEnvelopeProtocolError, match=pattern):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_empty_direct_fact_ids_accepted() -> None:
    envelope = parse_production_envelope_json(
        answer_envelope("Ответ."),
        active_service_catalog=_EMPTY_CATALOG,
        service_reference_catalog=_EMPTY_REF_CATALOG,
        commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
    )
    assert envelope.references.direct_fact_ids == ()


def test_unknown_current_pack_id_rejected() -> None:
    payload = production_envelope_template(
        references={"direct_fact_ids": ["missing_fact_id"]},
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_id_not_in_current_pack"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_demo_only_id_under_nikadent_uses_same_error_code() -> None:
    payload = production_envelope_template(
        references={"direct_fact_ids": ["installment_12"]},
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_id_not_in_current_pack"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_NIKADENT_COMMERCIAL_CATALOG,
        )


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


def test_prompt_contract_version_is_five() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 5


def test_prefix_contains_commercial_fact_catalog_without_text_fact() -> None:
    clear_one_call_prefix_cache()
    bundle, _hit = get_or_build_stable_prefix(
        identity=_PACK_IDENTITY,
        cached_full_context=_context(),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert "=== COMMERCIAL_FACT_CATALOG ===" in bundle.stable_prefix
    assert "installment_12" in bundle.stable_prefix
    assert "catalog_label" in bundle.stable_prefix
    assert "text_fact" not in bundle.stable_prefix.split("=== COMMERCIAL_FACT_CATALOG ===", 1)[1].split(
        "=== APPROVED_MD_CORPUS ===", 1
    )[0]


def test_commercial_catalog_mutation_changes_fingerprint() -> None:
    corpus = _context()
    fp_a = compute_prefix_input_fingerprint(
        _PACK_IDENTITY,
        corpus,
        _DEMO_CATALOG,
        _DEMO_REF_CATALOG,
        _DEMO_COMMERCIAL_CATALOG,
    )
    mutated = CommercialFactCatalogSnapshot(
        canonical_json='{"facts":[{"fact_id":"x","kind":"promo","catalog_label":"x","active":true}]}',
        fact_ids=frozenset({"x"}),
        active_fact_ids=frozenset({"x"}),
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
