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
    assert len(blocks) == 5
    refs = {block.ref for block in blocks}
    assert refs == {
        "clinic_contact:phone",
        "clinic_contact:whatsapp",
        "clinic_contact:address",
        "clinic_contact:hours",
        "clinic_contact:parking",
    }
    for block in blocks:
        assert block.kind == "clinic_contact"
        assert block.must_preserve_exact is True
    phone_block = next(block for block in blocks if block.ref == "clinic_contact:phone")
    assert canonical_contact_phone("demo") in phone_block.text


def test_address_aspect_filters_lines() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", aspect="contact_address")
    assert len(blocks) == 1
    text = blocks[0].text
    assert "Адрес:" in text
    assert "Режим работы:" not in text
