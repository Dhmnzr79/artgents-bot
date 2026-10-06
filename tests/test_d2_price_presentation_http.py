"""REC-4-P1: whole-turn price presentation through the offline D2 endpoints."""

from __future__ import annotations

import json
from datetime import date

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template
from core.response_plan_materialization import resolve_d2_operations
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_rec3_memory_http import _price_part
from tests.test_d2_ui_b12_scenarios import _price_raw as _overview_raw
from tests.test_d2_price_scope_selection import (
    _envelope as _scope_envelope, _volume, _with_scope_failure_authority,
)
from tests.test_d2_multi_request import _sources
from tests.test_target_offer_projection import _bundle


def _raw(*parts: dict, intro: str | None) -> str:
    primary = next((item["request_id"] for item in parts if item["kind"] == "price"), None)
    return json.dumps(production_envelope_template(
        commercial_intent="price",
        patient_text=intro,
        primary_price_request_id=primary,
        request_understanding={"subjects": [], "requests": list(parts)},
    ), ensure_ascii=False)


def _content_part(request_id: str, text: str) -> dict:
    return {
        "request_id": request_id,
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "service_id": "classic",
        "topic_id": "implantation",
        "statement_mode": "question",
        "volume": None,
        "content_text": text,
        "content_ref": None,
    }


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("intro", [None, "Вот варианты для одного зуба."])
def test_exact_price_is_compact_and_optional_intro_is_saved_once(http_env, transport, intro):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=intro,
    )))
    sid = f"p1-classic-{transport}-{'intro' if intro else 'plain'}"
    send = post if transport == "json" else post_sse
    first = send(client, sid=sid, request_id="price", q="Сколько стоит классическая имплантация?")
    assert first.status_code == 200
    body = first.get_json() if transport == "json" else dict(sse_events(first))["ui"]
    answer = body["answer"]

    assert "**Классическая имплантация**" in answer
    assert answer.count("- Implantium — **76\u00a0200\u00a0₽**") == 1
    assert answer.count("- Impro — **85\u00a0200\u00a0₽**") == 1
    assert answer.count("- Nobel Biocare — **101\u00a0200\u00a0₽**") == 1
    assert answer.count("за восстановление одного зуба") == 1
    assert answer.count("КТ при необходимости и временная коронка — отдельно") == 1
    assert answer.count("\n- ") == 3
    assert "имплант с документами" not in answer
    assert "Этап 1" not in answer
    if intro:
        assert answer.startswith(intro + "\n\n")
        assert answer.count(intro) == 1
    else:
        assert not answer.startswith("Понимаю")

    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        saved = store.read_latest_completion(key)
        assert saved.response.rendered_text == answer
        assert len(saved.response.resolved.d2_price_block.rows) == 3
        pairs = store.read(key).state.dialogue_pairs
        assert [pair.assistant_text for pair in pairs] == ([intro] if intro else [])
        assert tuple(ref.offer_id for ref in store.read(key).state.d2_shown_price_offer_refs) == (
            "classic.one_tooth.implantium", "classic.one_tooth.impro",
            "classic.one_tooth.nobel",
        )
    replay = send(client, sid=sid, request_id="price", q="Сколько стоит классическая имплантация?")
    replay_body = replay.get_json() if transport == "json" else dict(sse_events(replay))["ui"]
    assert replay_body == body
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("content_first", [False, True])
def test_mixed_content_keeps_its_place_and_all_prose_in_history(http_env, content_first):
    client, db, use_provider, _ = http_env
    content = "Приживаемость обсуждается по материалам клиники."
    intro = "Коротко о цене:"
    price_part = _price_part("r2" if content_first else "r1", "classic", "implantation")
    content_part = _content_part("r1" if content_first else "r2", content)
    parts = (content_part, price_part) if content_first else (price_part, content_part)
    fake = use_provider(FakeProvider(_raw(*parts, intro=intro)))
    sid = f"p1-mixed-{content_first}"
    response = post(client, sid=sid, request_id="mixed", q="Приживаемость и цена?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.count(content) == 1
    assert answer.count(intro) == 1
    assert answer.count("76\u00a0200\u00a0₽") == 1
    if content_first:
        assert answer.index(content) < answer.index(intro) < answer.index("76\u00a0200\u00a0₽")
    else:
        assert answer.index(intro) < answer.index("76\u00a0200\u00a0₽") < answer.index(content)
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid=sid)
        saved = store.read_latest_completion(key)
        assert saved.response.rendered_text == answer
        pairs = store.read(key).state.dialogue_pairs
        assert len(pairs) == 1
        expected_prose = f"{content}\n\n{intro}" if content_first else f"{intro}\n\n{content}"
        assert pairs[0].assistant_text == expected_prose
        assert "76\u00a0200" not in pairs[0].assistant_text
    assert post(client, sid=sid, request_id="mixed", q="Приживаемость и цена?").get_json()["answer"] == answer
    assert len(fake.inputs) == 1


def test_overview_is_a_short_list_with_factual_scope_and_choices(http_env):
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_overview_raw("implantation")))
    response = post(client, sid="p1-overview", request_id="overview", q="Сколько стоит имплантация?")
    assert response.status_code == 200, response.get_json()
    body = response.get_json()
    answer = body["answer"]
    assert answer.count("Цена зависит от протокола и объёма лечения.") == 1
    assert "Понимаю, хочется" not in answer
    assert answer.count("\n- ") == 3
    assert "Классическая имплантация" in answer
    assert all(brand in answer for brand in ("Implantium", "Impro", "Nobel Biocare"))
    assert [item["label"] for item in body["ui"]["quick_replies"]] == [
        "Один зуб", "Несколько зубов", "Вся челюсть", "Не знаю",
    ]


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_one_tooth_choice_names_its_single_service_once(http_env, transport):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_overview_raw("implantation")))
    send = post if transport == "json" else post_sse
    sid = f"p1-one-tooth-{transport}"
    overview = send(client, sid=sid, request_id="overview", q="Сколько стоит имплантация?")
    assert overview.status_code == 200
    first = overview.get_json() if transport == "json" else dict(sse_events(overview))["ui"]
    selected = next(
        item for item in first["ui"]["quick_replies"]
        if item["reply_id"] == "volume:implantation:one_tooth"
    )

    fake.raw = _overview_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    clicked = send(
        client, sid=sid, request_id="one-tooth", q="",
        ref=selected["reply_id"], ui_revision=first["revision"],
    )
    assert clicked.status_code == 200
    body = clicked.get_json() if transport == "json" else dict(sse_events(clicked))["ui"]
    answer = body["answer"]
    assert answer.count("Классическая имплантация") == 1
    assert answer.count("\n- ") == 3
    assert "- Implantium — **76\u00a0200\u00a0₽**" in answer
    assert "- Impro — **85\u00a0200\u00a0₽**" in answer
    assert "- Nobel Biocare — **101\u00a0200\u00a0₽**" in answer
    assert answer.count("КТ при необходимости и временная коронка — отдельно") == 1
    assert len(fake.inputs) == 2
    replay = send(
        client, sid=sid, request_id="one-tooth", q="",
        ref=selected["reply_id"], ui_revision=first["revision"],
    )
    replay_body = replay.get_json() if transport == "json" else dict(sse_events(replay))["ui"]
    assert replay_body == body
    assert len(fake.inputs) == 2


def test_offer_specific_condition_stays_with_its_variant(http_env):
    client, _, use_provider, tmp_path = http_env
    offer_path = (
        tmp_path / "clients" / "demo" / "target_response" / "pricebook"
        / "services" / "classic.one_tooth.nobel.json"
    )
    offer = json.loads(offer_path.read_text(encoding="utf-8"))
    offer["package"]["label"] += "; Только для варианта Nobel: контроль через неделю"
    offer_path.write_text(json.dumps(offer, ensure_ascii=False), encoding="utf-8")
    use_provider(FakeProvider(_raw(_price_part("r1", "classic", "implantation"), intro=None)))
    response = post(client, sid="p1-different-terms", request_id="price",
                    q="Стоимость классической имплантации?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    lines = answer.splitlines()
    assert answer.count("КТ при необходимости и временная коронка — отдельно") == 1
    assert answer.count("Только для варианта Nobel: контроль через неделю") == 1
    assert sum("за восстановление одного зуба" in line for line in lines) == 1
    nobel_line = next(line for line in lines if line.startswith("- Nobel Biocare"))
    assert "Только для варианта Nobel: контроль через неделю" in nobel_line
    assert not any("Только для варианта Nobel" in line for line in lines if line.startswith("- Impro"))


def test_single_price_has_no_list_and_keeps_its_tenant_scope(http_env):
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_raw(_price_part("r1", "professional_whitening"), intro=None)))
    response = post(client, sid="p1-single", request_id="price", q="Сколько стоит отбеливание?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert "**Профессиональное отбеливание** — **от 18\u00a0000\u00a0₽**" in answer
    assert "за одну процедуру" in answer
    assert "\n- " not in answer


def test_exact_duplicate_intro_does_not_replace_independent_content(http_env):
    client, db, use_provider, _ = http_env
    prose = "Приживаемость обсуждается по материалам клиники."
    fake = use_provider(FakeProvider(_raw(
        _content_part("r1", prose), _price_part("r2", "classic", "implantation"),
        intro=prose,
    )))
    response = post(client, sid="p1-duplicate", request_id="mixed", q="Приживаемость и цена?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.count(prose) == 1
    assert answer.index(prose) < answer.index("76\u00a0200\u00a0₽")
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="p1-duplicate")
        assert store.read(key).state.dialogue_pairs[0].assistant_text == prose
    assert len(fake.inputs) == 1


def test_optional_intro_does_not_turn_unavailable_price_into_an_answer():
    envelope = _scope_envelope(_volume("few_teeth")).model_copy(
        update={"patient_text": "Вот варианты для одного зуба."}
    )
    sources = _with_scope_failure_authority(_sources(_bundle()))
    outcome = resolve_d2_operations((envelope).blocks, sources, as_of=date(2026, 9, 18))
    assert outcome.resolved.d2_result_status == "failed"
    assert outcome.resolved.d2_price_block is None
    assert outcome.resolved.patient_text is None
    assert "Вот варианты" not in outcome.rendered_text
    assert "Нет подходящей опубликованной цены." in outcome.rendered_text
