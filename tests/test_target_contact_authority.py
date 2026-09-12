"""Unit tests for typed clinic contact PRIMARY_EVIDENCE blocks."""

from __future__ import annotations

from pathlib import Path

import pytest

from core.target_contact_authority import (
    canonical_contact_phone,
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


def test_canonical_contact_scalar_matches_policy() -> None:
    from core.target_contact_authority import canonical_contact_scalar, normalize_contact_scalar

    scalar = canonical_contact_scalar("address", "demo")
    assert scalar
    assert "Тверская" in scalar
    assert normalize_contact_scalar(scalar) in normalize_contact_scalar(
        f"Мы находимся по адресу {scalar}"
    )


def test_load_clinic_contact_facts_none_returns_empty_without_demo_default() -> None:
    from core.target_contact_authority import load_clinic_contact_facts

    facts = load_clinic_contact_facts(None)
    assert facts.phone_display == ""
    assert facts.branches == ()
    assert canonical_contact_phone(None) == ""


def test_serialize_clinic_contact_authority_block_demo_all_fields() -> None:
    from core.target_contact_authority import serialize_clinic_contact_authority_block

    block = serialize_clinic_contact_authority_block("demo")
    assert "<CLINIC_CONTACT_AUTHORITY>" in block
    assert "+7 (495) 128-47-60" in block
    assert "+7 (916) 842-17-30" in block
    assert "Тверская" in block
    assert "парковка" in block.casefold() or "parking" in block


def test_serialize_clinic_contact_authority_block_none_is_empty() -> None:
    from core.target_contact_authority import serialize_clinic_contact_authority_block

    assert serialize_clinic_contact_authority_block(None) == ""
    assert serialize_clinic_contact_authority_block("") == ""


def test_partial_contact_without_phone_still_serializes_known_fields(monkeypatch) -> None:
    from core.clinic_contact_policies import ClinicContactFacts
    from core.target_contact_authority import (
        build_clinic_contact_authority_payload,
        serialize_clinic_contact_authority_block,
    )

    facts = ClinicContactFacts(
        phone_display="",
        whatsapp_display="+7 (916) 842-17-30",
        address_display="г. Москва, ул. Тверская, 12",
        hours_display="Пн–Пт 09:00–21:00",
        parking_display=None,
    )
    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts",
        lambda _client_id: facts,
    )
    payload = build_clinic_contact_authority_payload("demo")
    assert payload["contacts_available"] is True
    contact = payload["contact"]
    assert isinstance(contact, dict)
    assert "phone" not in contact
    assert contact["whatsapp"] == "+7 (916) 842-17-30"
    assert "Тверская" in contact["address"]
    block = serialize_clinic_contact_authority_block("demo")
    assert "<CLINIC_CONTACT_AUTHORITY>" in block
    assert "+7 (916) 842-17-30" in block


def test_load_clinic_contact_facts_handles_missing_file(tmp_path, monkeypatch) -> None:
    from core.target_contact_authority import load_clinic_contact_facts

    monkeypatch.setattr("core.target_contact_authority._REPO_ROOT", tmp_path)
    facts = load_clinic_contact_facts("demo")
    assert facts.phone_display == ""
    assert facts.branches == ()


def test_load_clinic_contact_facts_handles_read_error(tmp_path, monkeypatch) -> None:
    from core.target_contact_authority import load_clinic_contact_facts

    policies_dir = tmp_path / "clients" / "demo"
    policies_dir.mkdir(parents=True)
    policies_file = policies_dir / "clinic_policies.yaml"
    policies_file.write_text("contact:\n  phone_display: '+7 (495) 000-00-00'\n", encoding="utf-8")
    monkeypatch.setattr("core.target_contact_authority._REPO_ROOT", tmp_path)

    def _fail_read(self: object, *args: object, **kwargs: object) -> str:
        raise OSError("read denied")

    monkeypatch.setattr(Path, "read_text", _fail_read)
    facts = load_clinic_contact_facts("demo")
    assert facts.phone_display == ""


def test_load_clinic_contact_facts_handles_corrupt_yaml(tmp_path, monkeypatch) -> None:
    from core.target_contact_authority import load_clinic_contact_facts

    policies_dir = tmp_path / "clients" / "demo"
    policies_dir.mkdir(parents=True)
    policies_file = policies_dir / "clinic_policies.yaml"
    policies_file.write_text("contact: [unclosed", encoding="utf-8")
    monkeypatch.setattr("core.target_contact_authority._REPO_ROOT", tmp_path)
    facts = load_clinic_contact_facts("demo")
    assert facts.phone_display == ""


def test_load_clinic_contact_facts_reraises_non_contact_errors(monkeypatch) -> None:
    from core.target_contact_authority import load_clinic_contact_facts

    def _boom(_path: object) -> object:
        raise RuntimeError("unexpected subsystem failure")

    monkeypatch.setattr(
        "core.target_contact_authority.load_clinic_contact_facts_from_policies_path",
        _boom,
    )
    with pytest.raises(RuntimeError, match="unexpected subsystem failure"):
        load_clinic_contact_facts("demo")
