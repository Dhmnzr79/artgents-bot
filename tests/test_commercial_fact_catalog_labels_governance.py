from __future__ import annotations

from pathlib import Path

from core.response_schema_loader import load_response_schema_bundle

_DEMO_ROOT = Path("clients/demo/target_response")
_NIKADENT_ROOT = Path("clients/nikadent/target_response")

_DEMO_LABELS = {
    "tax_deduction": "Налоговый вычет за лечение",
    "installment_12": "Рассрочка на лечение",
    "free_implant_consult": "Условия консультации по имплантации и протезированию",
    "implant_warranty": "Гарантия при имплантации",
    "implant_same_day_discount": "Скидка при оплате в день обращения",
    "professional_whitening_discount": "Скидка на профессиональное отбеливание",
}

_NIKADENT_LABELS = {
    "free_orthopedic_consult": "Условия консультации по ортопедии, имплантации и протезированию",
    "tax_deduction": "Налоговый вычет за лечение",
    "work_warranty_1year": "Гарантия на стоматологические работы",
}

_FORBIDDEN_IN_LABELS = (
    "13%",
    "12 месяцев",
    "1 год",
    "5 лет",
    "15%",
    "10%",
    "15 августа",
    "2026-08-15",
    "2026-12-31",
)


def _actual_label_mapping(root: Path) -> dict[str, str]:
    bundle = load_response_schema_bundle(root)
    return {fact_id: fact.catalog_label for fact_id, fact in bundle.facts.items()}


def test_demo_labels_match_approved_mapping() -> None:
    actual = _actual_label_mapping(_DEMO_ROOT)
    assert actual == _DEMO_LABELS
    for label in actual.values():
        assert label.strip()


def test_nikadent_labels_match_approved_mapping() -> None:
    actual = _actual_label_mapping(_NIKADENT_ROOT)
    assert actual == _NIKADENT_LABELS
    for label in actual.values():
        assert label.strip()


def test_catalog_labels_differ_from_text_fact() -> None:
    for root in (_DEMO_ROOT, _NIKADENT_ROOT):
        bundle = load_response_schema_bundle(root)
        for fact in bundle.facts.values():
            assert fact.catalog_label.strip() != fact.text_fact.strip()


def test_catalog_labels_do_not_duplicate_known_mutable_values() -> None:
    for root in (_DEMO_ROOT, _NIKADENT_ROOT):
        bundle = load_response_schema_bundle(root)
        for fact in bundle.facts.values():
            label = fact.catalog_label
            for token in _FORBIDDEN_IN_LABELS:
                assert token not in label
