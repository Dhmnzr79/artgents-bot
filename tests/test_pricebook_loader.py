from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.pricebook import PricebookServiceEntry
from core.pricebook_loader import (
    infer_brand_group,
    list_pricebook_service_ids,
    load_pricebook_manifest,
    load_pricebook_service,
    load_pricing_facts,
    offers_from_service_entry,
    resolve_fact_refs,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_PB = ROOT / "clients" / "demo" / "pricebook"


@pytest.fixture
def demo_client():
    return "demo"


def test_demo_has_all_catalog_price_keys(demo_client):
    catalog = json.loads((ROOT / "clients" / "demo" / "service_catalog.json").read_text(encoding="utf-8"))
    ids = set(list_pricebook_service_ids(demo_client))
    missing = []
    for sid, entry in catalog.items():
        if not isinstance(entry, dict) or not bool(entry.get("active", True)):
            continue
        price_key = str(entry.get("price_key") or "").strip()
        if price_key and price_key not in ids:
            missing.append(price_key)
    assert not missing, f"missing pricebook entries: {missing}"


def test_load_sinus_lift_and_pterygoid(demo_client):
    sinus = load_pricebook_service(demo_client, "sinus_lift")
    assert sinus is not None
    assert sinus.default_unit == "one_site"
    assert len(sinus.variants) == 2
    pterygoid = load_pricebook_service(demo_client, "pterygoid_implants")
    assert pterygoid is not None
    assert pterygoid.default_unit == "one_implant"


def test_demo_has_pricebook_services(demo_client):
    ids = list_pricebook_service_ids(demo_client)
    assert "classic" in ids
    assert "all_on_4" in ids
    assert "professional_whitening" in ids


def test_load_classic_entry(demo_client):
    entry = load_pricebook_service(demo_client, "classic")
    assert entry is not None
    assert entry.price_model == "complex"
    assert len(entry.variants) == 3
    assert entry.variants[0].brand_group in {None, "korean", "german", "swiss"}


def test_offers_from_classic_match_legacy_totals(demo_client):
    entry = load_pricebook_service(demo_client, "classic")
    assert entry
    offers = offers_from_service_entry(entry)
    totals = sorted(o.total for o in offers)
    assert totals == [76200, 85200, 101200]


def test_resolve_fact_refs_strict_and_natural(demo_client):
    facts = resolve_fact_refs(
        demo_client,
        ["tax_deduction", "free_implant_consult"],
        usable_in="price_answer",
    )
    ids = {f.id for f in facts}
    assert "tax_deduction" in ids
    assert "free_implant_consult" in ids
    assert facts[0].render_mode in {"strict", "natural"}


def test_manifest_implantation_group(demo_client):
    manifest = load_pricebook_manifest(demo_client)
    assert manifest
    group = manifest.groups["implantation"]
    assert len(group.members) >= 4


def test_infer_brand_group():
    assert infer_brand_group("Implantium (Южная Корея)") == "korean"
    assert infer_brand_group("Impro (Германия)") == "german"


def test_all_service_files_validate():
    svc_dir = DEMO_PB / "services"
    for path in svc_dir.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        PricebookServiceEntry.model_validate(raw)


def test_facts_file_loads(demo_client):
    facts = load_pricing_facts(demo_client)
    assert facts
    assert "installment_12" in facts.facts
