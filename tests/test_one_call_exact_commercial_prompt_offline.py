"""CP-EXACT-1A offline acceptance: exact commercial catalog prompt wiring."""

from __future__ import annotations

import json
import shutil
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

import app as app_module
from core.one_call_exact_commercial_catalog import (
    COMMERCIAL_AS_OF_HEADER,
    COMMERCIAL_AS_OF_UNAVAILABLE,
    ExactCommercialCatalogSnapshot,
    build_commercial_as_of_block,
)
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.one_call_prefix_cache import clear_one_call_prefix_cache, get_or_build_stable_prefix
from core.one_call_prefix_input_fingerprint import (
    compute_prefix_input_fingerprint,
    prefix_cache_lookup_key,
)
from core.one_call_prompt_contract import ONE_CALL_PROMPT_CONTRACT_VERSION
from core.response_schema_loader import load_response_schema_bundle
from core.sales_one_plus_protocol import build_sales_one_plus_dynamic_suffix
from core.target_cached_full_context import build_target_cached_full_context
from core.target_client_data import load_target_client_data
from tests.test_sales_one_plus_turn import (
    _DEMO_EXACT_CATALOG,
    _DEMO_PACK_IDENTITY,
    _EMPTY_EXACT_CATALOG,
    _PACK_IDENTITY,
    _context,
    _resolution,
)
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.one_call_client_pack_identity import build_client_pack_identity
from core import turn_timing

_DEMO_ROOT = Path("clients/demo/target_response")
_NIKADENT_ROOT = Path("clients/nikadent/target_response")


def _demo_bundle():
    return load_response_schema_bundle(_DEMO_ROOT)


def _demo_catalogs():
    bundle = _demo_bundle()
    return (
        ActiveServiceCatalogSnapshot.from_bundle(bundle),
        ServiceReferenceCatalogSnapshot.from_bundle(bundle),
        ExactCommercialCatalogSnapshot.from_bundle(bundle),
    )


def test_demo_exact_catalog_counts_from_real_bundle() -> None:
    snapshot = ExactCommercialCatalogSnapshot.from_bundle(_demo_bundle())
    payload = json.loads(snapshot.canonical_json)
    assert len(payload["facts"]) == 10
    assert len(payload["offers"]) == 32
    assert len(payload["services"]) == 22
    assert sum(1 for offer in payload["offers"] if offer.get("payment_stages")) == 12
    bone_graft = next(row for row in payload["offers"] if row["offer_id"] == "bone_graft.default")
    assert bone_graft["price"]["mode"] == "no_public_price"
    assert bone_graft["price"]["approved_text"]


def test_demo_exact_catalog_block_size_is_substantial() -> None:
    snapshot = ExactCommercialCatalogSnapshot.from_bundle(_demo_bundle())
    block = snapshot.block_text()
    assert block.startswith("=== EXACT_COMMERCIAL_CATALOG ===\n")
    assert len(block.encode("utf-8")) > 30_000


def test_assembled_prefix_contains_full_exact_catalog_only_once() -> None:
    clear_one_call_prefix_cache()
    active, ref, exact = _demo_catalogs()
    corpus = build_target_cached_full_context(Path("clients/demo/md"))
    prefix = build_one_call_stable_prefix(
        identity=_DEMO_PACK_IDENTITY,
        cached_full_context=corpus,
        active_service_catalog=active,
        service_reference_catalog=ref,
        exact_commercial_catalog=exact,
    )
    assert prefix.count("=== EXACT_COMMERCIAL_CATALOG ===") == 1
    assert "=== COMMERCIAL_FACT_CATALOG ===" not in prefix
    assert "billing_unit" in prefix
    assert "package" in prefix
    assert "payment_stages" in prefix
    assert "professional_whitening_discount" in prefix


def test_commercial_as_of_only_in_dynamic_suffix() -> None:
    active, ref, exact = _demo_catalogs()
    suffix = build_sales_one_plus_dynamic_suffix(
        exact_sales_resolution=_resolution(),
        current_strict_facts=(),
        sales_context={},
        user_message="Сколько стоит All-on-4?",
        exact_commercial_catalog=exact,
        as_of_date=date(2026, 8, 29),
    )
    assert COMMERCIAL_AS_OF_HEADER in suffix
    assert "=== EXACT_COMMERCIAL_CATALOG ===" not in suffix
    prefix = build_one_call_stable_prefix(
        identity=_DEMO_PACK_IDENTITY,
        cached_full_context=_context(),
        active_service_catalog=active,
        service_reference_catalog=ref,
        exact_commercial_catalog=exact,
    )
    assert COMMERCIAL_AS_OF_HEADER not in prefix


@pytest.mark.parametrize(
    ("as_of", "eligible"),
    (
        (date(2026, 11, 30), True),
        (date(2026, 12, 1), False),
    ),
)
def test_whitening_discount_date_eligibility(as_of: date, eligible: bool) -> None:
    exact = ExactCommercialCatalogSnapshot.from_bundle(_demo_bundle())
    fact_ids = exact.date_eligible_fact_ids(as_of)
    assert ("professional_whitening_discount" in fact_ids) is eligible


def test_implant_warranty_not_in_demo_automatic_amplifiers() -> None:
    bundle = _demo_bundle()
    ordered = [str(ref) for ref in bundle.marketing.ordered_amplifier_refs]
    assert "fact:implant_warranty" not in ordered


def test_demo_and_nikadent_prefix_catalogs_are_isolated() -> None:
    demo_exact = ExactCommercialCatalogSnapshot.from_bundle(_demo_bundle())
    nikadent_exact = ExactCommercialCatalogSnapshot.from_bundle(
        load_response_schema_bundle(_NIKADENT_ROOT)
    )
    assert demo_exact.canonical_json != nikadent_exact.canonical_json
    assert "free_implant_consult" in demo_exact.fact_ids
    assert "free_implant_consult" not in nikadent_exact.fact_ids
    assert "free_orthopedic_consult" in nikadent_exact.fact_ids
    assert "free_orthopedic_consult" not in demo_exact.fact_ids


def test_fingerprint_is_deterministic_and_client_scoped() -> None:
    corpus = _context()
    active, ref, exact = _demo_catalogs()
    fp1 = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
    fp2 = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
    assert fp1 == fp2
    nika_identity = build_client_pack_identity("nikadent")
    nika_exact = ExactCommercialCatalogSnapshot.from_bundle(
        load_response_schema_bundle(_NIKADENT_ROOT)
    )
    nika_active = ActiveServiceCatalogSnapshot.from_bundle(
        load_response_schema_bundle(_NIKADENT_ROOT)
    )
    nika_ref = ServiceReferenceCatalogSnapshot.from_bundle(
        load_response_schema_bundle(_NIKADENT_ROOT)
    )
    fp_nika = compute_prefix_input_fingerprint(nika_identity, corpus, nika_active, nika_ref, nika_exact)
    assert fp1 != fp_nika


def test_as_of_date_does_not_change_stable_fingerprint() -> None:
    corpus = _context()
    active, ref, exact = _demo_catalogs()
    fp_a = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
    _ = build_commercial_as_of_block(exact, as_of_date=date(2026, 8, 29))
    _ = build_commercial_as_of_block(exact, as_of_date=date(2027, 1, 1))
    fp_b = compute_prefix_input_fingerprint(_PACK_IDENTITY, corpus, active, ref, exact)
    assert fp_a == fp_b


def test_exact_commercial_price_change_updates_fingerprint_and_cache_key(
    tmp_path: Path,
) -> None:
    corpus = build_target_cached_full_context(Path("clients/demo/md"))
    active, ref, exact_original = _demo_catalogs()
    fp_original = compute_prefix_input_fingerprint(
        _PACK_IDENTITY, corpus, active, ref, exact_original
    )
    key_original = prefix_cache_lookup_key(
        _PACK_IDENTITY, corpus, active, ref, exact_original
    )

    isolated_root = tmp_path / "target_response"
    shutil.copytree(_DEMO_ROOT, isolated_root)
    offer_path = isolated_root / "pricebook/services/all_on_4.jaw.implantium.json"
    offer = json.loads(offer_path.read_text(encoding="utf-8"))
    assert offer["price"]["amount"] == 318000
    offer["price"]["amount"] = 319001
    offer_path.write_text(json.dumps(offer, ensure_ascii=False, indent=2), encoding="utf-8")

    modified_bundle = load_response_schema_bundle(isolated_root)
    exact_modified = ExactCommercialCatalogSnapshot.from_bundle(modified_bundle)
    active_modified = ActiveServiceCatalogSnapshot.from_bundle(modified_bundle)
    ref_modified = ServiceReferenceCatalogSnapshot.from_bundle(modified_bundle)

    assert exact_modified.canonical_json != exact_original.canonical_json
    assert "319001" in exact_modified.canonical_json
    assert "319001" not in exact_original.canonical_json

    fp_modified = compute_prefix_input_fingerprint(
        _PACK_IDENTITY, corpus, active_modified, ref_modified, exact_modified
    )
    key_modified = prefix_cache_lookup_key(
        _PACK_IDENTITY, corpus, active_modified, ref_modified, exact_modified
    )
    assert fp_modified != fp_original
    assert key_modified != key_original

    _ = build_commercial_as_of_block(exact_modified, as_of_date=date(2027, 1, 1))
    fp_after_as_of = compute_prefix_input_fingerprint(
        _PACK_IDENTITY, corpus, active_modified, ref_modified, exact_modified
    )
    assert fp_after_as_of == fp_modified


def test_commercial_as_of_unavailable_preserves_composer_invocation() -> None:
    from core.sales_one_plus_turn import run_sales_one_plus_candidate
    from tests.test_sales_one_plus_turn import _Backend, answer_envelope

    backend = _Backend(answer_envelope("Ответ без ADMIN."))
    with app_module.app.test_request_context("/ask", method="POST"):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        with patch(
            "core.one_call_exact_commercial_catalog.ExactCommercialCatalogSnapshot.date_eligible_fact_ids",
            side_effect=RuntimeError("forced optional failure"),
        ):
            result = run_sales_one_plus_candidate(
                user_message="Сколько стоит имплант?",
                cached_full_context=_context(),
                exact_sales_resolution=_resolution(),
                static_admin_handoff_text="Позвоните администратору.",
                backend=backend,
                pack_identity=_PACK_IDENTITY,
                active_service_catalog=ActiveServiceCatalogSnapshot(
                    canonical_json='{"services":[],"allowed_patient_stages":[]}'
                ),
                service_reference_catalog=ServiceReferenceCatalogSnapshot(
                    canonical_json='{"services":[]}'
                ),
                exact_commercial_catalog=_DEMO_EXACT_CATALOG,
                as_of_date=date(2026, 8, 29),
            )
        diagnostics = turn_timing.summary_for_turn_complete().get("commercial_as_of_diagnostics")
        assert isinstance(diagnostics, list)
        assert COMMERCIAL_AS_OF_UNAVAILABLE in diagnostics
        assert '"availability":"unavailable"' in backend.invocation.user_prompt
    assert result.decision == "answer"
    assert result.patient_text == "Ответ без ADMIN."
    assert COMMERCIAL_AS_OF_HEADER in backend.invocation.user_prompt


def test_get_or_build_stable_prefix_uses_exact_catalog_from_demo_bundle() -> None:
    clear_one_call_prefix_cache()
    active, ref, exact = _demo_catalogs()
    corpus = build_target_cached_full_context(Path("clients/demo/md"))
    bundle, hit = get_or_build_stable_prefix(
        identity=_DEMO_PACK_IDENTITY,
        cached_full_context=corpus,
        active_service_catalog=active,
        service_reference_catalog=ref,
        exact_commercial_catalog=exact,
    )
    assert hit is False
    assert "=== EXACT_COMMERCIAL_CATALOG ===" in bundle.stable_prefix
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 9
