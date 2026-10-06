"""REC-4-P2 exact offer details through the offline D2 endpoints."""

from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from contracts.d2_tenant_snapshot import D2ServiceCommercialProfile
from contracts.response_plan import SessionKey
from core.d2_dialogue_store import D2DialogueStore
from core.d2_dialogue import run_d2_dialogue_turn
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events
from tests.test_d2_price_presentation_http import _raw
from tests.test_d2_rec3_memory_http import _price_part
from tests.test_d2_no_legacy_path import no_legacy_calls
from tests.test_d2_widget_replay import _mixed_widget_raw
from tests.test_d2_ui_b12_scenarios import _content_pain_raw, _price_raw as _overview_raw


def _plain_raw(*parts: dict) -> str:
    return json.dumps(production_envelope_template(
        patient_text=None,
        request_understanding={"subjects": [], "requests": list(parts)},
    ), ensure_ascii=False)


def _detail_part(request_id: str, *, aspect: str = "includes") -> dict:
    return {
        "request_id": request_id, "kind": "price_detail", "subject_id": None,
        "context": "general_information", "price_detail_aspect": aspect,
    }


def _detail_raw(*, aspect: str, service_id: str | None = None,
                ordinal: int | None = None, offer_id: str | None = None) -> str:
    return json.dumps(production_envelope_template(
        patient_text=None,
        service_id=service_id,
        commercial_intent="included" if aspect == "includes" else "payment_stages",
        request_understanding={"subjects": [], "requests": [{
            "request_id": "r1", "kind": "price_detail", "subject_id": None,
            "context": "general_information", "service_id": service_id,
            "price_detail_aspect": aspect,
            "price_detail_offer_ordinal": ordinal,
            "price_detail_offer_id": offer_id,
        }]},
    ), ensure_ascii=False)


@pytest.mark.parametrize("transport", ["json", "sse"])
def test_classic_price_clicks_freeze_all_shown_offers_without_provider(http_env, transport):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    send = post if transport == "json" else post_sse
    sid = f"p2-click-{transport}"

    def body(response):
        assert response.status_code == 200, response.get_data(as_text=True)
        return response.get_json() if transport == "json" else dict(sse_events(response))["ui"]

    price = body(send(client, sid=sid, request_id="price", q="Сколько стоит классическая имплантация?"))
    replies = {item["label"]: item["reply_id"] for item in price["ui"]["quick_replies"]}
    assert replies == {"Что входит": "price_detail:includes", "Этапы оплаты": "price_detail:stages"}
    assert "price_detail_actions" not in price["ui"]
    assert len(fake.inputs) == 1

    with no_legacy_calls(ordinary=True):
        includes = body(send(client, sid=sid, request_id="includes", q="",
                             ref=replies["Что входит"], ui_revision=price["revision"]))
    assert len(fake.inputs) == 1
    assert includes["answer"].count("имплант с документами") == 1
    assert "Состав одинаковый для всех этих вариантов" in includes["answer"]
    assert {item["label"] for item in includes["ui"]["quick_replies"]} == {
        "Что входит", "Этапы оплаты",
    }
    stages = body(send(client, sid=sid, request_id="stages", q="",
                       ref="price_detail:stages", ui_revision=includes["revision"]))
    assert len(fake.inputs) == 1
    assert "Хирургический этап" in stages["answer"]
    assert "45\u00a0200\u00a0₽" in stages["answer"]
    replay = body(send(client, sid=sid, request_id="stages", q="",
                       ref="price_detail:stages", ui_revision=includes["revision"]))
    assert replay == stages
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert saved.response.resolved.d2_price_detail_block.aspect == "stages"
        assert len(saved.response.resolved.d2_price_detail_block.rows) == 3


def test_direct_detail_uses_shown_order_even_when_buttons_disabled(http_env):
    client, _, use_provider, tmp_path = http_env
    commercial_path = tmp_path / "clients" / "demo" / "target_response" / "d2_commercial.json"
    commercial = json.loads(commercial_path.read_text(encoding="utf-8"))
    commercial["service_profiles"][0]["price_detail_ids"] = []
    commercial_path.write_text(json.dumps(commercial, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-direct"
    price = post(client, sid=sid, request_id="price", q="Цена классической имплантации?")
    assert price.status_code == 200, price.get_json()
    assert price.get_json()["ui"]["quick_replies"] == []
    fake.raw = _detail_raw(aspect="includes", ordinal=2)
    answer = post(client, sid=sid, request_id="detail", q="А что входит во втором?")
    assert answer.status_code == 200, answer.get_json()
    assert "Impro" in answer.get_json()["answer"]
    assert "Implantium" not in answer.get_json()["answer"]
    assert len(fake.inputs) == 2


def test_price_and_detail_keep_both_parts_in_order(http_env):
    client, _, use_provider, _ = http_env
    price_part = _price_part("r1", "classic", "implantation")
    detail_part = {
        "request_id": "r2", "kind": "price_detail", "subject_id": None,
        "context": "general_information", "service_id": "classic",
        "price_detail_aspect": "includes",
    }
    fake = use_provider(FakeProvider(_raw(price_part, detail_part, intro=None)))
    response = post(client, sid="p2-both", request_id="both",
                    q="Сколько стоит классическая имплантация и что входит?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.index("76\u00a0200\u00a0₽") < answer.index("Что входит")
    assert answer.count("имплант с документами") == 1
    assert len(fake.inputs) == 1


def test_partial_stage_data_hides_only_stage_button_and_names_gap(http_env):
    client, _, use_provider, tmp_path = http_env
    offer_path = (tmp_path / "clients" / "demo" / "target_response" / "pricebook"
                  / "services" / "classic.one_tooth.nobel.json")
    offer = json.loads(offer_path.read_text(encoding="utf-8"))
    offer["followups"] = [item for item in offer["followups"] if item["id"] != "stages"]
    offer["payment_stages"] = None
    offer_path.write_text(json.dumps(offer, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-partial"
    price = post(client, sid=sid, request_id="price", q="Цена классической имплантации?")
    assert price.status_code == 200, price.get_json()
    assert {item["label"] for item in price.get_json()["ui"]["quick_replies"]} == {"Что входит"}
    assert "101\u00a0200\u00a0₽" in price.get_json()["answer"]
    fake.raw = _detail_raw(aspect="stages")
    detail = post(client, sid=sid, request_id="stage-question", q="Какие этапы оплаты?")
    assert detail.status_code == 200, detail.get_json()
    answer = detail.get_json()["answer"]
    assert "Implantium" in answer and "Impro" in answer and "Nobel Biocare" in answer
    assert "порядок оплаты не указан" in answer
    assert len(fake.inputs) == 2


def test_stale_forged_and_foreign_detail_clicks_never_reach_provider(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-guards"
    price = post(client, sid=sid, request_id="price", q="Цена классической имплантации?").get_json()
    revision = price["revision"]
    forged = post(client, sid=sid, request_id="forged", q="",
                  ref="price_detail:unknown", ui_revision=revision)
    assert forged.status_code != 200
    foreign = post(client, sid=sid, request_id="foreign", q="", client_id="nikadent",
                   ref="price_detail:includes", ui_revision=revision)
    assert foreign.status_code != 200
    includes = post(client, sid=sid, request_id="includes", q="",
                    ref="price_detail:includes", ui_revision=revision)
    assert includes.status_code == 200, includes.get_json()
    stale = post(client, sid=sid, request_id="stale", q="",
                 ref="price_detail:stages", ui_revision=revision)
    assert stale.status_code != 200
    assert len(fake.inputs) == 1
    with D2DialogueStore(db) as store:
        saved = store.read_latest_completion(SessionKey(client_id="demo", sid=sid))
        assert saved.committed_revision == includes.get_json()["revision"]


def test_direct_detail_without_service_or_shown_set_clarifies_once(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_detail_raw(aspect="includes")))
    response = post(client, sid="p2-no-context", request_id="detail", q="А что входит?")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["answer"]
    assert len(fake.inputs) == 1


@pytest.mark.parametrize("ids", [
    ["includes", "includes"], ["includes", "stages", "includes"], ["unknown"],
])
def test_price_detail_profile_rejects_duplicate_overflow_or_unknown(ids):
    with pytest.raises(ValueError):
        D2ServiceCommercialProfile.model_validate({
            "service_id": "classic", "price_detail_ids": ids,
        })


def test_direct_exact_service_detail_works_without_price_or_button(http_env):
    client, _, use_provider, tmp_path = http_env
    commercial_path = tmp_path / "clients" / "demo" / "target_response" / "d2_commercial.json"
    commercial = json.loads(commercial_path.read_text(encoding="utf-8"))
    commercial["service_profiles"][0]["price_detail_ids"] = []
    commercial_path.write_text(json.dumps(commercial, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_detail_raw(aspect="stages", service_id="classic")))
    response = post(client, sid="p2-direct-new", request_id="detail",
                    q="Какие этапы оплаты у классической имплантации?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert "Хирургический этап" in answer
    assert "Implantium" in answer and "Impro" in answer and "Nobel Biocare" in answer
    assert response.get_json()["ui"]["quick_replies"] == []
    assert len(fake.inputs) == 1


def test_other_tenant_has_no_classic_detail_buttons(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "tooth_extraction", None), intro=None,
    )))
    response = post(client, sid="p2-nikadent", request_id="price", client_id="nikadent",
                    q="Сколько стоит удаление зуба?")
    assert response.status_code == 200, response.get_json()
    assert not any(item["reply_id"].startswith("price_detail:")
                   for item in response.get_json()["ui"]["quick_replies"])
    assert len(fake.inputs) == 1


def test_service_switch_replaces_detail_offer_set(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-service-switch"
    assert post(client, sid=sid, request_id="classic", q="Цена классической имплантации?").status_code == 200
    fake.raw = _raw(_price_part("r1", "professional_whitening"), intro=None)
    whitening = post(client, sid=sid, request_id="whitening", q="Цена отбеливания?")
    assert whitening.status_code == 200, whitening.get_json()
    fake.raw = _detail_raw(aspect="includes")
    detail = post(client, sid=sid, request_id="detail", q="А что входит?")
    assert detail.status_code == 200, detail.get_json()
    assert "Implantium" not in detail.get_json()["answer"]
    with D2DialogueStore(db) as store:
        refs = store.read(SessionKey(client_id="demo", sid=sid)).state.d2_shown_price_offer_refs
        assert refs and all(ref.service_id == "professional_whitening" for ref in refs)
    assert len(fake.inputs) == 3


def test_content_service_switch_drops_old_price_details_in_multipart(http_env):
    client, db, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-content-switch"
    assert post(client, sid=sid, request_id="price", q="Цена имплантации?").status_code == 200
    fake.raw = _plain_raw({
        "request_id": "r1", "kind": "content", "subject_id": None,
        "context": "general_information", "service_id": "veneers",
        "topic_id": "prosthetics", "content_text": "О винирах расскажу отдельно.",
    })
    content = post(client, sid=sid, request_id="content", q="Расскажите о винирах")
    assert content.status_code == 200, content.get_json()
    with D2DialogueStore(db) as store:
        assert not store.read(SessionKey(client_id="demo", sid=sid)).state.d2_shown_price_offer_refs
    fake.raw = _plain_raw(
        {"request_id": "r1", "kind": "content", "subject_id": None,
         "context": "general_information", "content_text": "Виниры меняют форму зубов."},
        _detail_part("r2"),
    )
    mixed = post(client, sid=sid, request_id="mixed", q="А виниры и что входит?")
    assert mixed.status_code == 200, mixed.get_json()
    answer = mixed.get_json()["answer"]
    assert "Виниры меняют форму зубов." in answer
    assert "Уточните, для какой услуги" in answer
    assert "Implantium" not in answer


def test_same_turn_content_service_switch_does_not_borrow_old_details(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-same-turn-switch"
    assert post(client, sid=sid, request_id="price", q="Цена имплантации?").status_code == 200
    fake.raw = _plain_raw(
        {"request_id": "r1", "kind": "content", "subject_id": None,
         "context": "general_information", "service_id": "veneers",
         "topic_id": "prosthetics", "content_text": "Виниры меняют форму зубов."},
        _detail_part("r2"),
    )
    response = post(client, sid=sid, request_id="mixed",
                    q="Расскажите о винирах и что входит?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert "Виниры меняют форму зубов." in answer
    assert "Уточните, для какой услуги" in answer
    assert "Implantium" not in answer


def test_price_and_detail_for_different_explicit_services_stay_independent(http_env):
    client, db, use_provider, _ = http_env
    detail_part = _detail_part("r2") | {"service_id": "all_on_4"}
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), detail_part, intro=None,
    )))
    response = post(client, sid="p2-cross-service", request_id="mixed",
                    q="Цена классической имплантации и что входит в All-on-4?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.index("76\u00a0200\u00a0₽") < answer.index("Что входит")
    assert "All-on-4" in answer
    with D2DialogueStore(db) as store:
        assert not store.read(SessionKey(client_id="demo", sid="p2-cross-service")).state.d2_shown_price_offer_refs
    fake.raw = _detail_raw(aspect="stages")
    followup = post(client, sid="p2-cross-service", request_id="short-detail",
                    q="А этапы оплаты?")
    assert followup.status_code == 200, followup.get_json()
    assert "Имплантация All-on-4" not in followup.get_json()["answer"]
    assert "Классическая имплантация" not in followup.get_json()["answer"]
    assert len(fake.inputs) == 2


def test_direct_detail_reads_exact_data_when_followup_capability_is_off(http_env):
    client, _, use_provider, tmp_path = http_env
    offer_path = (tmp_path / "clients" / "demo" / "target_response" / "pricebook"
                  / "services" / "classic.one_tooth.nobel.json")
    offer = json.loads(offer_path.read_text(encoding="utf-8"))
    offer["followups"] = [item for item in offer["followups"] if item["id"] != "stages"]
    assert offer["payment_stages"]
    offer_path.write_text(json.dumps(offer, ensure_ascii=False), encoding="utf-8")
    fake = use_provider(FakeProvider(_raw(
        _price_part("r1", "classic", "implantation"), intro=None,
    )))
    sid = "p2-exact-without-action"
    price = post(client, sid=sid, request_id="price", q="Цена имплантации?")
    assert price.status_code == 200, price.get_json()
    assert "price_detail:stages" not in {
        item["reply_id"] for item in price.get_json()["ui"]["quick_replies"]
    }
    fake.raw = _detail_raw(aspect="stages")
    detail = post(client, sid=sid, request_id="detail", q="Какие этапы оплаты?")
    assert detail.status_code == 200, detail.get_json()
    assert "Nobel Biocare" in detail.get_json()["answer"]
    assert "порядок оплаты не указан" not in detail.get_json()["answer"]
    assert len(fake.inputs) == 2


def test_multipart_ambiguous_detail_preserves_independent_prose(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_plain_raw(
        {"request_id": "r1", "kind": "content", "subject_id": None,
         "context": "general_information", "content_text": "О методе отвечу отдельно."},
        _detail_part("r2"),
    )))
    response = post(client, sid="p2-ambiguous-mixed", request_id="mixed",
                    q="Расскажите о методе, и что входит?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.index("О методе отвечу отдельно.") < answer.index("Уточните, для какой услуги")
    assert len(fake.inputs) == 1


def test_detail_and_exact_contact_keep_order(http_env):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_plain_raw(
        _detail_part("r1", aspect="stages") | {"service_id": "classic"},
        {"request_id": "r2", "kind": "contact", "subject_id": None,
         "context": "general_information", "contact_fields": ["contact_address"]},
    )))
    response = post(client, sid="p2-detail-contact", request_id="mixed",
                    q="Этапы оплаты имплантации и адрес клиники?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert answer.index("Как оплачивается") < answer.index("г. Москва")
    assert "Хирургический этап" in answer
    assert len(fake.inputs) == 1


def test_expired_shown_set_is_not_used_for_short_detail(http_env):
    _, db, _, root = http_env
    sid = "p2-expired"
    key = SessionKey(client_id="demo", sid=sid)
    at = datetime(2026, 9, 29, 12, tzinfo=timezone.utc)
    fake = FakeProvider(_raw(_price_part("r1", "classic"), intro=None))
    with D2DialogueStore(db) as store:
        first = run_d2_dialogue_turn(
            session_key=key, user_message="Цена классической имплантации?",
            provider=fake, clients_root=root / "clients", store=store,
            now=at, request_id="price",
        )
        assert first.response.resolved.d2_price_block is not None
        fake.raw = _detail_raw(aspect="includes")
        detail = run_d2_dialogue_turn(
            session_key=key, user_message="А что входит?", provider=fake,
            clients_root=root / "clients", store=store,
            now=at + timedelta(minutes=30), request_id="detail",
        )
        assert detail.response.resolved.route == "CLARIFY"
        assert detail.response.resolved.d2_price_detail_block is None
    assert len(fake.inputs) == 2


def test_real_price_detail_payloads_render_and_click_in_widget(http_env, tmp_path):
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_mixed_widget_raw()))
    sid = "p2-browser-base"
    first = post(client, sid=sid, request_id="b1", q="первый").get_json()
    scope_ref = next(item["reply_id"] for item in first["ui"]["quick_replies"]
                     if item["reply_id"].endswith("one_tooth"))
    fake.raw = _overview_raw("implantation", {
        "scope_commitment": "reported", "extent": "one_tooth",
        "tooth_count": 1, "jaw": "unknown", "continuity": "same",
    })
    scope = post(client, sid=sid, request_id="b2", q="", ref=scope_ref,
                 ui_revision=first["revision"]).get_json()
    fake.raw = _overview_raw("implantation")
    second = post(client, sid=sid, request_id="b3", q="первый").get_json()
    cta = next(item for item in second["ui"]["buttons"] if item["action_kind"] == "cta")
    lead = post(client, sid=sid, request_id="b4", q="",
                ref=f"button:{cta['button_id']}", ui_revision=second["revision"]).get_json()
    after_ui = post(client, sid=sid, request_id="b5", q="после UI").get_json()
    manual = post(client, sid=sid, request_id="b6", q="ручной повтор").get_json()
    fake.raw = json.dumps(production_envelope_template(
        route="ADMIN", patient_text=None, commercial_intent="none",
        promotion_scope="none", scenario="none", primary_price_request_id=None,
        request_understanding={"subjects": [], "requests": []},
    ), ensure_ascii=False)
    terminal = post(client, sid="p2-terminal", request_id="terminal", q="terminal").get_json()
    fake.raw = _content_pain_raw()
    video = post(client, sid="p2-video", request_id="video", q="video").get_json()

    fake.raw = _raw(_price_part("r1", "classic", "implantation"), intro=None)
    sid = "p2-browser-detail"
    p2_price = post(client, sid=sid, request_id="price", q="Цена классической имплантации?").get_json()
    p2_includes = post(client, sid=sid, request_id="includes", q="",
                       ref="price_detail:includes", ui_revision=p2_price["revision"]).get_json()
    p2_stages = post(client, sid=sid, request_id="stages", q="",
                     ref="price_detail:stages", ui_revision=p2_includes["revision"]).get_json()
    payload_file = tmp_path / "p2_widget_payloads.json"
    payload_file.write_text(json.dumps({
        "first": first, "scope": scope, "second": second, "lead": lead,
        "afterUi": after_ui, "manual": manual, "terminal": terminal, "video": video,
        "p2Price": p2_price, "p2Includes": p2_includes, "p2Stages": p2_stages,
    }, ensure_ascii=False), encoding="utf-8")
    env = {**os.environ, "D2_WIDGET_PAYLOADS_FILE": str(payload_file)}
    harness = Path(__file__).parent / "js" / "d2_widget_harness.mjs"
    result = subprocess.run(["node", str(harness)], cwd=Path(__file__).resolve().parents[1],
                            env=env, capture_output=True, text=True, timeout=75, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '"price_detail_ref":"price_detail:includes"' in result.stdout
