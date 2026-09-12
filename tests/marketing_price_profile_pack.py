"""Isolated demo-derived pack for full price-profile widget integration tests."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import yaml

from core.target_client_data import clear_target_client_data_cache
from core.target_runtime_client_context import clear_target_runtime_client_context_cache

_DEMO_PACK = Path(__file__).resolve().parents[1] / "clients" / "demo"
CLIENT_ID = "mkt_price_profile"
SERVICE_ID = "all_on_4"
SV_FACT_ID = "sv_price_test"
SV_TEXT = "PRICE_PROFILE_SV_TEXT_UNIQUE."
PROMO_A_ID = "promo_price_a"
PROMO_B_ID = "promo_price_b"
PROMO_A_TEXT = "PRICE_PROFILE_PROMO_A_UNIQUE."
PROMO_B_TEXT = "PRICE_PROFILE_PROMO_B_UNIQUE."
AMP_IDS = ("amp_price_1", "amp_price_2", "amp_price_3", "amp_price_4")
AMP_TEXTS = (
    "PRICE_PROFILE_AMP_1_UNIQUE.",
    "PRICE_PROFILE_AMP_2_UNIQUE.",
    "PRICE_PROFILE_AMP_3_UNIQUE.",
    "PRICE_PROFILE_AMP_4_UNIQUE.",
)
PRICE_MAIN_TEXT = "All-on-4 на нижнюю челюсть — 368 000 ₽."


def build_marketing_price_profile_pack(tmp_path: Path) -> Path:
    pack_root = tmp_path / "clients" / CLIENT_ID
    shutil.copytree(_DEMO_PACK, pack_root)
    facts_path = pack_root / "target_response" / "pricebook" / "facts.json"
    facts = json.loads(facts_path.read_text(encoding="utf-8"))
    facts[SV_FACT_ID] = {
        "id": SV_FACT_ID,
        "kind": "service_value",
        "catalog_label": "SV price profile",
        "text_fact": SV_TEXT,
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": [SERVICE_ID],
        "incompatible_with": [],
    }
    facts[PROMO_A_ID] = {
        "id": PROMO_A_ID,
        "kind": "promo",
        "catalog_label": "Promo A price profile",
        "text_fact": PROMO_A_TEXT,
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": [SERVICE_ID],
        "incompatible_with": [],
    }
    facts[PROMO_B_ID] = {
        "id": PROMO_B_ID,
        "kind": "promo",
        "catalog_label": "Promo B price profile",
        "text_fact": PROMO_B_TEXT,
        "render_mode": "strict",
        "active": True,
        "allowed_service_ids": [SERVICE_ID],
        "incompatible_with": [],
    }
    for amp_id, amp_text in zip(AMP_IDS, AMP_TEXTS, strict=True):
        facts[amp_id] = {
            "id": amp_id,
            "kind": "benefit",
            "catalog_label": amp_id,
            "text_fact": amp_text,
            "render_mode": "strict",
            "active": True,
            "allowed_service_ids": [SERVICE_ID],
            "incompatible_with": [],
        }
    facts_path.write_text(
        json.dumps(facts, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    catalog_path = pack_root / "target_response" / "service_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    catalog[SERVICE_ID]["service_value_ref"] = f"fact:{SV_FACT_ID}"
    catalog_path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    marketing_path = pack_root / "target_response" / "marketing.yaml"
    marketing = yaml.safe_load(marketing_path.read_text(encoding="utf-8"))
    marketing["limits"] = {
        "max_scenarios_per_turn": 2,
        "service": {"max_promos_per_turn": 2, "max_amplifiers_per_turn": 2},
        "price": {"max_promos_per_turn": 2, "max_amplifiers_per_turn": 4},
    }
    marketing["initial_commercial_blocks"] = {
        "service": {
            "ordered_fact_refs": [
                f"fact:{PROMO_A_ID}",
                f"fact:{PROMO_B_ID}",
            ],
        }
    }
    marketing["ordered_amplifier_refs"] = [f"fact:{amp_id}" for amp_id in AMP_IDS]
    marketing["service_automatic_commercial"] = {
        SERVICE_ID: {
            "service": {
                "ordered_promo_refs": [f"fact:{PROMO_A_ID}"],
                "ordered_amplifier_refs": [f"fact:{AMP_IDS[0]}", f"fact:{AMP_IDS[1]}"],
            },
            "price": {
                "ordered_promo_refs": [f"fact:{PROMO_A_ID}", f"fact:{PROMO_B_ID}"],
                "ordered_amplifier_refs": [f"fact:{amp_id}" for amp_id in AMP_IDS],
            },
        }
    }
    marketing_path.write_text(
        yaml.safe_dump(marketing, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    return pack_root


def patch_isolated_marketing_price_repo(monkeypatch: pytest.MonkeyPatch, repo: Path) -> None:
    monkeypatch.setattr("core.target_runtime_client_context._REPO_ROOT", repo)
    monkeypatch.setattr("core.one_call_client_pack_identity._REPO_ROOT", repo)
    monkeypatch.setattr("core.target_client_data._REPO_ROOT", repo)
    monkeypatch.setattr("core.client_runtime._REPO_ROOT", str(repo))
    clear_target_client_data_cache()
    clear_target_runtime_client_context_cache()
    from core.topic_taxonomy import clear_topic_taxonomy_cache

    clear_topic_taxonomy_cache()
