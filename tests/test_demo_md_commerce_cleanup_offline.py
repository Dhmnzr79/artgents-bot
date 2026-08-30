"""CP-MD-COMMERCE-1 offline acceptance: demo MD commerce dedupe and cost objection contract."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

from core.one_call_active_service_catalog import ActiveServiceCatalogSnapshot
from core.one_call_client_pack_identity import build_client_pack_identity
from core.one_call_exact_commercial_catalog import ExactCommercialCatalogSnapshot
from core.one_call_fullcontext_messages import build_one_call_stable_prefix
from core.one_call_prompt_contract import (
    ONE_CALL_PROMPT_CONTRACT_VERSION,
    ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS,
)
from core.response_schema_loader import load_response_schema_bundle
from core.service_reference_catalog import ServiceReferenceCatalogSnapshot
from core.target_cached_full_context import build_target_cached_full_context

_DEMO_ROOT = Path("clients/demo")
_MD_ROOT = _DEMO_ROOT / "md"
_TARGET_ROOT = _DEMO_ROOT / "target_response"
_FACTS_PATH = _TARGET_ROOT / "pricebook" / "facts.json"
_MARKETING_PATH = _TARGET_ROOT / "marketing.yaml"

_PAYMENT_TERMS_DOC = _MD_ROOT / "clinic__info__payment_terms.md"
_CONSULTATION_MD = _MD_ROOT / "clinic__info__consultation.md"
_COST_FAQ_MD = _MD_ROOT / "implantation__faq__cost.md"
_TOOTH_LOSS_MD = _MD_ROOT / "implantation__faq__tooth_loss.md"
_CURATOR_MD = _MD_ROOT / "implantation__info__curator.md"
_BENEFITS_MD = _MD_ROOT / "implantation__service__benefits.md"

_COMMERCIAL_DUPLICATE_MARKERS = (
    "13%",
    "13 %",
    "до 15%",
    "рассрочк",
    "налогов",
    "вычет",
    "оплата по этапам",
    "фиксир",
    "бесплатн",
    "31 декабря 2026",
    "скрытых доплат",
)

_SCOPE_DUPLICATE_MARKERS = (
    "опубликованная цена",
    "оплачиваются отдельно",
    "оплачивается отдельно",
    "не цена полного",
    "не цена моста",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_payment_terms_document_removed() -> None:
    assert not _PAYMENT_TERMS_DOC.exists()


def test_facts_have_no_payment_terms_detail_refs() -> None:
    facts = json.loads(_FACTS_PATH.read_text(encoding="utf-8"))
    for fact_id in ("tax_deduction", "installment_12", "payment_stages", "fixed_price"):
        assert "detail_ref" not in facts[fact_id]
    assert facts["free_implant_consult"]["detail_ref"] == "clinic__info__consultation.md#korotko"


def test_free_implant_consult_fact_unchanged() -> None:
    facts = json.loads(_FACTS_PATH.read_text(encoding="utf-8"))
    promo = facts["free_implant_consult"]
    assert "До 31 декабря 2026 — бесплатная консультация" in promo["text_fact"]
    assert "три варианта плана лечения по стоимости" in promo["text_fact"]
    assert "КТ при необходимости оплачивается отдельно" in promo["text_fact"]


def test_consultation_md_is_neutral() -> None:
    raw = _read(_CONSULTATION_MD)
    body = raw.split("---", 2)[2]
    text = body.lower()
    assert "## Консультация" in body
    assert "бесплатн" not in text
    assert "31 декабря 2026" not in text
    assert "три варианта" not in text
    assert "кт оплачивается отдельно" not in text
    assert "20 000" not in text
    assert "20 лет" not in text


def test_cost_faq_keeps_objection_content_without_commercial_duplicates() -> None:
    text = _read(_COST_FAQ_MD).lower()
    assert "я боюсь что имплантация это дорого" in text
    assert "переживаю что лечение окажется слишком дорогим" in text
    assert "понимаем" in text or "беспокойство" in text
    assert "после диагностики" in text
    for marker in _COMMERCIAL_DUPLICATE_MARKERS:
        assert marker not in text, f"unexpected commercial duplicate: {marker}"


def test_tooth_loss_faq_has_no_consult_promo_repeat() -> None:
    text = _read(_TOOTH_LOSS_MD).lower()
    assert "бесплатн" not in text
    assert "три варианта" not in text
    assert "кт оплачивается отдельно" not in text
    assert "подходящие варианты восстановления" in text


def test_curator_md_has_neutral_org_help() -> None:
    text = _read(_CURATOR_MD).lower()
    assert "организацион" in text
    assert "налогов" not in text
    assert "вычет" not in text
    assert "льгот" not in text


def test_benefits_md_removed_3d_service_value_bullet() -> None:
    text = _read(_BENEFITS_MD).lower()
    assert "sv_3d_diagnocat" not in text
    assert "точность до миллиметра" not in text


def test_service_scope_md_files_have_no_offer_duplicates() -> None:
    paths = [
        _MD_ROOT / "implantation__service__pterygoid_implants.md",
        _MD_ROOT / "implantation__service__zygomatic_implants.md",
        _MD_ROOT / "prosthetics__service__implant_supported_prosthetics.md",
        _MD_ROOT / "prosthetics__service__zirconia_crowns.md",
        _MD_ROOT / "comparison__bone_graft_vs_all_on_4.md",
    ]
    for path in paths:
        text = _read(path).lower()
        for marker in _SCOPE_DUPLICATE_MARKERS:
            assert marker not in text, f"{path.name}: unexpected scope duplicate {marker}"


def test_marketing_cost_scenario_has_no_payment_terms_kb_ref() -> None:
    marketing = yaml.safe_load(_MARKETING_PATH.read_text(encoding="utf-8"))
    refs = marketing["scenario_rules"]["cost"]["ordered_amplifier_refs"]
    assert all("payment_terms" not in ref for ref in refs)


def test_prompt_contract_v7_documents_cost_objection_semantics() -> None:
    assert ONE_CALL_PROMPT_CONTRACT_VERSION == 9
    contract = ONE_CALL_TYPED_ENVELOPE_INSTRUCTIONS
    assert "Cost scenario and general cost objection (v7)" in contract
    assert "Я боюсь, что имплантация — это дорого" in contract
    assert "commercial_intent=none" in contract
    assert "Сколько стоит All-on-4?" in contract
    assert "commercial_intent=price" in contract


def test_demo_bundle_and_prefix_still_build_after_md_cleanup() -> None:
    bundle = load_response_schema_bundle(_TARGET_ROOT)
    assert len(bundle.facts) == 10
    active = ActiveServiceCatalogSnapshot.from_bundle(bundle)
    ref = ServiceReferenceCatalogSnapshot.from_bundle(bundle)
    exact = ExactCommercialCatalogSnapshot.from_bundle(bundle)
    corpus = build_target_cached_full_context(_MD_ROOT)
    identity = build_client_pack_identity(client_id="demo")
    prefix = build_one_call_stable_prefix(
        identity=identity,
        cached_full_context=corpus,
        active_service_catalog=active,
        service_reference_catalog=ref,
        exact_commercial_catalog=exact,
    )
    assert "=== EXACT_COMMERCIAL_CATALOG ===" in prefix
    assert "payment_terms" not in prefix
