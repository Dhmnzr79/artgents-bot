"""Sparse second-client target pack loads without legacy mirror files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from core.response_schema_loader import load_response_schema_bundle
from core.target_client_data import (
    allowed_brand_filters,
    build_compact_service_catalog,
    clear_target_client_data_cache,
    match_service_from_target_catalog,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_sparse_pack(tmp_path: Path) -> Path:
    pack = tmp_path / "clients" / "sparse_clinic"
    template = Path(__file__).resolve().parents[1] / "clients" / "_template"
    md = pack / "md"
    md.mkdir(parents=True)
    (md / "whitening__service__teeth_whitening.md").write_text(
        "---\ntopic: whitening\n---\n## Отбеливание\n",
        encoding="utf-8",
    )
    target = pack / "target_response"
    services = {
        "professional_whitening": {
            "name": "Профессиональное отбеливание",
            "aliases": ["отбеливание", "обеливание"],
            "family": "aesthetics",
            "roles": [],
            "active": True,
            "content_ref": "whitening__service__teeth_whitening.md",
            "selection": {"mode": "direct"},
            "options": [],
        }
    }
    _write_json(target / "service_catalog.json", services)
    _write_json(
        target / "brand_catalog.json",
        {
            "version": 1,
            "brands": {
                "local_brand": {
                    "canonical_name": "Local White",
                    "country": "Германия",
                    "aliases": ["локал"],
                }
            },
        },
    )
    _write_json(target / "pricebook" / "facts.json", {})
    _write_json(
        target / "pricebook" / "services" / "professional_whitening.default.json",
        {
            "offer_id": "professional_whitening.default",
            "service_id": "professional_whitening",
            "active": True,
            "brand_id": "local_brand",
            "price": {
                "mode": "fixed",
                "amount": 15000,
                "currency": "RUB",
                "billing_unit": "procedure",
            },
            "package": {"label": "процедура", "includes": []},
            "followups": [],
        },
    )
    _write_json(
        target / "pricebook" / "family_prices.json",
        {"version": 1, "records": []},
    )
    (target / "clinic_strategy.yaml").write_text(
        "version: 1\ndefault_max_options: 3\ndefault_service_priorities: {}\n"
        "default_offer_priorities: {}\nrules: []\n",
        encoding="utf-8",
    )
    (target / "marketing.yaml").write_text(
        "version: 1\nlimits:\n  max_marketing_facts_per_turn: 0\n"
        "  max_amplifiers_per_turn: 0\n  max_scenarios_per_turn: 0\n"
        "initial_commercial_blocks: {}\nscenario_rules: {}\ncta_contexts:\n"
        "  default: callback\n",
        encoding="utf-8",
    )
    _write_json(
        pack / "doctor_catalog.json",
        {
            "doctors": {},
        },
    )
    for name in (
        "brand.yaml",
        "clinic_policies.yaml",
        "features.yaml",
        "lead_config.yaml",
        "tone.yaml",
        "ui.yaml",
        "widget_config.json",
    ):
        (pack / name).write_text((template / name).read_text(encoding="utf-8"), encoding="utf-8")
    return target


def test_sparse_target_pack_loads_without_legacy_mirrors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target_root = _build_sparse_pack(tmp_path)
    bundle = load_response_schema_bundle(target_root)
    assert len(bundle.services) == 1
    assert len(bundle.offers) == 1
    assert bundle.offers[0].brand_id == "local_brand"


def test_sparse_pack_has_no_legacy_mirror_files(tmp_path: Path) -> None:
    pack = _build_sparse_pack(tmp_path).parent
    assert not (pack / "service_catalog.json").exists()
    assert not (pack / "pricebook").exists()
    assert not (pack / "marketing.yaml").exists()
    assert not (pack / "price_brand_aliases.json").exists()


def test_sparse_pack_catalog_match_and_brand_filters(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pack = _build_sparse_pack(tmp_path).parent
    monkeypatch.setattr(
        "core.target_client_data._REPO_ROOT",
        tmp_path,
    )
    monkeypatch.setattr(
        "core.target_client_data.resolve_pack_client_id",
        lambda _client_id: "sparse_clinic",
    )
    clear_target_client_data_cache()

    rows = build_compact_service_catalog("sparse_clinic")
    assert rows == [
        {
            "service_id": "professional_whitening",
            "title": "Профессиональное отбеливание",
            "about": "Профессиональное отбеливание (aesthetics)",
        }
    ]
    groups, brands = allowed_brand_filters("sparse_clinic")
    assert groups == frozenset({"german"})
    assert "local white" in brands

    match = match_service_from_target_catalog(
        "сколько стоит обеливание?",
        client_id="sparse_clinic",
    )
    assert match.get("matched_service_id") == "professional_whitening"
    assert match.get("is_confident") is True

    clear_target_client_data_cache()


def test_sparse_pack_passes_offline_validator(tmp_path: Path) -> None:
    pack = _build_sparse_pack(tmp_path).parent
    from scripts.validate_client_pack import validate_client_pack

    assert validate_client_pack(pack) == []
