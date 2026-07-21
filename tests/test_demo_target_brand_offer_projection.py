from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from contracts.response_schema import TargetStrategyMatch
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_brand_offer_projection import project_target_service_brand_offers


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"


def _project(service_id: str, brand_id: str):
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    context = build_service_data_context(bundle, doctors, service_id)
    result = project_target_service_brand_offers(
        context,
        bundle.brands,
        bundle.strategy,
        TargetStrategyMatch(),
        selected_brand_id=brand_id,
    )
    return bundle, context, result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_nobel_preserves_exact_money_package_and_stages() -> None:
    _bundle, context, result = _project("all_on_4", "nobel_biocare")

    assert result.selected_brand_id == "nobel_biocare"
    assert result.brand.canonical_name == "Nobel Biocare"
    assert result.brand.country == "Швейцария"
    assert result.brand.aliases == ["nobel", "нобель", "нобел"]
    assert [offer.offer_id for offer in result.offers] == ["all_on_4.jaw.nobel"]
    nobel = result.offers[0]
    source = next(
        offer for offer in context.offers if offer.offer_id == "all_on_4.jaw.nobel"
    )
    assert nobel.model_dump() == source.model_dump()
    assert nobel is not source
    assert nobel.price.amount == 428_000  # type: ignore[union-attr]
    assert nobel.price.currency == "RUB"  # type: ignore[union-attr]
    assert nobel.price.billing_unit == "jaw"  # type: ignore[union-attr]
    assert [stage.amount for stage in nobel.payment_stages or []] == [256_800, 171_200]
    assert [followup.id for followup in nobel.followups] == ["stages", "includes"]


@pytest.mark.parametrize(
    ("brand_id", "offer_id", "amount"),
    [
        ("implantium", "all_on_4.jaw.implantium", 318_000),
        ("impro", "all_on_4.jaw.impro", 368_000),
    ],
)
def test_real_all_on_4_exact_brand_never_mixes_offers(
    brand_id: str, offer_id: str, amount: int
) -> None:
    _bundle, _context, result = _project("all_on_4", brand_id)

    assert [offer.offer_id for offer in result.offers] == [offer_id]
    assert result.offers[0].brand_id == brand_id
    assert result.offers[0].price.amount == amount  # type: ignore[union-attr]


def test_real_classic_nobel_returns_only_exact_one_tooth_offer() -> None:
    _bundle, _context, result = _project("classic", "nobel_biocare")

    assert [offer.offer_id for offer in result.offers] == [
        "classic.one_tooth.nobel"
    ]
    assert result.offers[0].price.amount == 101_200  # type: ignore[union-attr]
    assert result.offers[0].price.billing_unit == "tooth_package"  # type: ignore[union-attr]


def test_real_existing_brand_on_generic_service_is_empty_without_fallback() -> None:
    _bundle, context, result = _project("caries", "nobel_biocare")

    assert [offer.offer_id for offer in context.offers] == ["caries.default"]
    assert context.offers[0].brand_id is None
    assert result.offers == ()


def test_real_projection_is_read_only_and_has_no_product_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _project("all_on_4", "nobel_biocare")

    assert {path: _sha256(path) for path in paths} == before
    tree = ast.parse(
        Path("core/target_brand_offer_projection.py").read_text(encoding="utf-8")
    )
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert not any(
        module.startswith(
            ("app", "config", "handlers", "orchestration", "routes", "telegram")
        )
        for module in imported_modules
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
