from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from contracts.response_schema import TargetStrategyMatch
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_brand_offer_projection import project_target_service_brand_offers
from core.target_brand_resolver import resolve_target_brand_term


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"


def _bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize(
    ("term", "expected_id", "expected_name", "expected_country"),
    [
        ("implantium", "implantium", "Implantium", "Южная Корея"),
        ("Implantium", "implantium", "Implantium", "Южная Корея"),
        ("имплантиум", "implantium", "Implantium", "Южная Корея"),
        ("impro", "impro", "Impro", "Германия"),
        ("Impro", "impro", "Impro", "Германия"),
        ("импро", "impro", "Impro", "Германия"),
        ("nobel_biocare", "nobel_biocare", "Nobel Biocare", "Швейцария"),
        ("Nobel Biocare", "nobel_biocare", "Nobel Biocare", "Швейцария"),
        ("nobel", "nobel_biocare", "Nobel Biocare", "Швейцария"),
        ("нобель", "nobel_biocare", "Nobel Biocare", "Швейцария"),
        ("нобел", "nobel_biocare", "Nobel Biocare", "Швейцария"),
        ("  НОБЕЛЬ  ", "nobel_biocare", "Nobel Biocare", "Швейцария"),
    ],
)
def test_real_brand_ids_canonical_names_and_aliases_resolve_exactly(
    term: str,
    expected_id: str,
    expected_name: str,
    expected_country: str,
) -> None:
    bundle = _bundle()
    result = resolve_target_brand_term(bundle.brands, term)

    assert result is not None
    assert result.brand_id == expected_id
    assert result.brand.canonical_name == expected_name
    assert result.brand.country == expected_country
    assert result.brand.model_dump() == bundle.brands.brands[
        expected_id
    ].model_dump()
    assert result.brand is not bundle.brands.brands[expected_id]


@pytest.mark.parametrize(
    "term",
    [
        "Straumann",
        "Nobe",
        "Нобелем",
        "Nobel!",
        "сколько стоит Nobel",
        "а у вас есть Nobel Biocare",
    ],
)
def test_real_unknown_typo_and_full_phrase_do_not_match(term: str) -> None:
    assert resolve_target_brand_term(_bundle().brands, term) is None


def test_real_resolution_composes_explicitly_with_s24_without_brand_mix() -> None:
    bundle = _bundle()
    resolution = resolve_target_brand_term(bundle.brands, "нобель")
    assert resolution is not None
    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    context = build_service_data_context(bundle, doctors, "all_on_4")

    projection = project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        TargetStrategyMatch(family="implantology", extent="full_arch"),
        selected_brand_id=resolution.brand_id,
    )

    assert projection.selected_brand_id == "nobel_biocare"
    assert [offer.offer_id for offer in projection.offers] == [
        "all_on_4.jaw.nobel"
    ]
    offer = projection.offers[0]
    assert offer.price.amount == 428_000  # type: ignore[union-attr]
    assert offer.price.currency == "RUB"  # type: ignore[union-attr]
    assert offer.price.billing_unit == "jaw"  # type: ignore[union-attr]
    assert [stage.amount for stage in offer.payment_stages or []] == [256_800, 171_200]


def test_real_resolution_is_read_only() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    resolve_target_brand_term(_bundle().brands, "Nobel")

    assert {path: _sha256(path) for path in paths} == before
