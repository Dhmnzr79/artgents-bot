"""Price presentation preserves frozen facts, differences and click receipts."""
from types import SimpleNamespace

import pytest

from contracts.response_plan import D2FrozenPriceDetailBlock, D2FrozenPriceDetailRow, D2FrozenPriceRow, SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.response_text_renderer import _render_d2_price_detail, _render_compact_price_group
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price


def row(offer, **fields):
    return D2FrozenPriceDetailRow(source_client_id="demo", offer_id=offer,
        service_id="service", service_name="Услуга", label=f"Услуга — {offer}", **fields)


def render(aspect, *rows):
    block = D2FrozenPriceDetailBlock(source_client_id="demo", request_id="r1", aspect=aspect, rows=rows)
    before = block.model_dump()
    parts = []
    _render_d2_price_detail(SimpleNamespace(d2_price_detail_block=block), parts)
    assert block.model_dump() == before
    return "\n\n".join(parts)


def test_single_package_has_one_identity_and_keeps_every_exclusion():
    answer = render("includes", row("A", includes=("Процедура", "Контроль через 3–6 месяцев"),
                                   excludes=("КТ по показаниям",)))
    assert answer.count("Услуга — A") == 1
    assert "Что входит" not in answer
    assert "В стоимость входят:" in answer
    assert "В эту стоимость не входят:" in answer
    for text in ("Процедура", "Контроль через 3–6 месяцев", "КТ по показаниям"):
        assert answer.count(text) == 1
    assert "оплачиваются отдельно" not in answer


@pytest.mark.parametrize("different", ["includes", "excludes", None])
def test_common_package_does_not_hide_variant_differences(different):
    a = row("A", includes=("Общий пункт",), excludes=("Общее исключение",))
    b = row("B", includes=("Общий пункт", "Дополнительный пункт") if different == "includes" else a.includes,
            excludes=("Общее исключение", "Особое исключение") if different == "excludes" else a.excludes)
    answer = render("includes", a, b)
    assert answer.count("Общий пункт") == answer.count("Общее исключение") == 1
    if different:
        assert "Состав одинаковый" not in answer
        assert "Во все эти варианты входят:" in answer
        assert "Услуга — B" in answer
        assert ("Дополнительный пункт" if different == "includes" else "Особое исключение") in answer
    else:
        assert "Состав одинаковый для всех этих вариантов:" in answer


def test_missing_package_does_not_claim_its_contents_match():
    answer = render("includes", row("A", includes=("Известный пункт",)), row("B", missing=True))
    assert "Состав одинаковый" not in answer and "Во все эти варианты" not in answer
    assert "Известный пункт" in answer
    assert answer.index("Услуга — B") < answer.index("Для этого варианта состав не указан.")


@pytest.mark.parametrize("other", ["same", "different", "missing"])
def test_payment_grouping_preserves_amount_timing_and_missing_variant(other):
    stage = "Первый этап — 10 000 ₽. В день операции"
    a = row("A", stages=(stage,))
    b = row("B", missing=True) if other == "missing" else row("B", stages=(
        stage if other == "same" else "Первый этап — 20 000 ₽. После приживления",))
    answer = render("stages", a, b)
    assert answer.count(stage) == 1
    if other == "same":
        assert "Порядок оплаты одинаковый" in answer
    else:
        assert "Порядок оплаты одинаковый" not in answer
        assert "Услуга — B" in answer
        assert ("20 000 ₽. После приживления" if other == "different"
                else "Для этого варианта порядок оплаты не указан.") in answer


@pytest.mark.parametrize("mode,text,metadata", [
    ("fixed", "10 000 ₽", {"amount": 10000}),
    ("from", "от 10 000 ₽", {"min_amount": 10000}),
    ("range", "10 000–20 000 ₽", {"min_amount": 10000, "max_amount": 20000}),
    ("no_public_price", "Стоимость уточняется после осмотра.",
     {"approved_text": "Стоимость уточняется после осмотра."}),
])
def test_single_price_preserves_mode_unit_and_every_condition(mode, text, metadata):
    fields = {} if mode == "no_public_price" else {"currency": "RUB", "billing_unit": "jaw"}
    item = D2FrozenPriceRow(source_client_id="demo", offer_id="offer", service_id="service",
        service_name="Услуга", variant_label="Вариант", mode=mode, display_text=f"Услуга — {text}",
        price_display_text=text, scope_text=None if mode == "no_public_price" else "за одну челюсть",
        condition_texts=("Диагностика по показаниям — отдельно",), **fields, **metadata)
    before = item.model_dump()
    parts = []
    _render_compact_price_group((item,), parts, show_service_in_each_row=False)
    answer = "\n\n".join(parts)
    assert item.model_dump() == before
    assert answer.startswith("**Услуга** — Вариант\n\n")
    assert answer.count(text) == 1
    assert answer.count("Диагностика по показаниям — отдельно") == 1
    if mode != "no_public_price":
        assert answer.count("за одну челюсть") == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("aspect", ["includes", "stages"])
def test_verified_detail_click_keeps_frozen_facts_and_replay_without_model(http_env, transport, aspect):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price("classic", "service"))))
    send = post if transport == "json" else post_sse
    first = _body(send(client, request_id="price", q="Цена классической имплантации?"), transport)
    args = dict(request_id="detail", q="", ref=f"price_detail:{aspect}", ui_revision=first["revision"])
    body = _body(send(client, **args), transport)
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        completion = store.read_latest_completion(SessionKey(client_id="demo", sid="cp6a"))
        block = completion.response.resolved.d2_price_detail_block
        assert block.aspect == aspect and len(block.rows) == 3
        assert completion.response.rendered_text == body["answer"]
        for item in block.rows:
            for text in (*item.includes, *item.excludes, *item.stages):
                assert text in body["answer"]
    assert f"price_detail:{aspect}" not in [item["reply_id"] for item in body["ui"]["quick_replies"]]
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1
