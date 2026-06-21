from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.pricebook import (
    PricebookManifest,
    PricebookServiceEntry,
    PricingFactsFile,
    PriceAnswerPlan,
)

ROOT = Path(__file__).resolve().parents[1]
DEMO_PB = ROOT / "clients" / "demo" / "pricebook"


def test_demo_pricebook_manifest_validates():
    raw = json.loads((DEMO_PB / "manifest.json").read_text(encoding="utf-8"))
    m = PricebookManifest.model_validate(raw)
    assert "implantation" in m.groups
    assert "full_jaw" in m.groups
    assert len(m.groups["implantation"].members) >= 3


def test_demo_pricebook_facts_validates():
    raw = json.loads((DEMO_PB / "facts.json").read_text(encoding="utf-8"))
    f = PricingFactsFile.model_validate(raw)
    assert "tax_deduction" in f.facts
    assert f.facts["tax_deduction"].render_mode == "strict"
    assert f.facts["free_implant_consult"].render_mode == "natural"
    assert "13%" in f.facts["tax_deduction"].text_fact


def test_price_answer_plan_complex_scenario():
    plan = PriceAnswerPlan(
        scenario="complex",
        service_id="classic",
        unit="one_tooth",
        blocks=["intro", "price_table", "stages", "includes", "fact_refs", "closer", "followups"],
        fact_refs=["free_implant_consult"],
        llm_intro=True,
        llm_closer=True,
    )
    assert plan.scenario == "complex"


def test_pricebook_service_entry_complex_example():
    entry = PricebookServiceEntry.model_validate(
        {
            "service_id": "classic",
            "price_model": "complex",
            "display_name": "Классическая имплантация",
            "default_unit": "one_tooth",
            "variants": [
                {
                    "offer_id": "classic.one_tooth.impro",
                    "brand": "Impro",
                    "brand_label": "Impro (Германия)",
                    "unit": "one_tooth",
                    "total": 85200,
                    "recommended": True,
                    "payment_stages": [],
                    "includes": ["имплант", "коронка"],
                    "excludes": [],
                }
            ],
            "fact_refs": ["free_implant_consult"],
            "followups": [
                {
                    "label": "Что на консультации",
                    "action": "md_ref",
                    "ref": "clinic__info__consultation.md#korotko",
                }
            ],
        }
    )
    assert entry.price_model == "complex"
    assert entry.variants[0].total == 85200
