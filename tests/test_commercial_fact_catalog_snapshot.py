from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.response_schema_loader import load_response_schema_bundle

_DEMO_ROOT = Path("clients/demo/target_response")
_NIKADENT_ROOT = Path("clients/nikadent/target_response")
_ROW_KEYS = frozenset({"fact_id", "kind", "catalog_label", "active", "text_fact", "render_mode", "allowed_service_ids", "allowed_topics", "incompatible_with", "excluded_service_ids"})
_OPTIONAL_KEYS = ("active_from", "active_until", "detail_ref", "microfact_text", "excluded_scope_text", "requested_display_policy")


def _demo_bundle():
    return load_response_schema_bundle(_DEMO_ROOT)


def _nikadent_bundle():
    return load_response_schema_bundle(_NIKADENT_ROOT)


def test_snapshot_is_deterministic_for_demo() -> None:
    bundle = _demo_bundle()
    first = CommercialFactCatalogSnapshot.from_bundle(bundle)
    second = CommercialFactCatalogSnapshot.from_bundle(bundle)
    assert first.canonical_json == second.canonical_json
    assert first.fact_ids == second.fact_ids
    assert first.active_fact_ids == second.active_fact_ids


def test_rows_are_sorted_by_fact_id() -> None:
    snapshot = CommercialFactCatalogSnapshot.from_bundle(_demo_bundle())
    payload = json.loads(snapshot.canonical_json)
    fact_ids = [row["fact_id"] for row in payload["facts"]]
    assert fact_ids == sorted(fact_ids)


def test_row_key_closure_is_exact() -> None:
    snapshot = CommercialFactCatalogSnapshot.from_bundle(_demo_bundle())
    payload = json.loads(snapshot.canonical_json)
    for row in payload["facts"]:
        fact = _demo_bundle().facts[row["fact_id"]]
        assert set(row.keys()) == _ROW_KEYS | {key for key in _OPTIONAL_KEYS if getattr(fact, key) is not None}


def test_fact_and_active_id_sets_match_bundle() -> None:
    bundle = _demo_bundle()
    snapshot = CommercialFactCatalogSnapshot.from_bundle(bundle)
    assert snapshot.fact_ids == frozenset(bundle.facts)
    assert snapshot.active_fact_ids == frozenset(
        fact_id for fact_id, fact in bundle.facts.items() if fact.active
    )


def test_demo_and_nikadent_snapshots_are_isolated() -> None:
    demo = CommercialFactCatalogSnapshot.from_bundle(_demo_bundle())
    nikadent = CommercialFactCatalogSnapshot.from_bundle(_nikadent_bundle())
    assert demo.fact_ids != nikadent.fact_ids
    assert "free_implant_consult" in demo.fact_ids
    assert "free_implant_consult" not in nikadent.fact_ids
    assert "free_orthopedic_consult" in nikadent.fact_ids
    assert "free_orthopedic_consult" not in demo.fact_ids


def test_from_bundle_does_not_mutate_bundle() -> None:
    bundle = _demo_bundle()
    before = deepcopy(bundle.model_dump())
    CommercialFactCatalogSnapshot.from_bundle(bundle)
    assert bundle.model_dump() == before


def test_block_text_uses_exact_header() -> None:
    snapshot = CommercialFactCatalogSnapshot.from_bundle(_demo_bundle())
    assert snapshot.block_text().startswith("=== COMMERCIAL_FACT_CATALOG ===\n")


def test_full_values_are_preserved_without_offer_or_service_rows() -> None:
    bundle = _demo_bundle()
    payload = json.loads(CommercialFactCatalogSnapshot.from_bundle(bundle).canonical_json)
    assert set(payload) == {"facts"}
    for row in payload["facts"]:
        fact = bundle.facts[row["fact_id"]]
        expected = fact.model_dump(mode="json", exclude_none=True)
        expected["fact_id"] = expected.pop("id")
        for key in ("allowed_service_ids", "allowed_topics", "incompatible_with", "excluded_service_ids"):
            expected[key] = sorted(expected[key])
        assert row == expected


def test_captured_text_does_not_follow_later_bundle_mutation() -> None:
    bundle = _demo_bundle()
    snapshot = CommercialFactCatalogSnapshot.from_bundle(bundle)
    original = snapshot.canonical_json
    bundle.facts["free_implant_consult"].text_fact = "Changed after capture."
    assert snapshot.canonical_json == original
    assert CommercialFactCatalogSnapshot.from_bundle(bundle).canonical_json != original
