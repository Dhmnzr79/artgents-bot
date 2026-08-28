"""Isolated demo-derived client pack for service_value widget/session integration tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from core.target_client_data import clear_target_client_data_cache
from core.target_runtime_client_context import clear_target_runtime_client_context_cache

_DEMO_PACK = Path(__file__).resolve().parents[1] / "clients" / "demo"
CLIENT_ID = "mkt_sv_cycle"
SV_FACT_ID = "sv_shared"
SV_TEXT = "Shared service value sv_shared."


def build_marketing_sv_cycle_pack(tmp_path: Path) -> Path:
    """Copy demo pack into tmp_path and add a shared service_value fact (not demo data)."""

    pack_root = tmp_path / "clients" / CLIENT_ID
    shutil.copytree(_DEMO_PACK, pack_root)
    facts_path = pack_root / "target_response" / "pricebook" / "facts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    facts[SV_FACT_ID] = {
        "id": SV_FACT_ID,
        "kind": "service_value",
        "catalog_label": "SV shared",
        "text_fact": SV_TEXT,
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": ["all_on_4", "all_on_6"],
        "incompatible_with": [],
    }
    facts_path.write_text(
        json.dumps(facts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog_path = pack_root / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    for service_id in ("all_on_4", "all_on_6"):
        catalog[service_id]["service_value_ref"] = f"fact:{SV_FACT_ID}"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return pack_root


def patch_isolated_marketing_sv_repo(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    monkeypatch.setattr("core.target_runtime_client_context._REPO_ROOT", repo)
    monkeypatch.setattr("core.one_call_client_pack_identity._REPO_ROOT", repo)
    monkeypatch.setattr("core.target_client_data._REPO_ROOT", repo)
    monkeypatch.setattr("core.client_runtime._REPO_ROOT", str(repo))
    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()
    from core.topic_taxonomy import clear_topic_taxonomy_cache

    clear_topic_taxonomy_cache()
