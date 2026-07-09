"""Price lookup resolution: service found vs price unavailable."""
from __future__ import annotations

from core.catalog_resolution import (
    fallback_reason_to_resolution,
    first_sentences,
    service_content_snippet,
)
from query_selector import match_service_from_catalog, select_price_service_route
from ux_builder import build_price_resolution_payload


def test_match_implant_supported_prosthetics_cesi():
    m = match_service_from_catalog(
        "Сколько стоит протез на имплантах?",
        client_id="cesi",
    )
    assert m.get("matched_service_id") == "implant_supported_prosthetics"
    assert m.get("is_confident") is True


def test_select_price_route_unavailable_when_no_price():
    pr = select_price_service_route(
        "Сколько стоит протез на имплантах?",
        client_id="cesi",
        sid="test_price_unavailable_implant",
        intent_override="price_lookup",
    )
    assert pr.get("mode") == "unavailable"
    assert pr.get("matched_service_id") == "implant_supported_prosthetics"
    assert pr.get("fallback_reason") == "price_not_in_catalog"


def test_build_price_unavailable_includes_korotko_snippet():
    pr = select_price_service_route(
        "Сколько стоит протез на имплантах?",
        client_id="cesi",
        sid="test_price_unavailable_snippet",
        intent_override="price_lookup",
    )
    payload = build_price_resolution_payload(
        sid="test_price_unavailable_snippet",
        client_id="cesi",
        intent="price_lookup",
        resolution_reason=str(pr.get("fallback_reason") or ""),
        service_id=str(pr.get("matched_service_id") or ""),
        service=pr.get("service") or {},
        match_score=float(pr.get("match_score") or 0.0),
        question="Сколько стоит протез на имплантах?",
    )
    answer = (payload.get("answer") or "").lower()
    meta = payload.get("meta") or {}
    assert meta.get("service_status") == "found"
    assert meta.get("price_status") == "not_available"
    assert meta.get("resolution_reason") == "matched_service_but_no_price"
    assert meta.get("matched_service_id") == "implant_supported_prosthetics"
    assert meta.get("content_snippet_source") == "korotko"
    assert "протезирование на имплантах" in answer
    assert "консультац" in answer
    assert "не могу определить услугу" not in answer
    assert "не вижу такую услугу" not in answer


def test_service_not_found_text():
    payload = build_price_resolution_payload(
        sid="s1",
        client_id="cesi",
        intent="price_lookup",
        resolution_reason="service_not_found",
        question="Сколько стоит услуга xyz-нет-в-каталоге?",
    )
    answer = payload.get("answer") or ""
    assert "администратор" in answer.lower()
    assert "в базе" not in answer.lower()
    meta = payload.get("meta") or {}
    assert meta.get("service_status") == "not_found"


def test_continuation_no_context_text():
    payload = build_price_resolution_payload(
        sid="s2",
        client_id="cesi",
        intent="price_lookup",
        resolution_reason="continuation_no_context",
        question="сколько?",
    )
    assert "о какой услуге" in (payload.get("answer") or "").lower()


def test_low_match_score_with_title():
    payload = build_price_resolution_payload(
        sid="s3",
        client_id="cesi",
        intent="price_lookup",
        resolution_reason="low_match_score",
        service_id="implant_supported_prosthetics",
        service={"title": "Протезирование на имплантах"},
        match_score=0.5,
        question="сколько стоит что-то неясное",
    )
    answer = payload.get("answer") or ""
    assert "протезирование на имплантах" in answer.lower()
    assert (payload.get("meta") or {}).get("service_status") == "ambiguous"


def test_fallback_reason_mapping():
    assert fallback_reason_to_resolution("price_not_in_catalog") == "matched_service_but_no_price"


def test_first_sentences_limits():
    text = "Первое предложение. Второе предложение. Третье предложение."
    assert first_sentences(text, max_sentences=2) == "Первое предложение. Второе предложение."


def test_service_content_snippet_from_facts():
    snippet, src = service_content_snippet(
        {
            "title": "КТ",
            "facts": ["помогает врачу оценить анатомию", "используется для планирования"],
        },
        client_id="cesi",
    )
    assert src == "facts"
    assert "помогает" in snippet.lower()
