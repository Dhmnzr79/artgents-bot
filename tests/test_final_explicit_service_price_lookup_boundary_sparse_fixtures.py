"""In-memory sparse packs for FINAL_EXPLICIT_SERVICE_PRICE_LOOKUP_BOUNDARY."""

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


def explicit_lookup_session_block_pack(
    tmp_path: Path,
) -> tuple[Path, ResponseSchemaBundle]:
    """Per-tooth priced service; inherited full_arch must not block explicit lookup."""

    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "svc_per_tooth": {
                "name": "Per-tooth protocol",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__svc_per_tooth.md",
                "selection": {
                    "mode": "context",
                    "extent": ["one_tooth", "few_teeth"],
                    "stage": ["extraction_context"],
                },
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "svc_per_tooth.default",
                "service_id": "svc_per_tooth",
                "active": True,
                "applies_to_extents": ["one_tooth"],
                "price": {
                    "mode": "fixed",
                    "amount": 42000,
                    "currency": "RUB",
                    "billing_unit": "tooth_package",
                },
                "package": {"label": "per tooth", "includes": []},
            }
        ],
    )
    return root, load_response_schema_bundle(root)


def explicit_lookup_no_public_price_pack(
    tmp_path: Path,
) -> tuple[Path, ResponseSchemaBundle]:
    from core.response_schema_loader import load_response_schema_bundle

    root = build_sparse_target_pack(
        tmp_path,
        services={
            "svc_private": {
                "name": "Private priced protocol",
                "aliases": [],
                "family": "implantology",
                "roles": ["protocol"],
                "active": True,
                "content_ref": "implantation__service__svc_private.md",
                "selection": {"mode": "direct"},
                "options": [],
            },
        },
        offers=[
            {
                "offer_id": "svc_private.no_public",
                "service_id": "svc_private",
                "active": True,
                "price": {
                    "mode": "no_public_price",
                    "approved_text": "Точная цена после консультации и КТ.",
                },
                "package": {"label": "private", "includes": []},
            }
        ],
    )
    return root, load_response_schema_bundle(root)
