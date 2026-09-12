"""In-memory sparse target packs for FINAL_PRICE_AND_SERVICE_COVERAGE."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.response_schema import ResponseSchemaBundle


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_marketing() -> dict[str, object]:
    return {
        "version": 1,
        "limits": {
            "max_marketing_facts_per_turn": 0,
            "max_amplifiers_per_turn": 0,
            "max_scenarios_per_turn": 0,
        },
        "initial_commercial_blocks": {},
        "scenario_rules": {},
        "cta_contexts": {"default": "callback"},
    }


def _base_strategy() -> dict[str, object]:
    return {
        "version": 1,
        "default_max_options": 3,
        "default_service_priorities": {},
        "default_offer_priorities": {},
        "rules": [],
    }


def build_sparse_target_pack(
    tmp_path: Path,
    *,
    services: dict[str, object],
    offers: list[dict[str, object]] | None = None,
    family_prices: list[dict[str, object]] | None = None,
) -> Path:
    root = tmp_path / "target_response"
    (root / "pricebook" / "services").mkdir(parents=True)
    _write_json(root / "service_catalog.json", services)
    _write_json(root / "brand_catalog.json", {"version": 1, "brands": {}})
    _write_json(root / "pricebook" / "facts.json", {})
    _write_json(
        root / "pricebook" / "family_prices.json",
        {"version": 1, "records": family_prices or []},
    )
    (root / "clinic_strategy.yaml").write_text(
        "version: 1\ndefault_max_options: 3\ndefault_service_priorities: {}\n"
        "default_offer_priorities: {}\nrules: []\n",
        encoding="utf-8",
    )
    (root / "marketing.yaml").write_text(
        "version: 1\nlimits:\n  max_marketing_facts_per_turn: 0\n"
        "  max_amplifiers_per_turn: 0\n  max_scenarios_per_turn: 0\n"
        "initial_commercial_blocks: {}\nscenario_rules: {}\ncta_contexts:\n"
        "  default: callback\n",
        encoding="utf-8",
    )
    for offer in offers or []:
        offer_id = str(offer["offer_id"])
        _write_json(root / "pricebook" / "services" / f"{offer_id}.json", offer)
    return root


def _implantation_service(
    service_id: str,
    *,
    name: str | None = None,
    extent: list[str] | None = None,
) -> dict[str, object]:
    return {
        "name": name or service_id,
        "aliases": [],
        "family": "implantology",
        "roles": ["protocol"],
        "active": True,
        "content_ref": f"implantation__service__{service_id}.md",
        "selection": {
            "mode": "scope",
            "extent": extent or ["one_tooth", "few_teeth", "full_arch"],
        },
        "options": [],
    }


def family_only_detailed_catalog_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "classic": _implantation_service("classic"),
            "all_on_4": _implantation_service("all_on_4", extent=["full_arch"]),
            "all_on_6": _implantation_service("all_on_6", extent=["full_arch"]),
        },
        offers=[],
        family_prices=[
            {
                "family_price_id": "implantation_family_from",
                "topic": "implantation",
                "price": {
                    "mode": "from",
                    "min_amount": 25000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "applies_to_service_ids": ["classic", "all_on_4", "all_on_6"],
                "approved_context": (
                    "Общая начальная стоимость направления; "
                    "не является ценой отдельного протокола"
                ),
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def umbrella_family_only_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "implantation": {
                "name": "Имплантация",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__implantation.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth", "few_teeth", "full_arch"],
                },
                "options": [],
            },
        },
        offers=[],
        family_prices=[
            {
                "family_price_id": "implantation_family_from",
                "topic": "implantation",
                "price": {
                    "mode": "from",
                    "min_amount": 25000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "applies_to_service_ids": ["implantation"],
                "approved_context": "Общая стоимость имплантации в материалах клиники",
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def service_specific_beats_family_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={"classic": _implantation_service("classic")},
        offers=[
            {
                "offer_id": "classic.default",
                "service_id": "classic",
                "active": True,
                "price": {
                    "mode": "from",
                    "min_amount": 45000,
                    "currency": "RUB",
                    "billing_unit": "implant",
                },
                "package": {"label": "classic", "includes": ["implant"]},
            }
        ],
        family_prices=[
            {
                "family_price_id": "implantation_family_from",
                "topic": "implantation",
                "price": {
                    "mode": "from",
                    "min_amount": 25000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "applies_to_service_ids": ["classic"],
                "approved_context": "Family fallback must not win",
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def no_public_beats_family_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={"classic": _implantation_service("classic")},
        offers=[
            {
                "offer_id": "classic.no_public",
                "service_id": "classic",
                "active": True,
                "price": {
                    "mode": "no_public_price",
                    "approved_text": "Точная цена после консультации и КТ.",
                },
                "package": {"label": "classic", "includes": []},
            }
        ],
        family_prices=[
            {
                "family_price_id": "implantation_family_from",
                "topic": "implantation",
                "price": {
                    "mode": "from",
                    "min_amount": 25000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "applies_to_service_ids": ["classic"],
                "approved_context": "Must not override no_public_price",
            }
        ],
    )
    return root, load_response_schema_bundle(root)
