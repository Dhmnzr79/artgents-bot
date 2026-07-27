from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
import yaml

from contracts.response_schema import (
    ResponseSchemaBundle,
    TargetBrandCatalog,
    TargetCommercialFact,
    TargetOffer,
    TargetService,
)
from core.doctor_schema_loader import load_doctor_catalog
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.service_data_context import build_service_data_context


DEMO_ROOT = Path("clients/demo")
TARGET_ROOT = DEMO_ROOT / "target_response"
TARGET_SERVICES = TARGET_ROOT / "service_catalog.json"
TARGET_BRANDS = TARGET_ROOT / "brand_catalog.json"
TARGET_FACTS = TARGET_ROOT / "pricebook/facts.json"
TARGET_OFFERS = TARGET_ROOT / "pricebook/services"

UNIT_LABELS = {
    "aligners": (
        "course",
        "за полный курс лечения; зависит от сложности прикуса и количества кап",
    ),
    "all_on_4": (
        "jaw",
        "за одну челюсть; КТ и костная пластика по показаниям — отдельно",
    ),
    "all_on_6": (
        "jaw",
        "за одну челюсть; КТ и костная пластика по показаниям — отдельно",
    ),
    "caries": (
        "tooth",
        "за лечение одного зуба; зависит от глубины поражения и объёма пломбирования",
    ),
    "clasp_dentures": (
        "unit",
        "за один протез; частичное восстановление, вариант на кламмерах или замках",
    ),
    "classic": (
        "tooth_package",
        "за один зуб под ключ; КТ при необходимости — отдельно",
    ),
    "implant_supported_prosthetics": (
        "tooth",
        "за ортопедический этап для одного зуба (коронка/мост); "
        "имплантация оплачивается отдельно",
    ),
    "one_stage": (
        "tooth_package",
        "за один зуб под ключ; КТ и лечение воспаления до операции — "
        "по показаниям, отдельно",
    ),
    "periodontitis": (
        "course",
        "за полный курс лечения; точный план после диагностики дёсен",
    ),
    "professional_whitening": (
        "procedure",
        "за одну процедуру; точная стоимость зависит от выбранного протокола",
    ),
    "pterygoid_implants": (
        "implant",
        "за один имплант; коронка или протез — отдельно",
    ),
    "pulpitis": (
        "tooth",
        "за лечение одного зуба: лечение каналов и восстановление зуба; "
        "при необходимости коронка оплачивается отдельно",
    ),
    "removable_dentures": (
        "jaw",
        "за одну челюсть; имплантация — отдельно",
    ),
    "sinus_lift": (
        "procedure",
        "за одну область; стоимость зависит от объёма костного материала и "
        "способа доступа; имплант, коронка и КТ — отдельно",
    ),
    "teeth_treatment": ("tooth", "за лечение одного зуба"),
    "temporary_teeth": (
        "tooth",
        "за одну временную коронку на период приживления; "
        "постоянная коронка — отдельно",
    ),
    "tomography": ("procedure", "за одно исследование"),
    "tooth_extraction": (
        "tooth",
        "за удаление одного зуба; сложное удаление или зуб мудрости — "
        "по результатам осмотра",
    ),
    "veneers": (
        "tooth",
        "за один зуб; полная реставрация улыбки рассчитывается на консультации",
    ),
    "zirconia_crowns": (
        "unit",
        "за одну конструкцию; стоимость зависит от сложности и типа — коронка или мост",
    ),
    "zygomatic_implants": (
        "jaw",
        "за одну челюсть; временный и постоянный протез — по плану лечения",
    ),
}

EXPECTED_BRANDS = {
    "version": 1,
    "brands": {
        "implantium": {
            "canonical_name": "Implantium",
            "country": "Южная Корея",
            "aliases": ["имплантиум"],
        },
        "impro": {
            "canonical_name": "Impro",
            "country": "Германия",
            "aliases": ["импро"],
        },
        "nobel_biocare": {
            "canonical_name": "Nobel Biocare",
            "country": "Швейцария",
            "aliases": ["nobel", "нобель", "нобел"],
        },
    },
}

BRAND_IDS = {
    "Implantium": "implantium",
    "Impro": "impro",
    "Nobel Biocare": "nobel_biocare",
}
OPTION_IDS = {
    ("removable_dentures", "partial"): "partial",
    ("removable_dentures", "full"): "full",
    ("sinus_lift", "closed"): "closed",
    ("sinus_lift", "open"): "open",
}
PAYMENT_STAGE_SERVICES = {"all_on_4", "all_on_6", "classic", "one_stage"}


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate_mapping_key:{key}")
        result[key] = value
    return result


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_pairs,
    )
    if not isinstance(value, dict):
        raise TypeError("json_top_level_must_be_mapping")
    return value


def _target_offer_files() -> list[Path]:
    return sorted(TARGET_OFFERS.glob("*.json"), key=lambda path: path.name)


def _target_offer_records() -> list[dict[str, Any]]:
    return [_load_json(path) for path in _target_offer_files()]


def _service_fact_refs() -> dict[str, list[str]]:
    refs: dict[str, list[str]] = {}
    for offer in _target_offer_records():
        sid = offer["service_id"]
        refs.setdefault(sid, [])
        for fact_id in offer.get("fact_refs", []):
            if fact_id not in refs[sid]:
                refs[sid].append(fact_id)
    return refs


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _real_bundle() -> ResponseSchemaBundle:
    raw_services = _load_json(TARGET_SERVICES)
    return ResponseSchemaBundle.model_validate(
        {
            "services": {
                service_id: TargetService.model_validate(record)
                for service_id, record in raw_services.items()
            },
            "brands": _load_json(TARGET_BRANDS),
            "offers": _target_offer_records(),
            "facts": _load_json(TARGET_FACTS),
            "strategy": {"version": 1, "default_max_options": 3, "rules": []},
            "marketing": {
                "version": 1,
                "limits": {
                    "max_marketing_facts_per_turn": 0,
                    "max_amplifiers_per_turn": 0,
                    "max_scenarios_per_turn": 0,
                },
                "initial_commercial_blocks": {},
                "scenario_rules": {},
                "cta_contexts": {"default": "validation_only"},
            },
        }
    )


def test_target_files_are_strict_complete_frozen_wire_data() -> None:
    offer_files = _target_offer_files()
    offers = _target_offer_records()
    brands_raw = _load_json(TARGET_BRANDS)
    facts_raw = _load_json(TARGET_FACTS)

    assert len(offer_files) == len(offers) == 32
    assert len({offer["offer_id"] for offer in offers}) == 32
    for path, offer in zip(offer_files, offers, strict=True):
        assert path.name == f'{offer["offer_id"]}.json'
    for offer in offers:
        assert TargetOffer.model_validate(offer).model_dump(exclude_none=True) == offer
    assert (
        TargetBrandCatalog.model_validate(brands_raw).model_dump(exclude_none=True)
        == brands_raw
    )
    assert len(facts_raw) == 6
    for fact in facts_raw.values():
        parsed = TargetCommercialFact.model_validate(fact)
        normalized = parsed.model_dump(exclude_none=True)
        for key, value in fact.items():
            assert normalized[key] == value


def test_nested_duplicate_keys_are_rejected() -> None:
    duplicate = '{"offer":{"price":{"mode":"fixed","mode":"from"}}}'
    with pytest.raises(ValueError, match="duplicate_mapping_key:mode"):
        json.loads(duplicate, object_pairs_hook=_reject_duplicate_pairs)


def test_exact_12_top_offers_preserve_authored_payment_stages() -> None:
    target = {offer["offer_id"]: offer for offer in _target_offer_records()}
    materialized_offer_ids = {
        offer_id for offer_id, offer in target.items() if "payment_stages" in offer
    }

    assert len(materialized_offer_ids) == 12

    for offer_id in materialized_offer_ids:
        offer = target[offer_id]
        stages = offer["payment_stages"]
        assert len(stages) == 2
        assert sum(stage["amount"] for stage in stages) == offer["price"]["amount"]
        followup_ids = [item["id"] for item in offer["followups"]]
        assert followup_ids == ["stages", "includes"]

    offers_without_stages = set(target) - materialized_offer_ids
    assert len(offers_without_stages) == 20
    assert {
        "sinus_lift.one_site.closed",
        "sinus_lift.one_site.open",
        "pulpitis.default",
    } <= offers_without_stages
    for offer_id in offers_without_stages:
        offer = target[offer_id]
        assert "payment_stages" not in offer
        assert all(followup["id"] != "stages" for followup in offer["followups"])


def test_owner_units_labels_and_followups_have_no_legacy_dead_actions() -> None:
    offers = _target_offer_records()

    assert set(UNIT_LABELS) == set(_load_json(TARGET_SERVICES))
    for offer in offers:
        unit, label = UNIT_LABELS[offer["service_id"]]
        assert offer["price"]["billing_unit"] == unit
        assert offer["package"]["label"] == label
        assert all(
            followup["id"] in {"stages", "includes"}
            for followup in offer["followups"]
        )
        assert all(followup["action"] == "price_aspect" for followup in offer["followups"])
        assert not (
            {"recommended", "excludes", "note", "intro_text"}
            & set(offer)
        )

    sinus = [offer for offer in offers if offer["service_id"] == "sinus_lift"]
    assert {offer["price"]["mode"] for offer in sinus} == {"from"}
    assert {offer["price"]["min_amount"] for offer in sinus} == {42000, 68000}
    assert next(offer for offer in offers if offer["service_id"] == "pulpitis")[
        "followups"
    ] == []


def test_brands_and_facts_preserve_target_integrity() -> None:
    brands = _load_json(TARGET_BRANDS)
    facts = _load_json(TARGET_FACTS)
    fact_refs = _service_fact_refs()

    assert brands == EXPECTED_BRANDS
    assert set(brands["brands"]) == {"implantium", "impro", "nobel_biocare"}
    target_alias_pairs = {
        alias: record["canonical_name"]
        for record in brands["brands"].values()
        for alias in record["aliases"]
    }
    canonical_name_pairs = {
        record["canonical_name"].lower(): record["canonical_name"]
        for record in brands["brands"].values()
    }
    assert target_alias_pairs | canonical_name_pairs

    assert len(facts) == 6
    kb_refs = set(build_response_schema_kb_refs(DEMO_ROOT / "md"))
    for fact_id, fact in facts.items():
        parsed = TargetCommercialFact.model_validate(fact)
        assert parsed.active is True
        assert parsed.incompatible_with == []
        if parsed.detail_ref:
            assert f"kb:{parsed.detail_ref}" in kb_refs
        linked = [
            service_id
            for service_id, refs in fact_refs.items()
            if fact_id in refs
        ]
        assert set(parsed.allowed_service_ids or ()) <= set(linked) | set(
            parsed.allowed_service_ids or ()
        )


def test_real_bundle_builds_every_service_price_doctor_context() -> None:
    bundle = _real_bundle()
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")

    assert len(bundle.services) == 22
    assert len(bundle.offers) == 32
    for service_id in bundle.services:
        context = build_service_data_context(bundle, doctors, service_id)
        expected_offers = [
            offer.model_dump() for offer in bundle.offers if offer.service_id == service_id
        ]
        expected_doctor_ids = [
            doctor_id
            for doctor_id, doctor in doctors.doctors.items()
            if service_id in doctor.service_ids
        ]
        assert context.service_id == service_id
        assert context.service.model_dump() == bundle.services[service_id].model_dump()
        assert [offer.model_dump() for offer in context.offers] == expected_offers
        assert expected_offers
        assert [doctor.doctor_id for doctor in context.doctors] == expected_doctor_ids

    tomography = build_service_data_context(bundle, doctors, "tomography")
    assert len(tomography.offers) == 1
    assert tomography.doctors == ()


def test_real_sources_are_read_only_and_test_has_no_product_wiring() -> None:
    paths = [
        TARGET_SERVICES,
        TARGET_BRANDS,
        TARGET_FACTS,
        DEMO_ROOT / "doctor_catalog.json",
        *_target_offer_files(),
        *sorted((DEMO_ROOT / "md").glob("*.md")),
    ]
    before = {path: _sha256(path) for path in paths}

    _real_bundle()
    load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    build_response_schema_kb_refs(DEMO_ROOT / "md")

    assert {path: _sha256(path) for path in paths} == before

    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    imported_modules.update(
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    )
    called_attributes = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert imported_modules.isdisjoint(
        {"app", "core.pricebook_loader", "doctors_lookup", "orchestration"}
    )
    assert called_attributes.isdisjoint(
        {"mkdir", "open", "touch", "unlink", "write_bytes", "write_text"}
    )
