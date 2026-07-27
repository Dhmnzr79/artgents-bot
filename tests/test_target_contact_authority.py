"""Unit tests for typed clinic contact PRIMARY_EVIDENCE blocks."""

from __future__ import annotations

from core.target_contact_authority import (
    contact_fields_from_turn_aspects,
    materialize_clinic_contact_primary_evidence,
)


def test_address_only_evidence_block() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", fields=("address",))
    assert len(blocks) == 1
    assert blocks[0].ref == "clinic_contact:address"
    assert blocks[0].text.startswith("Адрес:")
    assert "Телефон:" not in blocks[0].text


def test_parking_only_evidence_block() -> None:
    blocks = materialize_clinic_contact_primary_evidence("demo", fields=("parking",))
    assert len(blocks) == 1
    assert blocks[0].ref == "clinic_contact:parking"
    assert "Парковка:" in blocks[0].text
    assert "Адрес:" not in blocks[0].text


def test_mixed_address_parking_fields() -> None:
    fields = contact_fields_from_turn_aspects(
        ("contact_address", "contact_parking"),
        primary_aspect="contact_address",
    )
    assert fields == ("address", "parking")
    blocks = materialize_clinic_contact_primary_evidence("demo", fields=fields)
    refs = {block.ref for block in blocks}
    assert refs == {"clinic_contact:address", "clinic_contact:parking"}


def test_general_contacts_returns_all_fields() -> None:
    fields = contact_fields_from_turn_aspects(("contacts",), primary_aspect="contacts")
    assert fields is not None
    blocks = materialize_clinic_contact_primary_evidence("demo", fields=fields)
    assert len(blocks) >= 3
