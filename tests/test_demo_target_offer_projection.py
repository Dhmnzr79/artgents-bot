from __future__ import annotations

import ast
import hashlib
from pathlib import Path

import pytest

from contracts.response_schema import TargetStrategyMatch
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_loader import load_response_schema_bundle
from core.service_data_context import build_service_data_context
from core.target_offer_projection import project_target_service_offers


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
DOCTOR_CATALOG_PATH = DEMO_ROOT / "doctor_catalog.json"


def _real_inputs(service_id: str):
    bundle = load_response_schema_bundle(TARGET_ROOT)
    doctors = load_doctor_catalog(DOCTOR_CATALOG_PATH)
    context = build_service_data_context(bundle, doctors, service_id)
    return bundle, context


def _project(
    service_id: str,
    strategy_context: TargetStrategyMatch,
    **kwargs: object,
):
    bundle, context = _real_inputs(service_id)
    result = project_target_service_offers(
        context,
        bundle.strategy,
        strategy_context,
        **kwargs,  # type: ignore[arg-type]
    )
    return bundle, context, result


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_real_all_on_4_uses_offer_priority_and_preserves_exact_prices() -> None:
    _bundle, context, result = _project(
        "all_on_4",
        TargetStrategyMatch(family="implantology", extent="full_arch"),
    )

    assert result.matched_rule_id == "full_arch_restore"
    assert result.max_options == 3
    assert [offer.offer_id for offer in result.offers] == [
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.nobel",
    ]
    assert [offer.price.amount for offer in result.offers] == [  # type: ignore[union-attr]
        368_000,
        318_000,
        428_000,
    ]
    assert all(
        offer.price.currency == "RUB"  # type: ignore[union-attr]
        and offer.price.billing_unit == "jaw"  # type: ignore[union-attr]
        for offer in result.offers
    )
    assert [offer.offer_id for offer in context.offers] == [
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
    ]


def test_real_explicit_nobel_is_pinned_without_changing_package_or_stages() -> None:
    _bundle, context, result = _project(
        "all_on_4",
        TargetStrategyMatch(extent="full_arch"),
        explicit_offer_id="all_on_4.jaw.nobel",
    )

    assert [offer.offer_id for offer in result.offers] == [
        "all_on_4.jaw.nobel",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.implantium",
    ]
    nobel = result.offers[0]
    source_nobel = next(
        offer for offer in context.offers if offer.offer_id == "all_on_4.jaw.nobel"
    )
    assert nobel.model_dump() == source_nobel.model_dump()
    assert nobel is not source_nobel
    assert nobel.price.amount == 428_000  # type: ignore[union-attr]
    assert [stage.amount for stage in nobel.payment_stages or []] == [256_800, 171_200]
    assert [stage.currency for stage in nobel.payment_stages or []] == ["RUB", "RUB"]
    assert [followup.id for followup in nobel.followups] == ["stages", "includes"]


@pytest.mark.parametrize(
    ("option_id", "extent", "expected_offer", "expected_amount"),
    [
        ("partial", "few_teeth", "removable_dentures.jaw.partial", 45_000),
        ("full", "full_arch", "removable_dentures.jaw.full", 65_000),
    ],
)
def test_real_removable_denture_options_never_mix(
    option_id: str,
    extent: str,
    expected_offer: str,
    expected_amount: int,
) -> None:
    _bundle, _context, result = _project(
        "removable_dentures",
        TargetStrategyMatch(extent=extent),  # type: ignore[arg-type]
        selected_option_id=option_id,
    )

    assert result.selected_option_id == option_id
    assert [offer.offer_id for offer in result.offers] == [expected_offer]
    assert result.offers[0].price.amount == expected_amount  # type: ignore[union-attr]
    assert result.offers[0].price.billing_unit == "jaw"  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("option_id", "expected_offer", "expected_min"),
    [
        ("open", "sinus_lift.one_site.open", 68_000),
        ("closed", "sinus_lift.one_site.closed", 42_000),
    ],
)
def test_real_sinus_lift_options_never_mix(
    option_id: str,
    expected_offer: str,
    expected_min: int,
) -> None:
    _bundle, _context, result = _project(
        "sinus_lift",
        TargetStrategyMatch(
            family="implantology",
            jaw="upper",
            reported_context="reported_bone_deficit",
        ),
        selected_option_id=option_id,
    )

    assert [offer.offer_id for offer in result.offers] == [expected_offer]
    assert result.offers[0].price.mode == "from"
    assert result.offers[0].price.min_amount == expected_min  # type: ignore[union-attr]
    assert result.offers[0].price.currency == "RUB"  # type: ignore[union-attr]
    assert result.offers[0].price.billing_unit == "procedure"  # type: ignore[union-attr]


def test_real_projection_is_read_only_and_has_no_product_wiring() -> None:
    paths = sorted(path for path in DEMO_ROOT.rglob("*") if path.is_file())
    before = {path: _sha256(path) for path in paths}

    _project(
        "all_on_4",
        TargetStrategyMatch(extent="full_arch"),
        explicit_offer_id="all_on_4.jaw.nobel",
    )

    assert {path: _sha256(path) for path in paths} == before

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert not any(
        module.startswith(
            ("app", "config", "handlers", "orchestration", "routes", "telegram")
        )
        for module in imported_modules
    )
    assert not (
        {"write_text", "write_bytes", "unlink", "rename", "replace", "mkdir"}
        & called_attributes
    )
    assert not any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"skip", "skipif", "xfail"}
        for node in ast.walk(tree)
    )
