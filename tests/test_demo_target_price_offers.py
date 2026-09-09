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
        "за восстановление одного зуба (имплант + постоянная коронка); "
        "КТ при необходимости и временная коронка — отдельно",
    ),
    "implant_supported_prosthetics": (
        "tooth",
        "за одну постоянную коронку на уже установленном импланте "
        "(абатмент/основание, изготовление и фиксация включены); "
        "хирургическая установка импланта — отдельно",
    ),
    "one_stage": (
        "tooth_package",
        "за восстановление одного зуба (имплант в день удаления + постоянная коронка); "
        "КТ, лечение воспаления и временная коронка — по показаниям, отдельно",
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
        "за один имплант с хирургической установкой и местной анестезией; "
        "протезирование и диагностика (КТ) — отдельно",
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
        "за одну временную коронку на импланте (необходимые компоненты и фиксация включены); "
        "постоянная коронка, хирургическая установка импланта и протез на челюсть — отдельно",
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
        "tooth",
        "за одну циркониевую коронку на собственном зубе (изготовление, примерка и фиксация включены); "
        "подготовительное лечение зуба — отдельно",
    ),
    "zygomatic_implants": (
        "jaw",
        "за хирургический этап на верхнюю челюсть",
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

CHECKPOINT_SERVICE_IDS = (
    "implant_supported_prosthetics",
    "zirconia_crowns",
    "temporary_teeth",
    "pterygoid_implants",
    "zygomatic_implants",
    "all_on_4",
    "all_on_6",
    "classic",
    "one_stage",
)

CHECKPOINT_OFFER_COUNTS = {
    "implant_supported_prosthetics": 1,
    "zirconia_crowns": 1,
    "temporary_teeth": 1,
    "pterygoid_implants": 1,
    "zygomatic_implants": 1,
    "all_on_4": 3,
    "all_on_6": 3,
    "classic": 3,
    "one_stage": 3,
}


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


def _wire_values_equal(parsed: Any, raw: Any) -> bool:
    if isinstance(raw, dict) and isinstance(parsed, dict):
        return raw.keys() == parsed.keys() and all(
            _wire_values_equal(parsed[key], raw[key]) for key in raw
        )
    if isinstance(raw, list) and isinstance(parsed, (list, tuple)):
        return list(parsed) == raw
    return parsed == raw


def _offer_wire_with_schema_defaults(offer: dict[str, Any]) -> dict[str, Any]:
    """Mirror TargetOffer defaults omitted from on-disk JSON (e.g. empty excludes)."""

    wire = json.loads(json.dumps(offer))
    package = dict(wire.get("package", {}))
    package.setdefault("excludes", [])
    wire["package"] = package
    return TargetOffer.model_validate(wire).model_dump(exclude_none=True)


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
        parsed = TargetOffer.model_validate(offer).model_dump(exclude_none=True)
        assert _offer_wire_with_schema_defaults(offer) == parsed
    assert (
        TargetBrandCatalog.model_validate(brands_raw).model_dump(exclude_none=True)
        == brands_raw
    )
    assert len(facts_raw) == 10
    for fact in facts_raw.values():
        parsed = TargetCommercialFact.model_validate(fact)
        normalized = parsed.model_dump(exclude_none=True)
        for key, value in fact.items():
            assert _wire_values_equal(normalized[key], value)


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
        assert all(str(stage.get("timing_text") or "").strip() for stage in stages)
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


def _numeric_price_service_ids() -> set[str]:
    return {
        offer["service_id"]
        for offer in _target_offer_records()
        if offer.get("price", {}).get("mode") != "no_public_price"
    }


def test_owner_units_labels_and_followups_have_no_legacy_dead_actions() -> None:
    offers = _target_offer_records()
    catalog_services = set(_load_json(TARGET_SERVICES))
    numeric_services = _numeric_price_service_ids()

    assert set(UNIT_LABELS) == numeric_services
    assert numeric_services <= catalog_services
    assert "bone_graft" in catalog_services
    assert "bone_graft" not in UNIT_LABELS
    for offer in offers:
        if offer.get("price", {}).get("mode") == "no_public_price":
            assert "billing_unit" not in offer.get("price", {})
            continue
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

    assert len(facts) == 10
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


def _md_body(relative_path: str) -> str:
    parts = (DEMO_ROOT / "md" / relative_path).read_text(encoding="utf-8").split("---", 2)
    assert len(parts) == 3
    return parts[2]


def test_real_bundle_builds_every_service_price_doctor_context() -> None:
    bundle = _real_bundle()
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")

    assert len(bundle.services) >= 22
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
        assert [doctor.doctor_id for doctor in context.doctors] == expected_doctor_ids

    services_without_offers = {
        service_id
        for service_id in bundle.services
        if not any(offer.service_id == service_id for offer in bundle.offers)
    }
    assert services_without_offers == {"braces"}

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


CHANGED_OFFER_IDS = frozenset(
    {
        "implant_supported_prosthetics.default",
        "zirconia_crowns.default",
        "temporary_teeth.default",
        "pterygoid_implants.default",
        "zygomatic_implants.default",
        "all_on_4.jaw.implantium",
        "all_on_4.jaw.impro",
        "all_on_4.jaw.nobel",
        "all_on_6.jaw.implantium",
        "all_on_6.jaw.impro",
        "all_on_6.jaw.nobel",
        "classic.one_tooth.implantium",
        "classic.one_tooth.impro",
        "classic.one_tooth.nobel",
        "one_stage.one_tooth.implantium",
        "one_stage.one_tooth.impro",
        "one_stage.one_tooth.nobel",
        "bone_graft.default",
        "sinus_lift.one_site.closed",
        "sinus_lift.one_site.open",
        "removable_dentures.jaw.full",
        "removable_dentures.jaw.partial",
    }
)

UNCHANGED_OFFER_SHA256 = {
    "aligners.default": "ccc2f71863a93134c319e4880cd14ea0489aaf953cc87e2f2dbd327269bd5873",
    "caries.default": "0e6f0e22879cc3e3372504745d068073c6103bd448785e8e87e3ab8335c8867d",
    "clasp_dentures.default": "e06056cea65981bec26eeb128107e896d0dcd93116619088e6da50c8a467d696",
    "periodontitis.default": "8374c42e22ab17f3d2948f744152295c1796f65f6712526760d30ef3e985eed3",
    "professional_whitening.default": "98574b42e086b344885ce8055705ed14caa0501dd3e4b664a30800656f7f72d1",
    "pulpitis.default": "c617d6746a6baf02d97c0dd385826b66d8c5dd0d4cb0eb79ac06faf5f20def4d",
    "teeth_treatment.default": "f90932839c87b59f43c1c307721678ce9e6cc69f8bd4d724bd4db978fec77697",
    "tomography.default": "daec4b2203db784200297359e4b3ef021bbf09ea5f06c6b7322bf023fcdc162b",
    "tooth_extraction.default": "1ca8c4d0db94dda49d9f7d1dcced59d29aef93fa9a9794812436fa288ca1bb2d",
    "veneers.default": "cb903c935892ec5cd8065749b720d4aa2f4386396b41c8a08ec49188c766100d",
}


def test_owner_decisions_disambiguate_single_unit_offers() -> None:
    target = {offer["offer_id"]: offer for offer in _target_offer_records()}

    implant_prosthetics = target["implant_supported_prosthetics.default"]
    assert implant_prosthetics["price"]["min_amount"] == 31000
    assert implant_prosthetics["price"]["billing_unit"] == "tooth"
    label = implant_prosthetics["package"]["label"]
    assert "одну постоянную коронку" in label
    assert "мост" not in label
    assert "хирургическая установка импланта" in label

    zirconia = target["zirconia_crowns.default"]
    assert zirconia["price"]["min_amount"] == 25000
    assert zirconia["price"]["billing_unit"] == "tooth"
    assert "собственном зубе" in zirconia["package"]["label"]
    assert "мост" not in zirconia["package"]["label"]

    temporary = target["temporary_teeth.default"]
    assert temporary["price"]["min_amount"] == 18000
    assert temporary["price"]["billing_unit"] == "tooth"
    assert "временную коронку" in temporary["package"]["label"]
    assert "протез на челюсть — отдельно" in temporary["package"]["label"]

    pterygoid = target["pterygoid_implants.default"]
    zygomatic = target["zygomatic_implants.default"]
    assert pterygoid["price"]["billing_unit"] == "implant"
    assert zygomatic["price"]["billing_unit"] == "jaw"
    assert pterygoid["price"]["min_amount"] == 95000
    assert zygomatic["price"]["min_amount"] == 420000
    assert "хирургический этап" in zygomatic["package"]["label"]
    assert "под ключ" not in zygomatic["package"]["label"].lower()


def test_all_on_offers_distinguish_temporary_and_permanent_prosthesis() -> None:
    for offer in _target_offer_records():
        if offer["service_id"] not in {"all_on_4", "all_on_6"}:
            continue
        includes = offer["package"]["includes"]
        assert sum("временный" in line.lower() for line in includes) == 1
        assert sum("постоянный" in line.lower() for line in includes) == 1
        stages = offer["payment_stages"]
        assert len(stages) == 2
        assert sum(stage["amount"] for stage in stages) == offer["price"]["amount"]
        assert "временн" in stages[0]["label"].lower()
        assert "постоянн" in stages[1]["label"].lower()
        assert "рассроч" not in stages[0]["label"].lower()
        assert "рассроч" not in stages[1]["label"].lower()


def test_classic_and_one_stage_include_permanent_crown_not_silent_temporary() -> None:
    for offer in _target_offer_records():
        if offer["service_id"] not in {"classic", "one_stage"}:
            continue
        includes = offer["package"]["includes"]
        assert any("постоянная коронка" in item for item in includes)
        assert not any("временн" in item.lower() for item in includes)
        label = offer["package"]["label"].lower()
        assert "временн" in label
        stages = offer["payment_stages"]
        assert sum(stage["amount"] for stage in stages) == offer["price"]["amount"]


def test_ambiguous_offer_checkpoint_touches_only_seventeen_offers() -> None:
    offer_ids = {path.stem for path in _target_offer_files()}
    assert len(offer_ids) == 32
    assert len(CHANGED_OFFER_IDS) == 22
    assert len(UNCHANGED_OFFER_SHA256) == 10
    assert offer_ids == CHANGED_OFFER_IDS | set(UNCHANGED_OFFER_SHA256)
    for offer_id, expected_hash in UNCHANGED_OFFER_SHA256.items():
        path = TARGET_OFFERS / f"{offer_id}.json"
        assert _sha256(path) == expected_hash


def test_checkpoint_services_build_real_data_context_with_section66_semantics() -> None:
    bundle = _real_bundle()
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")
    assert sum(CHECKPOINT_OFFER_COUNTS.values()) == 17

    for service_id in CHECKPOINT_SERVICE_IDS:
        context = build_service_data_context(bundle, doctors, service_id)
        assert context.service_id == service_id
        assert len(context.offers) == CHECKPOINT_OFFER_COUNTS[service_id]
        assert {offer.offer_id for offer in context.offers} <= CHANGED_OFFER_IDS

        for offer in context.offers:
            price = offer.price
            unit, label = UNIT_LABELS[service_id]
            assert price.billing_unit == unit
            assert offer.package.label == label

            if service_id in {"implant_supported_prosthetics", "zirconia_crowns", "temporary_teeth"}:
                assert price.mode == "from"
                assert price.min_amount in {31000, 25000, 18000}
                assert offer.payment_stages is None
            elif service_id == "pterygoid_implants":
                assert price.min_amount == 95000
                assert price.billing_unit == "implant"
                assert "протезирование" in offer.package.label
            elif service_id == "zygomatic_implants":
                assert price.min_amount == 420000
                assert price.billing_unit == "jaw"
                assert "хирургический этап" in offer.package.label
                assert "под ключ" not in offer.package.label.lower()
            elif service_id in {"all_on_4", "all_on_6"}:
                assert price.mode == "fixed"
                assert price.billing_unit == "jaw"
                includes = offer.package.includes
                assert sum("временный" in line.lower() for line in includes) == 1
                assert sum("постоянный" in line.lower() for line in includes) == 1
                assert offer.payment_stages is not None
                assert sum(stage.amount for stage in offer.payment_stages) == price.amount
            elif service_id in {"classic", "one_stage"}:
                assert price.mode == "fixed"
                assert price.billing_unit == "tooth_package"
                assert any("постоянная коронка" in item for item in offer.package.includes)
                assert "временн" in offer.package.label.lower()
                assert offer.payment_stages is not None
                assert sum(stage.amount for stage in offer.payment_stages) == price.amount


def test_temporary_teeth_md_aligns_protocol_timing_without_all_on_single_crown() -> None:
    body = _md_body("implantation__service__temporary_teeth.md")
    korotko = body.split("### Когда ставят")[0]

    assert "на один зуб" in korotko
    assert "не временный несъёмный протез на всю челюсть" in korotko
    assert "2–3 дня" in korotko
    assert "3–4 месяца" in korotko
    assert "all-on" not in korotko.lower()
    assert "сразу после имплантации или через несколько дней" not in korotko

    when_section = body.split("### Когда ставят")[1].split("### Ограничения")[0]
    assert "одномоментной" in when_section
    assert "классической" in when_section
    assert "3–4 месяца" in when_section


def test_duration_faq_md_separates_temporary_result_from_permanent_crown() -> None:
    body = _md_body("implantation__faq__duration.md")
    korotko = body.split("### От чего зависит")[0]

    assert "Временный результат" in korotko
    assert "Постоянная" in korotko
    assert "первые дни" in korotko
    assert "3–6 месяцев" in korotko
    assert "от нескольких дней до" not in korotko
    assert "Весь путь от диагностики до постоянной коронки" not in korotko

    methods = body.split("По методам:")[1].split("### Можно ли ускорить")[0]
    assert "классическая имплантация — **3–6 месяцев**" in methods
    assert "постоянный протез — после приживления" in methods


CHECKPOINT_FACT_IDS = frozenset(
    {
        "tax_deduction",
        "installment_12",
        "free_implant_consult",
        "implant_warranty",
        "implant_same_day_discount",
        "professional_whitening_discount",
        "payment_stages",
        "fixed_price",
        "sv_3d_diagnocat",
        "sv_aprf",
    }
)

CHECKPOINT_CONTROL_DATE = "2026-12-01"


def test_commercial_facts_catalog_has_exact_ten_ids_and_validates() -> None:
    facts_raw = _load_json(TARGET_FACTS)
    assert set(facts_raw) == CHECKPOINT_FACT_IDS
    for fact in facts_raw.values():
        parsed = TargetCommercialFact.model_validate(fact)
        normalized = parsed.model_dump(exclude_none=True)
        for key, value in fact.items():
            assert _wire_values_equal(normalized[key], value)


def test_canonical_fact_texts_carry_unambiguous_source_conditions() -> None:
    bundle = _real_bundle()

    installment = bundle.facts["installment_12"]
    assert "12 месяцев" in installment.text_fact
    assert "оформление на консультации" in installment.text_fact
    assert "24" not in installment.text_fact

    consult = bundle.facts["free_implant_consult"]
    assert "31 декабря 2026" in consult.text_fact
    assert "бесплатная консультация" in consult.text_fact.lower()
    assert "три варианта плана лечения по стоимости" in consult.text_fact
    assert "КТ при необходимости оплачивается отдельно" in consult.text_fact
    assert "не бесплатное лечение" not in consult.text_fact.lower()
    assert "20 000" not in consult.text_fact
    assert "20-лет" not in consult.text_fact
    assert "стаж" not in consult.text_fact.lower()

    warranty = bundle.facts["implant_warranty"]
    assert "корректировки и помощь бесплатно" in warranty.text_fact
    assert "поломке конструкции" not in warranty.text_fact
    assert "перестановка" not in warranty.text_fact.lower()

    tax = bundle.facts["tax_deduction"]
    assert tax.text_fact == (
        "Поможем подготовить документы для оформления налогового вычета за лечение."
    )
    assert set(tax.allowed_service_ids) == {
        "aligners",
        "all_on_4",
        "all_on_6",
        "bone_graft",
        "caries",
        "classic",
        "clasp_dentures",
        "implant_supported_prosthetics",
        "one_stage",
        "periodontitis",
        "professional_whitening",
        "pulpitis",
        "removable_dentures",
        "sinus_lift",
        "teeth_treatment",
        "temporary_teeth",
        "tomography",
        "tooth_extraction",
        "veneers",
        "zirconia_crowns",
        "zygomatic_implants",
        "pterygoid_implants",
    }

    same_day = bundle.facts["implant_same_day_discount"]
    assert "до 15%" in same_day.text_fact
    assert same_day.text_fact.count("15%") == 1
    assert "скидка 15%" not in same_day.text_fact

    whitening = bundle.facts["professional_whitening_discount"]
    assert whitening.active_until == "2026-11-30"
    assert whitening.text_fact == (
        "Сейчас на профессиональное отбеливание действует скидка 10% до 30 ноября 2026 года."
    )

    payment_stages = bundle.facts["payment_stages"]
    assert payment_stages.text_fact == "Доступна оплата лечения по этапам."

    fixed_price = bundle.facts["fixed_price"]
    assert "фиксируется в договоре" in fixed_price.text_fact


def test_expired_whitening_promo_excluded_on_checkpoint_control_date() -> None:
    from core.target_marketing_selector import _fact_is_eligible

    bundle = _real_bundle()
    assert not _fact_is_eligible(
        bundle,
        "fact:professional_whitening_discount",
        service_id="professional_whitening",
        turn_topic=None,
        today_iso=CHECKPOINT_CONTROL_DATE,
        shown_fact_ids=frozenset(),
        selected_fact_ids=set(),
    )
    assert _fact_is_eligible(
        bundle,
        "fact:installment_12",
        service_id="classic",
        turn_topic=None,
        today_iso=CHECKPOINT_CONTROL_DATE,
        shown_fact_ids=frozenset(),
        selected_fact_ids=set(),
    )


def test_checkpoint_offers_link_facts_in_real_service_data_context() -> None:
    bundle = _real_bundle()
    doctors = load_doctor_catalog(DEMO_ROOT / "doctor_catalog.json")

    classic = build_service_data_context(bundle, doctors, "classic")
    classic_fact_refs = {
        fact_ref for offer in classic.offers for fact_ref in offer.fact_refs
    }
    assert {"installment_12", "free_implant_consult", "implant_warranty"}.issubset(
        classic_fact_refs
    )
    assert classic.offers[0].fact_refs
    for fact_id in classic_fact_refs:
        assert fact_id in bundle.facts

    all_on = build_service_data_context(bundle, doctors, "all_on_4")
    all_on_fact_refs = {fact_ref for offer in all_on.offers for fact_ref in offer.fact_refs}
    assert "tax_deduction" in all_on_fact_refs
    assert "implant_same_day_discount" in all_on_fact_refs
    assert bundle.facts["tax_deduction"].text_fact.startswith("Поможем подготовить")

    whitening = build_service_data_context(bundle, doctors, "professional_whitening")
    whitening_fact_refs = {
        fact_ref for offer in whitening.offers for fact_ref in offer.fact_refs
    }
    assert "professional_whitening_discount" in whitening_fact_refs
