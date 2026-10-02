"""Approved exact/unit/missing-price publication, not model-adherence evidence."""
import json

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse
from tests.test_d2_document_click_task_http import _body
from tests.test_d2_sim2_dialogues import raw, price, explanation


def scope(count):
    return dict(scope_commitment="hypothetical", extent="one_tooth" if count == 1 else "few_teeth",
                tooth_count=count, jaw="unknown", continuity="new")


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("topic", ["implantation", "prosthetics", "restoration"])
@pytest.mark.parametrize("count", [1, 2, 3, None])
def test_price_guidance_keeps_requested_scope_units_and_continuation(http_env, transport, topic, count):
    client, db, use, _ = http_env
    fake = use(FakeProvider(raw(price(topic, "topic", situation=scope(count)))))
    send = post if transport == "json" else post_sse
    args = dict(sid="guidance", request_id="price", q=f"Стоимость: {topic}, зубов: {count or 'несколько'}")
    response = send(client, **args)
    assert response.status_code == 200
    body = _body(response, transport)
    answer = body["answer"].replace("\u00a0", " ")
    expected = {
        ("implantation", True): ("classic.one_tooth.implantium", "one_stage.one_tooth.implantium"),
        ("implantation", False): ("classic.one_tooth.implantium",),
        ("restoration", True): ("classic.one_tooth.implantium",),
        ("restoration", False): ("classic.one_tooth.implantium", "removable_dentures.jaw.partial"),
        ("prosthetics", True): ("implant_supported_prosthetics.default",),
        ("prosthetics", False): ("removable_dentures.jaw.partial", "clasp_dentures.default", "implant_supported_prosthetics.default"),
    }[topic, count == 1]
    with D2DialogueStore(db) as store:
        key = SessionKey(client_id="demo", sid="guidance")
        saved = store.read_latest_completion(key)
        result = saved.response.resolved
        assert tuple(r.offer_id for r in result.d2_price_block.rows) == expected
        assert result.d2_treatment_situation.tooth_count == count
        assert result.d2_treatment_situation.extent == scope(count)["extent"]
        assert store.read(key).state.situation_state is None
    assert "All-on-4" not in answer and "All-on-6" not in answer
    if topic != "prosthetics":
        assert "76 200" in answer and "одного зуба" in answer
        assert "КТ" in answer and "временная коронка" in answer
    if topic == "prosthetics":
        assert "31 000" in answer and "уже установленном импланте" in answer
        assert "установка импланта" in answer
    if count != 1:
        assert "ориентир за один зуб" in answer and "консультации" in answer
        if topic != "implantation":
            assert "45 000" in answer and "челюсть" in answer
        assert "228 600" not in answer and "152 400" not in answer
    assert any(b["action_kind"] == "cta" for b in body["ui"]["buttons"])
    assert body["lead_effect"]["status"] == "not_requested"
    assert _body(send(client, **args), transport) == body
    assert len(fake.inputs) == 1
    fake.raw = raw(explanation("Сроки зависят от плана лечения."))
    assert send(client, sid="guidance", request_id="next", q="А сколько времени это займёт?").status_code == 200
    discussion = fake.inputs[-1].context.ordinary.discussion_scope
    assert discussion.topic_id == topic and discussion.extent == scope(count)["extent"]


@pytest.mark.parametrize("transport", ["json", "sse"])
@pytest.mark.parametrize("service", ["veneers", "professional_whitening"])
@pytest.mark.parametrize("content_first", [False, True])
def test_known_service_without_price_keeps_explanation_and_consultation(http_env, transport, service, content_first):
    client, db, use, tmp = http_env
    # Remove only the isolated test clinic's price, keeping its active service.
    (tmp / "clients/demo/target_response/pricebook/services" / f"{service}.default.json").unlink()
    blocks = [price(service, "service"), explanation("Пояснение процедуры из материалов клиники.", request_id="r2")]
    if content_first:
        blocks.reverse()
    fake = use(FakeProvider(raw(*blocks)))
    send = post if transport == "json" else post_sse
    args = dict(sid="missing", request_id="price", q="Как проходит эта процедура и сколько стоит?")
    response = send(client, **args)
    assert response.status_code == 200
    body = _body(response, transport)
    assert "Пояснение процедуры" in body["answer"]
    assert "Стоимость по вашему запросу не указана" in body["answer"]
    assert "у администратора" in body["answer"] and "Хотите записаться" in body["answer"]
    assert "вариант восстановления" not in body["answer"]
    assert "₽" not in body["answer"]
    assert any(b["action_kind"] == "cta" for b in body["ui"]["buttons"])
    assert not any(r["reply_id"].startswith("service:") for r in body["ui"]["quick_replies"])
    with D2DialogueStore(db) as store:
        result = store.read_latest_completion(SessionKey(client_id="demo", sid="missing")).response.resolved
        assert result.d2_price_block is None
        assert next(p for p in result.d2_request_parts if p.kind == "price").status == "unavailable"
    assert _body(send(client, **args), transport) == body and len(fake.inputs) == 1


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_partial_overview_keeps_numeric_price_and_authored_no_price_row(http_env, transport):
    client, db, use, tmp = http_env
    path = tmp / "clients/demo/target_response/pricebook/services/removable_dentures.jaw.partial.json"
    offer = json.loads(path.read_text(encoding="utf-8"))
    offer["price"] = {"mode": "no_public_price", "approved_text": "Цена частичного протеза не опубликована. Её можно уточнить у администратора."}
    path.write_text(json.dumps(offer, ensure_ascii=False), encoding="utf-8")
    fake = use(FakeProvider(raw(price("restoration", "topic", situation=scope(3)))))
    send = post if transport == "json" else post_sse
    response = send(client, sid="partial", request_id="price", q="Сколько стоит восстановить три зуба?")
    assert response.status_code == 200
    body = _body(response, transport)
    assert "76 200" in body["answer"].replace("\u00a0", " ")
    assert offer["price"]["approved_text"] in body["answer"]
    assert "45 000" not in body["answer"].replace("\u00a0", " ")
    assert "Стоимость по вашему запросу не указана" not in body["answer"]
    assert body["lead_effect"]["status"] == "not_requested"
    assert len(fake.inputs) == 1


def test_exact_whitening_preserves_published_price_and_does_not_get_tooth_guidance(http_env):
    client, _, use, _ = http_env
    use(FakeProvider(raw(price("professional_whitening", "service"))))
    body = post(client, q="Сколько стоит отбеливание?").get_json()
    assert "18 000" in body["answer"].replace("\u00a0", " ")
    assert "один зуб" not in body["answer"]
    assert "не указана" not in body["answer"]


def test_missing_brand_does_not_select_a_different_reference(http_env):
    client, db, use, _ = http_env
    use(FakeProvider(raw(price("implantation", "topic", brand_id="impro", situation=scope(3)))))
    body = post(client, q="Сколько стоят три импланта Impro?").get_json()
    assert "76 200" not in body["answer"].replace("\u00a0", " ")
    assert "Стоимость по вашему запросу не указана" in body["answer"]
