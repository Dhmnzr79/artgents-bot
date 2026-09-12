"""Catalog containment: channel-aware scoring and topic tie-break."""
from __future__ import annotations

from core.catalog_match import resolve_catalog_match, score_catalog_phrase
from core.target_client_data import match_service_from_target_catalog, service_catalog_dict


def _demo_catalog() -> dict:
    return service_catalog_dict("demo")


def test_typo_only_implant_word_does_not_win_containment() -> None:
    m = match_service_from_target_catalog(
        "Что такое имплантация зубов?",
        client_id="demo",
        service_topic="implantation",
        topic_confidence=0.9,
    )
    assert m.get("matched_service_id") != "tomography"
    assert m.get("containment_eligible") is False


def test_exact_kt_phrase_wins_tomography() -> None:
    m = match_service_from_target_catalog(
        "Нужна ли КТ перед имплантацией?",
        client_id="demo",
        service_topic="implantation",
        topic_confidence=0.9,
    )
    assert m.get("matched_service_id") == "tomography"
    assert m.get("containment_eligible") is True
    assert m.get("match_channel") == "exact"


def test_prosthetics_on_implants_exact_containment() -> None:
    m = match_service_from_target_catalog(
        "Сколько стоит протез на имплантах?",
        client_id="demo",
    )
    assert m.get("matched_service_id") == "implant_supported_prosthetics"
    assert m.get("containment_eligible") is True


def test_typo_obelivanie_still_confident_for_price() -> None:
    m = match_service_from_target_catalog("сколько стоит обеливание?", client_id="default")
    assert m.get("matched_service_id") == "professional_whitening"
    assert m.get("is_confident") is True


def test_golden_14_no_tomography_containment() -> None:
    m = match_service_from_target_catalog(
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


def test_rank_uses_target_catalog_name_field() -> None:
    catalog = {
        "svc": {
            "name": "Профессиональное отбеливание",
            "aliases": ["отбеливание"],
            "active": True,
            "content_ref": "whitening__service__teeth_whitening.md",
        }
    }
    result = resolve_catalog_match(
        "сколько стоит отбеливание",
        catalog,
        strong_match_min=0.5,
    )
    assert result.get("matched_service_id") == "svc"
