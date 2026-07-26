from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from contracts.response_schema import ResponseSchemaBundle
from core.response_schema_loader import load_response_schema_bundle


ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / "clients" / "demo"
TARGET = DEMO / "target_response"
AUDIT = (
    ROOT
    / "docs"
    / "evidence"
    / "client_pack"
    / "FINAL_CLIENT_PACK_DATA_CONVERGENCE_SEAM_AUDIT.md"
)
TASK = ROOT / "TASK.md"

LEGACY_SHA256 = {
    "service_catalog.json": (
        "2089fde05d832df83cfcb5561165b170152c4cd8d02c775acebd1984b50728de"
    ),
    "marketing.yaml": (
        "e958fcd14be057a3e9867ec133175f4024f90178fbfedec8d3d1421f8e2c1eae"
    ),
    "price_brand_aliases.json": (
        "c6541d0cd2ecd526b25302f55f8fce4451f78a8d4e152ce523efc0d342c9c8f8"
    ),
    "pricebook/facts.json": (
        "fa94c72de8c936fffdc50998c0f761fd75adbafee7569f77dfe30771f55dd612"
    ),
    "pricebook/manifest.json": (
        "1611d97a89d74e101d66b78acb20fc86b166b0eaf508b6b3ab6fc68a3970e555"
    ),
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_governance_checkpoint_keeps_legacy_sources_byte_identical() -> None:
    for relative, expected in LEGACY_SHA256.items():
        path = DEMO / relative
        assert path.is_file()
        assert _sha256(path) == expected

    assert len(list((DEMO / "pricebook/services").glob("*.json"))) == 21
    assert len(list((TARGET / "pricebook/services").glob("*.json"))) == 31


def test_target_bundle_is_already_strict_loadable_product_authority() -> None:
    bundle = load_response_schema_bundle(TARGET)

    assert isinstance(bundle, ResponseSchemaBundle)
    assert len(bundle.services) == 21
    assert len(bundle.offers) == 31
    assert len(bundle.facts) == 6


def test_service_identity_is_preserved_in_target_catalog() -> None:
    legacy = _json(DEMO / "service_catalog.json")
    target = _json(TARGET / "service_catalog.json")

    assert list(legacy) == list(target)
    for service_id, old in legacy.items():
        new = target[service_id]
        assert new["name"] == old["title"]
        assert new["aliases"] == old["aliases"]
        assert new["active"] is old["active"]
        old_ref = old.get("md_entry_ref")
        if old_ref is None:
            assert "content_ref" not in new
        else:
            assert new["content_ref"] == f"{old_ref}.md"


def test_facts_and_brand_aliases_are_preserved_in_target_schema() -> None:
    legacy_facts = _json(DEMO / "pricebook/facts.json")["facts"]
    target_facts = _json(TARGET / "pricebook/facts.json")
    assert list(legacy_facts) == list(target_facts)
    for fact_id, old in legacy_facts.items():
        new = target_facts[fact_id]
        for field in ("id", "kind", "text_fact", "render_mode"):
            assert new[field] == old[field]
        assert new.get("detail_ref") == old.get("detail_ref")

    old_aliases = _json(DEMO / "price_brand_aliases.json")["brand_aliases"]
    brands = _json(TARGET / "brand_catalog.json")["brands"]
    target_alias_pairs = {
        alias: record["canonical_name"]
        for record in brands.values()
        for alias in record["aliases"]
    }
    canonical_name_pairs = {
        record["canonical_name"].lower(): record["canonical_name"]
        for record in brands.values()
    }
    assert old_aliases == target_alias_pairs | canonical_name_pairs


def test_old_marketing_free_text_is_not_silently_promoted_to_target_facts() -> None:
    legacy = yaml.safe_load((DEMO / "marketing.yaml").read_text(encoding="utf-8"))
    target_facts = _json(TARGET / "pricebook/facts.json")
    free_strings = {
        text
        for entry in legacy["service_marketing"].values()
        for field in ("clinic_proof", "consult_reasons")
        for text in entry.get(field, [])
    }

    assert len(free_strings) == 24
    assert free_strings.isdisjoint(
        {record["text_fact"] for record in target_facts.values()}
    )


def test_audit_and_task_define_one_authority_and_two_checkpoint_stop_law() -> None:
    audit = AUDIT.read_text(encoding="utf-8")
    task = TASK.read_text(encoding="utf-8")

    for required in (
        "один authoring source на домен",
        "Checkpoint A — reader convergence",
        "Checkpoint B — deletion and authoring closeout",
        "clients/{client_id}/target_response/**",
        "24 свободные строки",
        "NO LIVE / NO LLM / NO A9 tuning",
    ):
        assert required in audit
    for required in (
        "FINAL_CLIENT_PACK_DATA_CONVERGENCE",
        "Checkpoint A",
        "Checkpoint B",
        "separate owner GO",
    ):
        assert required in task


def test_implementation_has_not_started_at_governance_checkpoint() -> None:
    assert not (ROOT / "core/target_client_data.py").exists()
    assert not (ROOT / "docs/CLIENT_PACK_AUTHORING.md").exists()
    assert not (ROOT / "scripts/validate_client_pack.py").exists()
