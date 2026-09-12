"""Demo data correction checks for bone_graft service promotion."""

from __future__ import annotations

from pathlib import Path

from core.target_client_data import match_service_from_target_catalog
from core.response_schema_loader import load_response_schema_bundle

_REPO_ROOT = Path(__file__).resolve().parents[1]
_TARGET = _REPO_ROOT / "clients" / "demo" / "target_response"
_MD = _REPO_ROOT / "clients" / "demo" / "md"


def test_bone_graft_md_renamed_to_service_doc() -> None:
    assert not (_MD / "implantation__info__bone_graft.md").exists()
    service_md = _MD / "implantation__service__bone_graft.md"
    assert service_md.is_file()
    text = service_md.read_text(encoding="utf-8")
    assert "doc_id: implantation__service__bone_graft" in text
    assert "doc_type: service" in text


def test_bone_graft_explicit_service_match() -> None:
    match = match_service_from_target_catalog(
        "Что такое костная пластика?",
        client_id="demo",
    )
    assert match is not None
    assert match["matched_service_id"] == "bone_graft"


def test_bone_graft_no_public_price_offer() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    offer = next(offer for offer in bundle.offers if offer.service_id == "bone_graft")
    assert offer.price.mode == "no_public_price"
    assert "Стоимость костной пластики" in offer.price.approved_text


def test_catalog_counts_updated() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    assert len(bundle.services) == 22
    assert len(bundle.offers) == 32
