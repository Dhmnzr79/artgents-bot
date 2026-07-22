from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path

import pytest

from contracts.response_schema import TargetStrategyMatch
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_brand_offer_projection import project_target_service_brand_offers
from core.target_brand_resolver import resolve_target_brand_term
from core.target_service_resolver import resolve_target_service_term


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"


def _bundle():
    return load_response_schema_bundle(TARGET_ROOT)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_all_real_authored_service_labels_resolve_to_their_exact_active_id() -> None:
    bundle = _bundle()
    checked = 0

    assert len(bundle.services) == 21
    assert all(service.active for service in bundle.services.values())
    for service_id, service in bundle.services.items():
        for term in (service_id, service.name, *service.aliases):
            resolution = resolve_target_service_term(bundle.services, term)
            assert resolution is not None
            assert resolution.service_id == service_id
            assert resolution.service.model_dump() == service.model_dump()
            assert resolution.service is not service
            checked += 1

    assert checked == 199


def test_real_catalog_has_no_normalized_cross_service_label_collisions() -> None:
    bundle = _bundle()
    owners: dict[str, list[str]] = defaultdict(list)

    for service_id, service in bundle.services.items():
        for label in (service_id, service.name, *service.aliases):
            normalized = label.strip().casefold()
            if service_id not in owners[normalized]:
                owners[normalized].append(service_id)

    assert sum(2 + len(service.aliases) for service in bundle.services.values()) == 199
    assert {label: ids for label, ids in owners.items() if len(ids) > 1} == {}


@pytest.mark.parametrize(
    ("term", "expected_id"),
    [
        ("  ALL-ON-4  ", "all_on_4"),
        ("\tВСЕ НА ЧЕТЫРЁХ\n", "all_on_4"),
        ("ПРОФЕССИОНАЛЬНОЕ ОТБЕЛИВАНИЕ", "professional_whitening"),
        ("КТ ЗУБОВ", "tomography"),
    ],
)
def test_real_case_and_outer_whitespace_resolve(
    term: str, expected_id: str
) -> None:
    resolution = resolve_target_service_term(_bundle().services, term)

    assert resolution is not None
    assert resolution.service_id == expected_id


@pytest.mark.parametrize(
    "term",
    [
        "расскажите пожалуйста про all-on-4",
        "all-on-4?",
        "all-on-",
        "всем на четырёх",
        "пульпитом",
        "неизвестная услуга",
    ],
)
def test_real_unknown_typo_morphology_and_containing_phrase_do_not_match(
    term: str,
) -> None:
    assert resolve_target_service_term(_bundle().services, term) is None


def test_real_authored_full_question_alias_matches_only_as_whole_string() -> None:
    services = _bundle().services
    exact = resolve_target_service_term(services, "сколько стоит all-on-4")
    containing = resolve_target_service_term(
        services, "подскажите сколько стоит all-on-4 пожалуйста"
    )

    assert exact is not None
    assert exact.service_id == "all_on_4"
    assert containing is None


def test_real_service_brand_offer_chain_preserves_nobel_money_and_stages() -> None:
    bundle = _bundle()
    service_resolution = resolve_target_service_term(bundle.services, "All-on-4")
    brand_resolution = resolve_target_brand_term(bundle.brands, "нобель")
    assert service_resolution is not None
    assert brand_resolution is not None

    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    context = build_service_data_context(
        bundle, doctors, service_resolution.service_id
    )
    projection = project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        TargetStrategyMatch(family="implantology", extent="full_arch"),
        selected_brand_id=brand_resolution.brand_id,
    )

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

    resolve_target_service_term(_bundle().services, "All-on-4")

    assert {path: _sha256(path) for path in paths} == before
