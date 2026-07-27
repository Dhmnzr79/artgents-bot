"""Offline tests for clinic_contact PRIMARY_EVIDENCE materialization."""

from __future__ import annotations

from core.target_contact_authority import (
    canonical_contact_phone,
    load_clinic_contact_facts,
    materialize_clinic_contact_primary_evidence,
)


def test_contact_facts_from_clinic_policies_only() -> None:
    facts = load_clinic_contact_facts("demo")
    assert facts.phone_display == "+7 (495) 128-47-60"
    assert facts.address_display
    assert facts.hours_display
    assert facts.whatsapp_display


def test_clinic_contact_evidence_kind_and_exact_text() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", aspect="contacts")
    assert len(blocks) == 1
    block = blocks[0]
    assert block.kind == "clinic_contact"
    assert block.ref == "clinic_contact:canonical"
    assert block.must_preserve_exact is True
    assert canonical_contact_phone("demo") in block.text


def test_address_aspect_filters_lines() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", aspect="address")
    text = blocks[0].text
    assert "Адрес:" in text
    assert "Режим работы:" not in text
