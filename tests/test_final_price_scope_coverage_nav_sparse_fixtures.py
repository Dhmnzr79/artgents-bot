"""In-memory sparse packs for FINAL_PRICE_SCOPE_COVERAGE_NAV."""

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


def classic_one_tooth_only_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "classic": {
                "name": "Classic implant",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__classic.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth", "few_teeth"],
                },
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "classic.one_tooth.default",
                "service_id": "classic",
                "active": True,
                "applies_to_extents": ["one_tooth"],
                "price": {
                    "mode": "from",
                    "min_amount": 50000,
                    "currency": "RUB",
                    "billing_unit": "implant",
                },
                "package": {"label": "one tooth", "includes": ["implant"]},
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def three_extent_routes_pack(tmp_path: Path) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "classic": {
                "name": "Classic",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__classic.md",
                "selection": {
                    "mode": "scope",
                    "extent": ["one_tooth", "few_teeth", "full_arch"],
                },
                "options": [],
            },
            "bridge": {
                "name": "Bridge",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__bridge.md",
                "selection": {"mode": "scope", "extent": ["few_teeth"]},
                "options": [],
            },
            "all_on_4": {
                "name": "All-on-4",
                "aliases": [],
                "family": "implantology",
                "roles": ["advanced_protocol"],
                "active": True,
                "content_ref": "implantation__service__all_on_4.md",
                "selection": {"mode": "scope", "extent": ["full_arch"]},
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "classic.one_tooth",
                "service_id": "classic",
                "active": True,
                "applies_to_extents": ["one_tooth"],
                "price": {
                    "mode": "fixed",
                    "amount": 60000,
                    "currency": "RUB",
                    "billing_unit": "implant",
                },
                "package": {"label": "one", "includes": ["a"]},
            },
            {
                "offer_id": "bridge.few",
                "service_id": "bridge",
                "active": True,
                "applies_to_extents": ["few_teeth"],
                "price": {
                    "mode": "fixed",
                    "amount": 120000,
                    "currency": "RUB",
                    "billing_unit": "procedure",
                },
                "package": {"label": "few", "includes": ["b"]},
            },
            {
                "offer_id": "all_on_4.jaw",
                "service_id": "all_on_4",
                "active": True,
                "applies_to_extents": ["full_arch"],
                "price": {
                    "mode": "fixed",
                    "amount": 318000,
                    "currency": "RUB",
                    "billing_unit": "jaw",
                },
                "package": {"label": "jaw", "includes": ["c"]},
            },
        ],
    )
    return root, load_response_schema_bundle(root)
