"""Catalog containment: channel-aware scoring and topic tie-break."""
from __future__ import annotations

from core.catalog_match import resolve_catalog_match, score_catalog_phrase
from query_selector import (
    _read_json_dict,
    _client_json_path,
    match_service_from_catalog,
)


def _demo_catalog() -> dict:
    return _read_json_dict(_client_json_path("demo", "service_catalog.json"))


def test_typo_only_implant_word_does_not_win_containment() -> None:
    m = match_service_from_catalog(
        "Что такое имплантация зубов?",
        client_id="demo",
        service_topic="implantation",
        topic_confidence=0.9,
    )
    assert m.get("matched_service_id") != "tomography"
    assert m.get("containment_eligible") is False


def test_exact_kt_phrase_wins_tomography() -> None:
    m = match_service_from_catalog(
        "Нужна ли КТ перед имплантацией?",
        client_id="demo",
        service_topic="implantation",
        topic_confidence=0.9,
    )
    assert m.get("matched_service_id") == "tomography"
    assert m.get("containment_eligible") is True
    assert m.get("match_channel") == "exact"


def test_prosthetics_on_implants_exact_containment() -> None:
    m = match_service_from_catalog(
        "Сколько стоит протез на имплантах?",
        client_id="demo",
    )
    assert m.get("matched_service_id") == "implant_supported_prosthetics"
    assert m.get("containment_eligible") is True


def test_typo_obelivanie_still_confident_for_price() -> None:
    m = match_service_from_catalog("сколько стоит обеливание?", client_id="default")
    assert m.get("matched_service_id") == "professional_whitening"
    assert m.get("is_confident") is True


def test_golden_14_no_tomography_containment() -> None:
    m = match_service_from_catalog(
        "Что сначала: КТ, удаление, лечение дёсен или имплантация?",
        client_id="demo",
        service_topic="implantation",
        topic_confidence=0.9,
    )
    assert m.get("matched_service_id") != "tomography"
    assert m.get("containment_eligible") is False


def test_score_catalog_phrase_typo_alone_not_containment() -> None:
    pm = score_catalog_phrase("Сколько стоит имплантация?", "классическая имплантация")
    assert pm.channel == "typo"
    assert pm.containment_ok is False
