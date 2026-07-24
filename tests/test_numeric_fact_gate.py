"""Unit tests for stage-5a numeric fact safety gate."""
from __future__ import annotations

from core.numeric_fact_gate import (
    apply_numeric_fact_gate,
    extract_installment_months,
    extract_percents,
    extract_rub_amounts,
    gate_in_scope,
)


def test_extract_rub_amounts_normalizes_spaces():
    assert extract_rub_amounts("Стоимость **85 200 ₽**") == [85200]
    assert extract_rub_amounts("от 12 500 руб.") == [12500]


def test_extract_percents_and_installment_months():
    assert 0.0 in extract_percents("Рассрочка 0% на 12 месяцев")
    assert extract_installment_months("Рассрочка 0% на 12 месяцев") == [12]
    assert extract_installment_months("Лечение занимает 12 месяцев") == []


def test_gate_skipped_when_feature_disabled(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: False,
    )
    result = apply_numeric_fact_gate(
        answer="Цена 99 999 ₽",
        route="price_lookup",
        meta={"price_offers_applied": True, "price_offer_ids": ["x"]},
        client_id="demo",
        allowed_source_text="85 200 ₽",
    )
    assert result.action == "skipped"
    assert result.answer == "Цена 99 999 ₽"


def test_gate_pass_when_llm_matches_append(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    append = "**Точные цены:**\n\n- Osstem — **85 200 ₽**"
    answer = f"По имплантации.\n\n{append}"
    result = apply_numeric_fact_gate(
        answer=answer,
        route="price_lookup",
        meta={"price_offers_applied": True, "price_offer_ids": ["classic_osstem_one"]},
        client_id="demo",
        allowed_source_text=append,
    )
    assert result.action == "pass"


def test_gate_remove_fact_strips_hallucinated_price(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    append = "**Точные цены:**\n\n- Osstem — **85 200 ₽**"
    answer = (
        "Стоимость имплантации около 120 000 ₽ за один зуб.\n\n"
        f"{append}"
    )
    result = apply_numeric_fact_gate(
        answer=answer,
        route="price_lookup",
        meta={"price_offers_applied": True, "price_offer_ids": ["classic_osstem_one"]},
        client_id="demo",
        allowed_source_text=append,
    )
    assert result.action == "remove_fact"
    assert "120 000" not in result.answer
    assert "85 200" in result.answer


def test_gate_blocked_when_only_bad_price(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    result = apply_numeric_fact_gate(
        answer="Имплантация стоит 120 000 ₽.",
        route="price_lookup",
        meta={"price_offers_applied": True, "price_offer_ids": ["classic_osstem_one"]},
        client_id="demo",
        allowed_source_text="85 200 ₽",
    )
    assert result.action == "blocked"
    assert "консультации" in result.answer


def test_gate_out_of_scope_for_plain_content(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    result = apply_numeric_fact_gate(
        answer="Обычно процедура занимает 6 месяцев.",
        route="retrieval_chunk",
        meta={},
        client_id="demo",
        allowed_source_text=None,
    )
    assert result.action == "skipped"


def test_gate_in_scope_with_deterministic_append():
    assert gate_in_scope(
        route="retrieval_chunk",
        meta={},
        allowed_source_text="Рассрочка 0% на 12 месяцев",
    )


def test_gate_pass_percent_from_knowledge_base_whitelist(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    kb = "Можно оформить налоговый вычет — государство возвращает 13% от стоимости лечения."
    answer = "Также можно вернуть 13% через налоговый вычет."
    result = apply_numeric_fact_gate(
        answer=answer,
        route="content",
        meta={},
        client_id="demo",
        allowed_source_text=kb,
    )
    assert result.action == "pass"
    assert "13%" in result.answer


def test_gate_remove_hallucinated_percent_with_kb_whitelist(monkeypatch):
    monkeypatch.setattr(
        "core.numeric_fact_gate.numeric_fact_gate_enabled",
        lambda _cid: True,
    )
    kb = "Можно оформить налоговый вычет — государство возвращает 13% от стоимости лечения."
    answer = "Сейчас действует скидка 25% на все услуги."
    result = apply_numeric_fact_gate(
        answer=answer,
        route="content",
        meta={},
        client_id="demo",
        allowed_source_text=kb,
    )
    assert result.action == "blocked"
    assert "25%" not in result.answer
