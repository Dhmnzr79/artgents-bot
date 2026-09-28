"""REC-4: concise verified prices and tenant-owned UI through offline HTTP."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_rec3_memory_http import _price_part, _price_raw
from tests.test_d2_ui_b12_scenarios import _content_pain_raw, _price_raw as _overview_raw


def _add_fourth_all_on_4_offer(clients: Path) -> None:
    root = clients / "demo" / "target_response"
    brands_path = root / "brand_catalog.json"
    brands = json.loads(brands_path.read_text(encoding="utf-8"))
    brands["brands"]["demo_four"] = {
        "canonical_name": "Demo Four", "country": "не указана", "aliases": [],
    }
    brands_path.write_text(json.dumps(brands, ensure_ascii=False), encoding="utf-8")

    service_dir = root / "pricebook" / "services"
    original = json.loads((service_dir / "all_on_4.jaw.impro.json").read_text(encoding="utf-8"))
    original["offer_id"] = "all_on_4.jaw.demo_four"
    original["brand_id"] = "demo_four"
    original["price"]["amount"] = 398_000
    original["payment_stages"][0]["amount"] = 238_800
    original["payment_stages"][1]["amount"] = 159_200
    (service_dir / "all_on_4.jaw.demo_four.json").write_text(
        json.dumps(original, ensure_ascii=False), encoding="utf-8",
    )


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_exact_service_shows_four_short_verified_offers_and_replays(http_env, transport):
    client, db, use_provider, tmp_path = http_env
    _add_fourth_all_on_4_offer(tmp_path / "clients")
    fake = use_provider(FakeProvider(_price_raw(_price_part("r1", "all_on_4", "implantation"))))
    send = post if transport == "json" else post_sse
    first = send(client, sid=f"rec4-four-{transport}", request_id="price",
                 q="Сколько стоит имплантация All-on-4?")
    assert first.status_code == 200
    body = first.get_json() if transport == "json" else dict(sse_events(first))["ui"]

    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=f"rec4-four-{transport}")
        completion = store.read_latest_completion(key)
        rows = completion.response.resolved.d2_price_block.rows
        assert [(row.offer_id, row.amount) for row in rows] == [
            ("all_on_4.jaw.implantium", 318_000),
            ("all_on_4.jaw.impro", 368_000),
            ("all_on_4.jaw.demo_four", 398_000),
            ("all_on_4.jaw.nobel", 428_000),
        ]
        assert all(row.service_id == "all_on_4" for row in rows)
        assert all(row.condition_texts == (
            "за одну челюсть", "КТ и костная пластика по показаниям — отдельно",
        )
                   for row in rows)
        assert "Demo Four" in rows[2].display_text
        assert completion.response.rendered_text == body["answer"]
        assert tuple(item.offer_id for item in store.read(key).state.d2_shown_price_offer_refs) == (
            "all_on_4.jaw.implantium", "all_on_4.jaw.impro",
            "all_on_4.jaw.demo_four", "all_on_4.jaw.nobel",
        )
    assert "4 импланта с документами" not in body["answer"]
    assert "Этап 1" not in body["answer"]
    assert "за одну челюсть — за одну челюсть" not in body["answer"]
    ctas = [item for item in body["ui"]["buttons"] if item["action_kind"] == "cta"]
    assert [(item["button_id"], item["label"]) for item in ctas] == [
        ("default_consult", "Записаться на консультацию"),
    ]
    import session
    with session.session_client_scope("demo"):
        assert session.peek_lead_activity(f"rec4-four-{transport}") == (False, False)
    replay = (post_sse if transport == "json" else post)(
        client, sid=f"rec4-four-{transport}", request_id="price",
        q="Сколько стоит имплантация All-on-4?",
    )
    replay_body = dict(sse_events(replay))["ui"] if transport == "json" else replay.get_json()
    assert replay_body == body
    assert len(fake.inputs) == 1


def test_general_overview_keeps_three_prices_four_choices_and_neutral_intro(http_env):
    client, db, use_provider, _ = http_env
    use_provider(FakeProvider(_overview_raw("implantation")))
    response = post(client, sid="rec4-overview", request_id="overview",
                    q="Сколько стоит имплантация?")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid="rec4-overview"))
        plan = saved.response.resolved
        assert len(plan.d2_price_block.rows) == 3
        assert plan.d2_price_scope_decision.introduction_text == (
            "Цена зависит от протокола и объёма лечения."
        )
        assert "восстановления одного зуба" not in plan.d2_price_scope_decision.introduction_text
    assert [item["label"] for item in body["ui"]["quick_replies"]] == [
        "Один зуб", "Несколько зубов", "Вся челюсть", "Не знаю",
    ]


def test_document_followup_label_is_clean_and_keeps_source_cta(http_env):
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_content_pain_raw()))
    response = post(client, sid="rec4-document", request_id="content",
                    q="Боюсь боли при имплантации")
    assert response.status_code == 200
    ui = response.get_json()["ui"]
    assert [(item["reply_id"], item["label"]) for item in ui["quick_replies"]] == [
        ("implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut",
         "Какую анестезию используют"),
    ]
    assert [(item["button_id"], item["label"]) for item in ui["buttons"]] == [
        ("consult", "Обсудить вопрос"),
    ]


def test_live_content_without_source_cta_uses_neutral_tenant_fallback(http_env):
    client, db, use_provider, _ = http_env
    payload = json.loads(_content_pain_raw())
    part = payload["request_understanding"]["requests"][0]
    part["content_ref"] = None
    part["content_section_refs"] = []
    part["content_fallback_section_ref"] = None
    fake = use_provider(FakeProvider(json.dumps(payload, ensure_ascii=False)))
    response = post(client, sid="rec4-content-fallback", request_id="content",
                    q="Волнуюсь перед имплантацией")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    assert "Понимаю этот страх" in body["answer"]
    assert [(item["button_id"], item["label"]) for item in body["ui"]["buttons"]] == [
        ("default_consult", "Записаться на консультацию"),
    ]
    assert body["ui"]["quick_replies"] == []
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="rec4-content-fallback")
        saved = store.read_latest_completion(key)
        assert saved.response.rendered_text == body["answer"]
        assert saved.response.resolved.ui_plan.source_content_ref is None
    assert post(client, sid="rec4-content-fallback", request_id="content",
                q="Волнуюсь перед имплантацией").get_json() == body
    assert len(fake.inputs) == 1


def test_price_and_default_cta_stay_inside_each_tenant(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_price_raw(_price_part("r1", "tooth_extraction"))))
    for tenant, expected_scope in (
        ("demo", ("за удаление одного зуба",)),
        ("nikadent", ("за удаление", "зависит от сложности")),
    ):
        response = post(client, client_id=tenant, sid="rec4-shared-sid",
                        request_id="price", q="Сколько стоит удаление зуба?")
        assert response.status_code == 200, response.get_json()
        body = response.get_json()
        with D2DialogueStore(db) as store:
            key = SessionKey(client_id=tenant, sid="rec4-shared-sid")
            completion = store.read_latest_completion(key)
            row = completion.response.resolved.d2_price_block.rows[0]
            assert row.source_client_id == tenant
            assert row.condition_texts == expected_scope
            assert "за один зуб" not in row.display_text
            assert completion.response.rendered_text == body["answer"]
        assert [(item["button_id"], item["label"]) for item in body["ui"]["buttons"]] == [
            ("default_consult", "Записаться на консультацию"),
        ]
    assert len(fake.inputs) == 2
