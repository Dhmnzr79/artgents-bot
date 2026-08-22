"""Offline validation for temporary Stage 5.3 nikadent client pack."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
import yaml

from contracts.doctor_schema_refs import (
    DoctorCatalogExternalIndex,
    validate_doctor_catalog_external_refs,
)
from contracts.exact_sales_resolution import ExactSalesFieldAuthority, ExactSalesResolution
from core.doctor_schema_loader import load_doctor_catalog
from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_commercial_fact_catalog import CommercialFactCatalogSnapshot
from core.one_call_envelope_protocol import dumps_production_envelope, parse_production_envelope_json
from core.response_schema_kb_index import build_response_schema_kb_refs
from core.response_schema_loader import load_response_schema_bundle
from core.sales_one_plus_semantic_authority import bind_semantic_frame, governed_ui_authority_from_resolution
from core.target_client_data import build_compact_service_catalog, clear_target_client_data_cache, load_target_client_data
from core.target_contact_authority import load_clinic_contact_facts
from core.service_availability_presentation import build_availability_overlay
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from scripts.validate_client_pack import validate_client_pack

_NIKADENT = Path(__file__).resolve().parents[1] / "clients" / "nikadent"
_REPO = Path(__file__).resolve().parents[1]
_NIKADENT_COMMERCIAL_CATALOG = CommercialFactCatalogSnapshot.from_bundle(
    load_target_client_data("nikadent").bundle
)
_MD_ROOT = _NIKADENT / "md"
_TARGET = _NIKADENT / "target_response"
_DOCTOR_CATALOG_PATH = _NIKADENT / "doctor_catalog.json"
_OVERVIEW_MD = "doctors__doctor__overview.md"
# OWNER_APPROVED_PROVISIONAL: provisional service_id routing; pending future clinic confirmation.
_OWNER_APPROVED_PROVISIONAL_MAPPINGS = {
    "doctors__doctor__gadzhimuradov": "teeth_treatment",
    "doctors__doctor__kadiev": "classic",
}
_PLACEHOLDER_CONTACT_TOKENS = (
    "+7 (000) 111-22-33",
    "+7 (000) 111-22-34",
    "ул. Никадент",
    "временный placeholder",
    "г. Город",
)

_INACTIVE_KNOWN_NOT_OFFERED = frozenset(
    {
        "braces",
        "aligners",
        "professional_whitening",
        "tomography",
        "zygomatic_implants",
        "pterygoid_implants",
        "sedation",
    }
)

_MD_META_SOURCE_FRAGMENTS = (
    "на сайте",
    "как заявлено",
    "по информации клиники",
    "согласно информации",
    "по данным клиники",
    "по данным базы",
    "в материалах клиники",
    "официальных материалах",
    "владелец подтвердил",
    "owner-approved",
    "owner_approved",
)

_MD_FORBIDDEN_RESIDUE_FRAGMENTS = (
    "делает КТ",
    "КТ при необходимости оплачивается отдельно",
    "централизованное стерилизационное отделение",
    "кварцевание воздуха",
    "протоколы стерильности уровня операционной",
    "исключить риск заражения",
)

_DEMO_RESIDUE_TOKENS = (
    "Тверская",
    "+7 (495) 128-47-60",
    "+7 (916) 842-17-30",
    "Фёдорова",
    "Орлов",
    "Волков",
    "Implantium",
    "implantium",
    "Nobel Biocare",
    "nobel_biocare",
    "Impro",
    "implant_same_day_discount",
    "professional_whitening_discount",
    "free_implant_consult",
    "zygomatic_implants.default",
    "pterygoid_implants.default",
)


def _unknown_exact_sales_resolution() -> ExactSalesResolution:
    authority = ExactSalesFieldAuthority(authority="unknown", provenance="test")
    return ExactSalesResolution(None, None, None, None, None, authority, authority, authority, authority, authority)


def _nikadent_stage51b_catalogs() -> tuple[ActiveServiceCatalogSnapshot, ServiceReferenceCatalogSnapshot]:
    bundle = load_target_client_data("nikadent").bundle
    return (
        ActiveServiceCatalogSnapshot.from_bundle(bundle),
        ServiceReferenceCatalogSnapshot.from_bundle(bundle),
    )


def _read_doctor_md(path: Path) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) == 3
    frontmatter = yaml.safe_load(parts[1]) or {}
    assert isinstance(frontmatter, dict)
    return frontmatter, parts[2]


def _personal_doctor_md_paths() -> list[Path]:
    return sorted(
        [
            path
            for path in _MD_ROOT.glob("doctors__doctor__*.md")
            if path.name != _OVERVIEW_MD
        ],
        key=lambda path: path.name,
    )


def test_nikadent_pack_passes_production_validator() -> None:
    assert validate_client_pack(_NIKADENT) == []


def test_nikadent_bundle_loads_family_prices_without_implant_brand_offers() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    assert len(bundle.family_prices.records) == 4
    implant_ids = {offer.service_id for offer in bundle.offers if offer.service_id in {"classic", "one_stage", "all_on_4", "all_on_6"}}
    assert implant_ids == set()
    assert all(offer.brand_id is None for offer in bundle.offers)


def test_nikadent_inactive_not_offered_services_have_no_content_ref() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    for service_id in _INACTIVE_KNOWN_NOT_OFFERED:
        service = bundle.services[service_id]
        assert service.active is False
        assert service.content_ref is None


def test_nikadent_fixed_bridge_is_active_with_offer_and_content() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    service = bundle.services["fixed_bridge"]
    assert service.active is True
    assert service.content_ref == "prosthetics__service__fixed_bridge.md"
    assert (_MD_ROOT / service.content_ref).is_file()
    offer = next((o for o in bundle.offers if o.offer_id == "fixed_bridge.default"), None)
    assert offer is not None
    assert offer.price.mode == "from"
    assert offer.price.min_amount == 10000
    assert offer.price.currency == "RUB"
    assert offer.price.billing_unit == "unit"


def test_nikadent_core_inlay_is_active_with_offer_and_content() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    service = bundle.services["core_inlay"]
    assert service.active is True
    assert service.content_ref == "prosthetics__service__core_inlay.md"
    assert (_MD_ROOT / service.content_ref).is_file()
    offer = next((o for o in bundle.offers if o.offer_id == "core_inlay.default"), None)
    assert offer is not None
    assert offer.price.mode == "from"
    assert offer.price.min_amount == 7000
    assert offer.price.currency == "RUB"
    assert offer.price.billing_unit == "tooth"


def test_nikadent_ceramic_inlays_remains_separate_from_core_inlay() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    ceramic = bundle.services["ceramic_inlays"]
    core = bundle.services["core_inlay"]
    assert ceramic.active is True
    assert core.active is True
    assert ceramic.content_ref == "prosthetics__service__ceramic_inlays.md"
    assert core.content_ref == "prosthetics__service__core_inlay.md"
    assert ceramic.content_ref != core.content_ref


def test_nikadent_active_service_count_includes_bridge_and_core_inlay() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    active_ids = {sid for sid, svc in bundle.services.items() if svc.active}
    assert "fixed_bridge" in active_ids
    assert "core_inlay" in active_ids
    assert "fixed_bridge" not in _INACTIVE_KNOWN_NOT_OFFERED
    assert len(active_ids) == 24


def test_nikadent_marketing_free_consult_scope_and_priority() -> None:
    marketing = yaml.safe_load((_TARGET / "marketing.yaml").read_text(encoding="utf-8"))
    promos = marketing.get("priority_service_promos") or {}
    assert "classic" not in promos
    assert "one_stage" not in promos
    assert "sinus_lift" not in promos
    assert "bone_graft" not in promos
    for service_id in (
        "all_on_4",
        "all_on_6",
        "removable_dentures",
        "clasp_dentures",
        "implant_supported_prosthetics",
        "zirconia_crowns",
        "metal_ceramic_crowns",
        "fixed_bridge",
        "core_inlay",
    ):
        assert promos[service_id]["ordered_fact_refs"] == ["fact:free_orthopedic_consult"]
    overview = marketing.get("promotion_overview") or {}
    assert overview.get("ordered_fact_refs") == ["fact:free_orthopedic_consult"]

    facts = json.loads((_TARGET / "pricebook" / "facts.json").read_text(encoding="utf-8"))
    allowed = facts["free_orthopedic_consult"]["allowed_service_ids"]
    assert "classic" not in allowed
    assert "one_stage" not in allowed
    assert "fixed_bridge" in allowed
    assert "core_inlay" in allowed


def test_nikadent_owner_content_facts_in_md() -> None:
    md_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(_MD_ROOT.glob("*.md"))
    )
    assert "99,8%" in md_text or "99.8%" in md_text
    assert "16 лет" in md_text
    assert "26 лет" not in md_text
    assert "15%" not in md_text
    assert "31 декабря 2026" not in md_text
    assert "В процессе лечения нет неожиданных доплат" in md_text
    pain_md = (_MD_ROOT / "implantation__faq__pain.md").read_text(encoding="utf-8")
    assert "Лечение под седацией или общим наркозом в клинике не проводится" in pain_md
    assert "внутривенная седация" not in pain_md.casefold()


def test_nikadent_md_has_no_meta_source_phrases() -> None:
    md_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(_MD_ROOT.glob("*.md"))
    ).casefold()
    hits = [frag for frag in _MD_META_SOURCE_FRAGMENTS if frag.casefold() in md_text]
    assert hits == []


def test_nikadent_md_has_no_ct_and_safety_demo_residues() -> None:
    md_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(_MD_ROOT.glob("*.md"))
    ).casefold()
    hits = [frag for frag in _MD_FORBIDDEN_RESIDUE_FRAGMENTS if frag.casefold() in md_text]
    assert hits == []


def test_nikadent_clasp_denture_lock_fixation_is_hidden() -> None:
    body = (_MD_ROOT / "prosthetics__service__clasp_dentures.md").read_text(encoding="utf-8")
    assert "скрытые замковые элементы" in body.casefold()
    assert "снаружи не видны" in body.casefold()


def test_nikadent_removable_denture_owner_facts_present() -> None:
    body = (_MD_ROOT / "prosthetics__service__removable_dentures.md").read_text(encoding="utf-8")
    assert "в первые дни после установки" in body.casefold()
    assert "боль сохраняется дольше недели" in body.casefold()
    assert "мягкой щёткой" in body.casefold()
    assert "рацион можно постепенно расширять" in body.casefold()
    assert "изменении формы дёсен" in body.casefold()
    assert "относительно быстрая и недорогая процедура" in body.casefold()


def test_nikadent_sedation_inactive_known_not_offered_service() -> None:
    bundle = load_response_schema_bundle(_TARGET)
    service = bundle.services["sedation"]
    assert service.active is False
    assert service.content_ref is None
    assert "sedation" in _INACTIVE_KNOWN_NOT_OFFERED
    offer_ids = {offer.offer_id for offer in bundle.offers if offer.service_id == "sedation"}
    assert offer_ids == set()
    facts = json.loads((_TARGET / "pricebook" / "facts.json").read_text(encoding="utf-8"))
    for fact in facts.values():
        assert "sedation" not in fact.get("allowed_service_ids", [])
    family_prices = json.loads((_TARGET / "pricebook" / "family_prices.json").read_text(encoding="utf-8"))
    for record in family_prices.get("records", []):
        assert "sedation" not in record.get("applies_to_service_ids", [])
    marketing = yaml.safe_load((_TARGET / "marketing.yaml").read_text(encoding="utf-8"))
    promos = marketing.get("priority_service_promos") or {}
    assert "sedation" not in promos
    ref_catalog = ServiceReferenceCatalogSnapshot.from_bundle(bundle)
    assert ref_catalog.is_active("sedation") is False


def test_nikadent_clinic_policies_has_no_no_sedation_policy() -> None:
    policies_text = (_NIKADENT / "clinic_policies.yaml").read_text(encoding="utf-8")
    assert "no_sedation" not in policies_text


def test_nikadent_sedation_known_not_offered_overlay_without_alternative() -> None:
    bundle = load_target_client_data("nikadent").bundle
    active_catalog, ref_catalog = _nikadent_stage51b_catalogs()
    envelope_json = dumps_production_envelope(
        patient_text="Можно ли сделать имплантацию под седацией?",
        service_reference_status="resolved",
        requested_service_id="sedation",
        service_id=None,
    )
    envelope = parse_production_envelope_json(
        envelope_json,
        active_service_catalog=active_catalog,
        service_reference_catalog=ref_catalog,
        commercial_fact_catalog=_NIKADENT_COMMERCIAL_CATALOG,
    )
    semantic = bind_semantic_frame(
        envelope=envelope,
        governed_ui=governed_ui_authority_from_resolution(_unknown_exact_sales_resolution()),
        active_service_catalog=active_catalog,
        service_reference_catalog=ref_catalog,
    )
    assert semantic.availability_status == "known_not_offered"
    assert semantic.service_id is None

    overlay = build_availability_overlay(
        client_id="nikadent",
        availability_status=semantic.availability_status,
        requested_service_id="sedation",
        bundle=bundle,
    )
    assert overlay is not None
    assert overlay.not_offered_text is not None
    overlay_text = overlay.not_offered_text.lower()
    assert "не оказывается" in overlay_text
    assert overlay.alternative_texts == ()
    assert "₽" not in overlay.not_offered_text
    assert "%" not in overlay.not_offered_text
    combined = overlay_text + "\n".join(overlay.alternative_texts).casefold()
    assert "бесплатн" not in combined
    assert "скидк" not in combined


def test_nikadent_catalog_is_independent_from_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    clear_target_client_data_cache()
    rows = build_compact_service_catalog("nikadent")
    service_ids = {row["service_id"] for row in rows}
    assert "metal_ceramic_crowns" in service_ids
    assert "prosthetics_consultation" in service_ids
    assert "aligners" not in service_ids
    clear_target_client_data_cache()


def test_nikadent_has_no_demo_residue_tokens() -> None:
    text_blobs: list[str] = []
    for path in sorted(_NIKADENT.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".json", ".yaml", ".yml", ".md"}:
            continue
        text_blobs.append(path.read_text(encoding="utf-8"))
    joined = "\n".join(text_blobs).casefold()
    hits = [token for token in _DEMO_RESIDUE_TOKENS if token.casefold() in joined]
    assert hits == []


def test_nikadent_doctor_catalog_matches_profiles() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    profile_paths = _personal_doctor_md_paths()
    assert len(catalog.doctors) == 5
    assert len(profile_paths) == 5
    assert set(catalog.doctors) == {path.stem for path in profile_paths}


def test_nikadent_owner_approved_provisional_doctor_mappings() -> None:
    """OWNER_APPROVED_PROVISIONAL: not screenshot-confirmed service routing."""
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    for doctor_id, service_id in _OWNER_APPROVED_PROVISIONAL_MAPPINGS.items():
        doctor = catalog.doctors[doctor_id]
        assert doctor.service_ids == [service_id]


def test_nikadent_doctor_profile_refs_resolve() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    bundle = load_response_schema_bundle(_TARGET)
    kb_refs = build_response_schema_kb_refs(_MD_ROOT)
    index = DoctorCatalogExternalIndex(
        service_ids=tuple(bundle.services),
        kb_refs=kb_refs,
    )
    assert validate_doctor_catalog_external_refs(catalog, index) is None


def test_nikadent_doctor_json_and_md_are_consistent() -> None:
    catalog = load_doctor_catalog(_DOCTOR_CATALOG_PATH)
    for path in _personal_doctor_md_paths():
        frontmatter, body = _read_doctor_md(path)
        doctor_id = path.stem
        doctor = catalog.doctors[doctor_id]
        assert frontmatter["doc_id"] == doctor_id
        assert doctor.name == frontmatter["name_full"]
        assert doctor.position == frontmatter["position"]
        assert doctor.experience_years == frontmatter["experience_years"]
        assert doctor.service_ids == frontmatter["services"]
        assert doctor.profile_ref == f"kb:{path.name}#korotko"
        assert re.search(r"^### Коротко \{#korotko\}$", body, flags=re.MULTILINE)
        assert re.search(
            rf"\*\*{doctor.experience_years}\s+(?:лет|года)\*\*",
            body,
        )


def test_nikadent_contacts_use_multibranch_model_without_scalar_composites() -> None:
    policies_text = (_NIKADENT / "clinic_policies.yaml").read_text(encoding="utf-8")
    joined = policies_text.casefold()
    hits = [token for token in _PLACEHOLDER_CONTACT_TOKENS if token.casefold() in joined]
    assert hits == []

    raw = yaml.safe_load(policies_text) or {}
    contact = raw.get("contact") if isinstance(raw.get("contact"), dict) else {}
    assert isinstance(contact.get("branches"), list) and len(contact["branches"]) == 2
    facts = load_clinic_contact_facts("nikadent")
    assert [branch.branch_id for branch in facts.branches] == ["ryabikova", "pogranichnaya"]


def test_nikadent_contacts_md_exists_without_duplicate_facts() -> None:
    contacts_md = _MD_ROOT / "clinic__info__contacts.md"
    assert contacts_md.is_file()
    body = contacts_md.read_text(encoding="utf-8")
    assert "+7" not in body
    assert "елизово" not in body.casefold()


def test_nikadent_wip_files_are_well_formed() -> None:
    paths = [
        _NIKADENT / "clinic_policies.yaml",
        _DOCTOR_CATALOG_PATH,
        Path(__file__).resolve(),
        _REPO / "core" / "clinic_contact_policies.py",
        _REPO / "core" / "target_contact_authority.py",
        _REPO / "tests" / "test_multibranch_contact_authority.py",
    ]
    paths.extend(_personal_doctor_md_paths())
    paths.append(_MD_ROOT / _OVERVIEW_MD)
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert text.endswith("\n")
        for line in text.splitlines():
            assert line == line.rstrip(" \t")
        if path.suffix == ".json":
            json.loads(text)
        if path.suffix in {".yaml", ".yml"}:
            yaml.safe_load(text)
