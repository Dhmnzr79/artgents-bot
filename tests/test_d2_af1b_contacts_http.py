"""AF-1b: exact tenant contacts survive one D2 HTTP answer and replay."""

from __future__ import annotations

import json

import pytest
import yaml

from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_envelope_protocol import production_envelope_template
from tests.test_d2_http_contract import FakeProvider, http_env, post, post_sse, sse_events


DEMO_PHONE = "+7 (495) 128-47-60"
DEMO_ADDRESS = "г. Москва, ул. Тверская, 12, стр. 1"
DEMO_HOURS = "Пн–Пт 09:00–21:00"
DEMO_PARKING = "городская парковка у здания"
PROSE = "Имплантация проходит в несколько этапов по материалам клиники."


def _contact_raw(
    fields: list[str], *, branch_id: str | None = None,
    prose: bool = False, content_first: bool = False,
) -> str:
    contact = {
        "request_id": "r2" if content_first else "r1",
        "kind": "contact", "subject_id": None,
        "context": "general_information", "contact_fields": fields,
        "contact_branch_id": branch_id,
    }
    content = {
        "request_id": "r1" if content_first else "r2",
        "kind": "content", "subject_id": None,
        "context": "general_information", "topic_id": "implantation",
        "content_text": PROSE, "content_realization": "model_prose",
    }
    requests = ([content, contact] if content_first else [contact, content]) if prose else [contact]
    return json.dumps(production_envelope_template(
        patient_text=None,
        request_understanding={"subjects": [], "requests": requests},
    ), ensure_ascii=False)


@pytest.mark.parametrize("question,fields,expected,excluded", [
    ("Какой у вас телефон?", ["contact_phone"], DEMO_PHONE, DEMO_ADDRESS),
    ("Где вы находитесь?", ["contact_address"], DEMO_ADDRESS, DEMO_PHONE),
    ("До скольки вы работаете?", ["contact_hours"], DEMO_HOURS, DEMO_PHONE),
    ("Есть ли парковка?", ["contact_parking"], DEMO_PARKING, DEMO_PHONE),
    ("Какие у вас контакты?", ["contacts"], DEMO_ADDRESS, DEMO_PARKING),
])
def test_exact_demo_field_without_phone_substitution(
    http_env, question: str, fields: list[str], expected: str, excluded: str,
) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_contact_raw(fields)))
    response = post(client, sid="af1b-" + fields[0], request_id="q", q=question)
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert expected in answer
    assert excluded not in answer
    if fields == ["contacts"]:
        assert DEMO_PHONE in answer and DEMO_HOURS in answer
    assert len(fake.inputs) == 1


def test_several_requested_fields_keep_each_exact_value(http_env) -> None:
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_contact_raw(["contact_hours", "contact_parking"])))
    response = post(client, sid="af1b-several", request_id="q",
                    q="До скольки работаете и есть ли парковка?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert DEMO_HOURS in answer and DEMO_PARKING in answer
    assert DEMO_PHONE not in answer and DEMO_ADDRESS not in answer


@pytest.mark.parametrize("content_first", [False, True])
@pytest.mark.parametrize("transport", ["json", "sse"])
def test_address_and_independent_explanation_survive_mixed_answer_and_replay(
    http_env, transport: str, content_first: bool,
) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_contact_raw(
        ["contact_address"], prose=True, content_first=content_first,
    )))
    send = post if transport == "json" else post_sse
    args = dict(sid=f"af1b-mixed-{transport}-{content_first}", request_id="q",
                q="Где вы и как проходит имплантация?")
    first = send(client, **args)
    assert first.status_code == 200
    body = first.get_json() if transport == "json" else dict(sse_events(first))["ui"]
    assert DEMO_ADDRESS in body["answer"] and PROSE in body["answer"]
    assert DEMO_PHONE not in body["answer"]
    replay = send(client, **args)
    again = replay.get_json() if transport == "json" else dict(sse_events(replay))["ui"]
    assert again == body
    assert len(fake.inputs) == 1


def test_missing_parking_is_honest_gap_not_phone(http_env) -> None:
    client, _, use_provider, tmp_path = http_env
    policy = tmp_path / "clients" / "demo" / "clinic_policies.yaml"
    source = yaml.safe_load(policy.read_text(encoding="utf-8"))
    source["contact"].pop("parking_display", None)
    policy.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    use_provider(FakeProvider(_contact_raw(["contact_parking"])))
    response = post(client, sid="af1b-no-parking", request_id="q", q="Есть парковка?")
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["answer"] == "В материалах клиники нет информации о парковке."
    assert DEMO_PHONE not in response.get_json()["answer"]


def test_missing_parking_keeps_requested_hours(http_env) -> None:
    client, _, use_provider, tmp_path = http_env
    policy = tmp_path / "clients" / "demo" / "clinic_policies.yaml"
    source = yaml.safe_load(policy.read_text(encoding="utf-8"))
    source["contact"].pop("parking_display", None)
    policy.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    use_provider(FakeProvider(_contact_raw(["contact_hours", "contact_parking"])))
    response = post(client, sid="af1b-hours-no-parking", request_id="q",
                    q="Когда работаете и есть ли парковка?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert DEMO_HOURS in answer
    assert "В материалах клиники нет информации о парковке." in answer
    assert DEMO_PHONE not in answer


def test_missing_required_address_fails_without_phone_answer(http_env) -> None:
    client, _, use_provider, tmp_path = http_env
    policy = tmp_path / "clients" / "demo" / "clinic_policies.yaml"
    source = yaml.safe_load(policy.read_text(encoding="utf-8"))
    source["contact"].pop("address_display", None)
    policy.write_text(yaml.safe_dump(source, allow_unicode=True), encoding="utf-8")
    use_provider(FakeProvider(_contact_raw(["contact_address"])))
    response = post(client, sid="af1b-no-address", request_id="q", q="Где вы?")
    assert response.status_code == 400
    assert DEMO_PHONE not in response.get_data(as_text=True)


@pytest.mark.parametrize("branch_id,expected,excluded", [
    (None, "Рябикова, д. 49", None),
    ("pogranichnaya", "Пограничная, д. 27", "Рябикова, д. 49"),
])
def test_branch_address_selection_is_typed_and_tenant_owned(
    http_env, branch_id: str | None, expected: str, excluded: str | None,
) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_contact_raw(
        ["contact_address"], branch_id=branch_id,
    )))
    response = post(client, sid=f"af1b-branch-{branch_id}", request_id="q",
                    client_id="nikadent",
                    q="Где вы находитесь?" if branch_id is None else "Где филиал на Пограничной?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert expected in answer
    if branch_id is None:
        assert "Филиал 1" in answer and "Филиал 2" in answer
        assert "Пограничная, д. 27" in answer
    else:
        assert excluded not in answer
        assert "Филиал 1" not in answer
    assert response.get_json()["ui"]["buttons"] == []
    assert len(fake.inputs) == 1


def test_foreign_or_unknown_branch_claim_is_rejected(http_env) -> None:
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_contact_raw(
        ["contact_address"], branch_id="pogranichnaya",
    )))
    response = post(client, sid="af1b-foreign-branch", request_id="q",
                    client_id="demo", q="Где вы?")
    assert response.status_code == 400


def test_empty_contact_fields_do_not_turn_address_question_into_phone(http_env) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_contact_raw([])))
    response = post(client, sid="af1b-empty-fields", request_id="q",
                    q="Где вы находитесь?")
    assert response.status_code == 400
    assert DEMO_PHONE not in response.get_data(as_text=True)
    assert len(fake.inputs) == 1


def test_branch_phones_are_labeled_without_arbitrary_call_button(http_env) -> None:
    client, _, use_provider, _ = http_env
    use_provider(FakeProvider(_contact_raw(["contact_phone"])))
    response = post(client, sid="af1b-all-branch-phones", request_id="q",
                    client_id="nikadent", q="Какие у вас телефоны?")
    assert response.status_code == 200, response.get_json()
    answer = response.get_json()["answer"]
    assert "Филиал 1" in answer and "Филиал 2" in answer
    assert "+7 (900) 444-69-97" in answer
    assert "+7 (914) 995-78-82" in answer
    assert response.get_json()["ui"]["buttons"] == []


def test_prompt_exposes_branch_ids_without_using_address_as_second_source(http_env) -> None:
    client, _, use_provider, _ = http_env
    fake = use_provider(FakeProvider(_contact_raw(["contact_address"])))
    response = post(client, sid="af1b-branch-prompt", request_id="q",
                    client_id="nikadent", q="Где вы?")
    assert response.status_code == 200, response.get_json()
    request = fake.inputs[0]
    policies = json.loads(request.model_view.clinic_policy_catalog_json)
    assert {item["branch_id"] for item in policies["contact_branches"]} == {
        "ryabikova", "pogranichnaya",
    }
    system, _ = build_d2_d1r_messages(request)
    assert "contact_branch_id" in system["content"]
    assert "pogranichnaya" in system["content"]
