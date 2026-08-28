from __future__ import annotations

import json
from pathlib import Path

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

LEGACY_MIRROR_PATHS = (
    "service_catalog.json",
    "marketing.yaml",
    "price_brand_aliases.json",
    "pricebook",
)


def _json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_legacy_root_mirrors_are_deleted() -> None:
    for relative in LEGACY_MIRROR_PATHS:
        path = DEMO / relative
        assert not path.exists(), f"legacy mirror must be deleted: {relative}"


def test_target_bundle_is_strict_loadable_product_authority() -> None:
    bundle = load_response_schema_bundle(TARGET)

    assert isinstance(bundle, ResponseSchemaBundle)
    assert len(bundle.services) == 23
    assert len(bundle.offers) == 32
    assert len(bundle.facts) == 10


def test_target_service_catalog_preserves_identity_fields() -> None:
    target = _json(TARGET / "service_catalog.json")
    assert len(target) == 23
    for service_id, record in target.items():
        assert record["name"]
        assert isinstance(record["aliases"], list)
        assert isinstance(record["active"], bool)


def test_target_facts_and_brands_are_canonical() -> None:
    facts = _json(TARGET / "pricebook/facts.json")
    brands = _json(TARGET / "brand_catalog.json")
    assert len(facts) == 10
    assert set(brands["brands"]) == {"implantium", "impro", "nobel_biocare"}


def test_retired_root_marketing_yaml_is_absent() -> None:
    assert not (DEMO / "marketing.yaml").is_file()


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
        "CLIENT_PACK_AUTHORING.md",
        "validate_client_pack.py",
    ):
        assert required in task


def test_checkpoint_b_authoring_artifacts_exist() -> None:
    assert (ROOT / "core/target_client_data.py").is_file()
    assert (ROOT / "core/target_query_cues.py").is_file()
    assert (ROOT / "docs/CLIENT_PACK_AUTHORING.md").is_file()
    assert (ROOT / "scripts/validate_client_pack.py").is_file()
