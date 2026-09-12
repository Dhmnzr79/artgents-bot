"""clients/_template scaffold validates without demo-specific IDs."""

from __future__ import annotations

from pathlib import Path

from scripts.validate_client_pack import validate_client_pack

_TEMPLATE = Path(__file__).resolve().parents[1] / "clients" / "_template"

_FORBIDDEN_DEMO_TOKENS = (
    "all_on_4",
    "nobel_biocare",
    "implantium",
    "classic",
    "zygomatic_implants",
)


def test_template_validates_in_scaffold_mode() -> None:
    errors = validate_client_pack(_TEMPLATE, scaffold=True)
    assert errors == []


def test_template_uses_placeholder_ids_not_demo() -> None:
    catalog = (_TEMPLATE / "target_response" / "service_catalog.json").read_text(encoding="utf-8")
    brands = (_TEMPLATE / "target_response" / "brand_catalog.json").read_text(encoding="utf-8")
    for token in _FORBIDDEN_DEMO_TOKENS:
        assert token not in catalog
        assert token not in brands
    assert "sample_service" in catalog
    assert "template_brand" in brands


def test_template_has_canonical_structure() -> None:
    required = [
        "target_response/service_catalog.json",
        "target_response/brand_catalog.json",
        "target_response/marketing.yaml",
        "target_response/clinic_strategy.yaml",
        "target_response/pricebook/facts.json",
        "target_response/pricebook/services/sample_service.default.json",
        "doctor_catalog.json",
        "clinic_policies.yaml",
        "ui.yaml",
        "brand.yaml",
        "features.yaml",
        "lead_config.yaml",
        "tone.yaml",
        "widget_config.json",
        "md/sample__service__example.md",
    ]
    for rel in required:
        assert (_TEMPLATE / rel).is_file(), rel
