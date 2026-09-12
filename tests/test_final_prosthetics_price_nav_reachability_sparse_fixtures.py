"""In-memory sparse packs for FINAL_PROSTHETICS_PRICE_NAV_REACHABILITY."""

from __future__ import annotations

import json
from pathlib import Path

from contracts.response_schema import ResponseSchemaBundle


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def build_sparse_target_pack(
    tmp_path: Path,
    *,
    services: dict[str, object],
    offers: list[dict[str, object]] | None = None,
) -> Path:
    root = tmp_path / "target_response"
    (root / "pricebook" / "services").mkdir(parents=True)
    _write_json(root / "service_catalog.json", services)
    _write_json(root / "brand_catalog.json", {"version": 1, "brands": {}})
    _write_json(root / "pricebook" / "facts.json", {})
    _write_json(root / "pricebook" / "family_prices.json", {"version": 1, "records": []})
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
        _write_json(
            root / "pricebook" / "services" / f"{offer['offer_id']}.json",
            offer,
        )
    return root


def prosthetics_stage_only_one_tooth_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "zirconia_crowns": {
                "name": "Zirconia crowns",
                "aliases": [],
                "family": "prosthodontics",
                "roles": [],
                "active": True,
                "content_ref": "prosthetics__service__zirconia_crowns.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth"],
                    "stage": ["natural_tooth_present"],
                },
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "zirconia_crowns.default",
                "service_id": "zirconia_crowns",
                "active": True,
                "applies_to_extents": ["one_tooth"],
                "price": {
                    "mode": "from",
                    "min_amount": 25000,
                    "currency": "RUB",
                    "billing_unit": "unit",
                },
                "package": {"label": "crown", "includes": []},
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def prosthetics_stage_paths_without_prices_pack(
    tmp_path: Path,
) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "zirconia_crowns": {
                "name": "Zirconia crowns",
                "aliases": [],
                "family": "prosthodontics",
                "roles": [],
                "active": True,
                "content_ref": "prosthetics__service__zirconia_crowns.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth"],
                    "stage": ["natural_tooth_present"],
                },
                "options": [],
            },
            "implant_supported_prosthetics": {
                "name": "Implant supported",
                "aliases": [],
                "family": "prosthodontics",
                "roles": [],
                "active": True,
                "content_ref": "prosthetics__service__implant_supported_prosthetics.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth"],
                    "stage": ["implant_placed"],
                },
                "options": [],
            },
        },
        offers=[],
    )
    return root, load_response_schema_bundle(root)
