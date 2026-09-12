from __future__ import annotations

from orchestration.sales_one_plus_ask_turn import _contact_aspects_from_message


def test_parking_question_maps_to_single_contact_aspect() -> None:
    aspects = _contact_aspects_from_message("Есть ли парковка?")
    assert aspects == ("contact_parking",)


def test_address_question_maps_to_single_contact_aspect() -> None:
    aspects = _contact_aspects_from_message("А где вы находитесь?")
    assert aspects == ("contact_address",)


def test_broad_contacts_without_proven_field_passes_to_flash() -> None:
    assert _contact_aspects_from_message("как с вами связаться?") is None


def test_explicit_general_contacts_aspect() -> None:
    aspects = _contact_aspects_from_message("контакты клиники")
    assert aspects == ("contacts",)
