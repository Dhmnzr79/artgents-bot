"""Active Demo widget offline checks: implant volume, scope clicks, follow-ups."""

from __future__ import annotations

import json
import re
import uuid
from datetime import date
from pathlib import Path

import pytest

import app as app_module
from contracts.ui_scope_action import build_ui_scope_ref
from evals.v5.run_bot_cleanup_live import compare_ask_stream_payloads
from session import bind_session_client, mem_reset, session_client_scope
from tests.session_binding_test_support import read_target_runtime_session_for
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
MANDATORY_EXCLUSION_FULL_ARCH = "КТ и костная пластика по показаниям — отдельно"
MANDATORY_EXCLUSION_ONE_TOOTH = "КТ при необходимости и временная коронка — отдельно"


def _clear_session_connection_cache() -> None:
    import session as session_module

    with session_module._lock:
        for conn in list(session_module._conns.values()):
            try:
                conn.close()
            except Exception:
                pass
        session_module._conns.clear()


@pytest.fixture
def isolated_demo_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    monkeypatch.setattr("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    monkeypatch.setattr("session.sqlite_path_for_client", _sqlite_path)
    bind_session_client("demo")
    yield
    _clear_session_connection_cache()


@pytest.fixture
def flask_app():
    return app_module.app


class _Backend:
    def __init__(self, output: str) -> None:
        self.output = output

    def generate(self, invocation, /):
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        on_raw_delta(self.output)
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _Backend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _general_overview_envelope(prose: str = "Стоимость зависит от объёма работы.") -> str:
    return answer_envelope(
        prose,
        commercial_intent="price",
        service_id=None,
        extent=None,
        scenario="cost",
        service_reference_status="none",
    )


def _scoped_model_envelope(prose: str) -> str:
    return answer_envelope(
        prose,
        commercial_intent="none",
        service_id=None,
        extent=None,
        scenario="none",
        service_reference_status="none",
    )


def _with_scope_commitment(envelope_json: str, commitment: str) -> str:
    payload = json.loads(envelope_json)
    payload["request_understanding"]["scope_commitment"] = commitment
    return json.dumps(payload, ensure_ascii=False)


def _with_reported_count(envelope_json: str, commitment: str, count: int | None) -> str:
    payload = json.loads(_with_scope_commitment(envelope_json, commitment))
    payload["request_understanding"]["tooth_count"] = count
    return json.dumps(payload, ensure_ascii=False)


def _for_other_person_current_care(
    envelope_json: str,
    *,
    commitment: str = "none",
    context: str = "current_care",
    count: int | None = None,
) -> str:
    payload = json.loads(envelope_json)
    payload["request_understanding"] = {
        "subjects": [{"subject_id": "s1", "relation": "other", "age_group": "adult"}],
        "scope_commitment": commitment,
        "tooth_count": count,
        "requests": [{
            "request_id": "r1",
            "kind": "price",
            "subject_id": "s1",
            "context": context,
            "policy_ids": [],
            "payment_scheme": "unspecified",
            "payment_scheme_intent": "unspecified",
            "contact_fields": [],
            "content_text": None,
            "content_ref": None,
        }],
    }
    payload["primary_price_request_id"] = "r1"
    return json.dumps(payload, ensure_ascii=False)


def _scope_clarify_envelope(axis: str = "extent") -> str:
    return answer_envelope(
        "Какая челюсть?" if axis == "jaw" else "Сколько зубов нужно восстановить?",
        route="CLARIFY", commercial_intent="price",
        service_id="classic", extent=None,
        service_reference_status="resolved", requested_service_id="classic",
        clarify_axis=axis, clarify_service_options=None,
        request_understanding={
            "subjects": [],
            "requests": [{"request_id": "r1", "kind": "price", "subject_id": None,
                          "context": "current_care"}],
            "scope_commitment": "unknown",
        },
        primary_price_request_id="r1",
    )


def _service_clarify_envelope() -> str:
    return answer_envelope(
        "Вас интересует All-on-4 или All-on-6?", route="CLARIFY",
        commercial_intent="price", service_id=None, extent=None,
        service_reference_status="unresolved", requested_service_id=None,
        clarify_axis="service", clarify_service_options=("all_on_4", "all_on_6"),
        request_understanding={
            "subjects": [],
            "requests": [{"request_id": "r1", "kind": "price", "subject_id": None,
                          "context": "current_care"}],
            "scope_commitment": "none",
        },
        primary_price_request_id="r1",
    )


def _run_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    backend: _Backend,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    _install_sales_fast(monkeypatch, backend)
    with session_client_scope("demo"):
        if reset_session:
            mem_reset(sid, client_id="demo")
    client = app_module.app.test_client()
    payload: dict = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    response = client.post("/ask", json=payload)
    assert response.status_code == 200
    body = response.get_json()
    assert isinstance(body, dict)
    return body


def _run_stream(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    backend: _Backend,
    user_message: str,
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    _install_sales_fast(monkeypatch, backend)
    with session_client_scope("demo"):
        if reset_session:
            mem_reset(sid, client_id="demo")
    client = app_module.app.test_client()
    payload: dict = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    response = client.post("/ask/stream", json=payload)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    return body


def _norm_digits(text: str) -> str:
    return re.sub(r"[^\d]", "", text or "")


def _offer_ids(payload: dict) -> tuple[str, ...]:
    offer = payload.get("offer")
    if not isinstance(offer, dict):
        return ()
    if offer.get("mode") == "exact_offer":
        offer_id = str(offer.get("offer_id") or "").strip()
        return (offer_id,) if offer_id else ()
    rows = offer.get("offers")
    if not isinstance(rows, list):
        return ()
    return tuple(
        str(row.get("offer_id") or "").strip()
        for row in rows
        if isinstance(row, dict) and str(row.get("offer_id") or "").strip()
    )


def _scope_ref(payload: dict, extent_token: str) -> tuple[str, str]:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if extent_token in ref:
            return ref, str(item.get("label") or "")
    raise AssertionError(f"missing scope ref for {extent_token}")


def test_broad_implantation_overview_and_scope_quick_replies(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = _general_overview_envelope()
    payload = _run_ask(
        monkeypatch,
        sid=f"demo-vol-broad-{uuid.uuid4().hex[:8]}",
        backend=_Backend(env),
        user_message="Сколько стоит имплантация?",
        envelope_json=env,
    )
    answer = str(payload.get("answer") or "")
    digits = _norm_digits(answer)
    assert "76200" in digits
    assert "318000" in digits
    quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") in quick_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") in quick_refs
    assert (payload.get("meta") or {}).get("service_topic") == "implantation"


@pytest.mark.parametrize("extent_token,expected_amounts", [("one_tooth", ("76200",)), ("full_arch", ("318000", "398000"))])
def test_scope_click_materializes_volume_prices_without_reasking(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    extent_token: str,
    expected_amounts: tuple[str, ...],
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-click-{extent_token}-{uuid.uuid4().hex[:8]}"
    t1_env = _general_overview_envelope()
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref, _ = _scope_ref(t1, extent_token)
    t2_env = _scoped_model_envelope("Модель без цен.")
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t2_env),
        user_message="",
        envelope_json=t2_env,
        ref=ref,
        reset_session=False,
    )
    digits = _norm_digits(str(t2.get("answer") or ""))
    for amount in expected_amounts:
        assert amount in digits
    scope_refs = {str(item.get("ref") or "") for item in t2.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") not in scope_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") not in scope_refs
    assert "уточните объём" not in str(t2.get("answer") or "").casefold()


def test_followup_a_skolko_after_full_arch_scope_keeps_arch_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-ask-{uuid.uuid4().hex[:8]}"
    t1_env = _general_overview_envelope()
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref, _ = _scope_ref(t1, "full_arch")
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(_scoped_model_envelope("x")),
        user_message="",
        envelope_json=_scoped_model_envelope("x"),
        ref=ref,
        reset_session=False,
    )
    follow_env = answer_envelope(
        "Стоимость по выбранному объёму.",
        commercial_intent="price",
        service_id=None,
        service_reference_status="none",
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(follow_env),
        user_message="А сколько?",
        envelope_json=follow_env,
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids
    assert all(oid.startswith("all_on_4.") or oid.startswith("all_on_6.") for oid in offer_ids)
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "318000" in digits or "398000" in digits
    assert "76200" not in digits


def test_explicit_other_service_after_full_arch_scope_does_not_inherit_implant_arch(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-other-{uuid.uuid4().hex[:8]}"
    t1_env = _general_overview_envelope()
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref, _ = _scope_ref(t1, "full_arch")
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(_scoped_model_envelope("x")),
        user_message="",
        envelope_json=_scoped_model_envelope("x"),
        ref=ref,
        reset_session=False,
    )
    after_scope = read_target_runtime_session_for(sid)
    assert after_scope.patient_facts is not None
    assert after_scope.patient_facts.extent == "full_arch"
    assert after_scope.patient_facts.topic == "implantation"

    switch_env = answer_envelope(
        "Съёмный протез зависит от типа конструкции.",
        commercial_intent="price",
        service_id="removable_dentures",
        extent="full_arch",
        service_reference_status="resolved",
        requested_service_id="removable_dentures",
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(switch_env),
        user_message="Сколько стоит съёмный протез?",
        envelope_json=switch_env,
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert not any(oid.startswith("all_on_4.") or oid.startswith("all_on_6.") for oid in offer_ids)
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "318000" not in digits
    assert "398000" not in digits
    if offer_ids:
        assert all(oid.startswith("removable_dentures.") for oid in offer_ids)
    assert (payload.get("meta") or {}).get("matched_service_id") == "removable_dentures"


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_other_person_current_care_clears_self_scope_and_offer_context(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-other-person-{uuid.uuid4().hex[:8]}"
    self_scope = _with_reported_count(answer_envelope(
        "Стоимость восстановления одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth", jaw="lower",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported", 1)
    runner(
        monkeypatch, sid=sid, backend=_Backend(self_scope),
        user_message="У меня нет одного зуба снизу. Сколько стоит имплантация?",
        envelope_json=self_scope,
    )
    before = read_target_runtime_session_for(sid)
    assert before.patient_facts is not None
    assert before.patient_facts.extent == "one_tooth"
    assert before.patient_facts.jaw == "lower"

    for_mother = _for_other_person_current_care(answer_envelope(
        "Для мамы сначала нужно уточнить объём восстановления.",
        commercial_intent="price", service_id=None, extent=None, jaw=None,
        service_reference_status="none", requested_service_id=None,
    ))
    other_reply = runner(
        monkeypatch, sid=sid, backend=_Backend(for_mother),
        user_message="А маме сколько стоит имплантация?",
        envelope_json=for_mother, reset_session=False,
    )
    assert "318000" in _norm_digits(str(other_reply.get("answer") or ""))
    after = read_target_runtime_session_for(sid)
    assert after.patient_facts is None

    vague = answer_envelope(
        "Уточните объём восстановления.", commercial_intent="price",
        service_id=None, extent=None, service_reference_status="none",
    )
    continued = runner(
        monkeypatch, sid=sid, backend=_Backend(vague),
        user_message="А сколько?", envelope_json=vague, reset_session=False,
    )
    assert "76200" not in _norm_digits(str(continued.get("answer") or ""))
    assert "уточните объём" in str(continued.get("answer") or "").casefold()
    assert read_target_runtime_session_for(sid).patient_facts is None


def test_other_person_past_history_does_not_clear_self_scope(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"demo-other-history-{uuid.uuid4().hex[:8]}"
    self_scope = _with_reported_count(answer_envelope(
        "Стоимость восстановления одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported", 1)
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(self_scope),
        user_message="У меня нет одного зуба. Сколько стоит имплантация?",
        envelope_json=self_scope,
    )
    history = _for_other_person_current_care(answer_envelope(
        "В детстве маме уже лечили зуб.", commercial_intent="none",
        service_id=None, extent=None, service_reference_status="none",
    ), context="past_history")
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(history),
        user_message="У мамы в детстве уже лечили зуб.",
        envelope_json=history, reset_session=False,
    )
    saved = read_target_runtime_session_for(sid).patient_facts
    assert saved is not None
    assert saved.extent == "one_tooth"
    assert saved.tooth_count == 1


def test_other_person_reported_scope_replaces_self_scope_without_old_jaw(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"demo-other-reported-{uuid.uuid4().hex[:8]}"
    self_scope = _with_reported_count(answer_envelope(
        "Стоимость восстановления одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth", jaw="lower",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported", 1)
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(self_scope),
        user_message="У меня нет одного зуба снизу.", envelope_json=self_scope,
    )
    mother_scope = _for_other_person_current_care(answer_envelope(
        "Для мамы нужно восстановить три зуба.", commercial_intent="none",
        service_id="classic", extent="few_teeth", jaw=None,
        service_reference_status="resolved", requested_service_id="classic",
    ), commitment="reported", count=3)
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(mother_scope),
        user_message="Маме нужно восстановить три зуба.",
        envelope_json=mother_scope, reset_session=False,
    )
    saved = read_target_runtime_session_for(sid).patient_facts
    assert saved is not None
    assert saved.extent == "few_teeth"
    assert saved.tooth_count == 3
    assert saved.jaw is None


def test_service_detour_keeps_reported_need_without_pricing_other_service_from_it(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-detour-{uuid.uuid4().hex[:8]}"
    reported = _with_scope_commitment(answer_envelope(
        "Стоимость восстановления одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported")
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(reported),
        user_message="У меня нет одного зуба. Сколько стоит имплантация?",
        envelope_json=reported,
    )
    assert read_target_runtime_session_for(sid).patient_facts.extent == "one_tooth"

    other = answer_envelope(
        "Стоимость съёмного протеза зависит от конструкции.",
        commercial_intent="price", service_id="removable_dentures",
        service_reference_status="resolved", requested_service_id="removable_dentures",
    )
    other_reply = _run_ask(
        monkeypatch, sid=sid, backend=_Backend(other),
        user_message="А сколько стоит съёмный протез?",
        envelope_json=other, reset_session=False,
    )
    assert (other_reply.get("meta") or {}).get("matched_service_id") == "removable_dentures"
    assert "76200" not in _norm_digits(str(other_reply.get("answer") or ""))
    saved = read_target_runtime_session_for(sid).patient_facts
    assert saved is not None and saved.extent == "one_tooth" and saved.topic == "implantation"

    back = answer_envelope(
        "Стоимость имплантации.", commercial_intent="price",
        service_id="classic", service_reference_status="resolved",
        requested_service_id="classic",
    )
    back_reply = _run_ask(
        monkeypatch, sid=sid, backend=_Backend(back),
        user_message="Вернёмся к имплантации. Сколько стоит?",
        envelope_json=back, reset_session=False,
    )
    assert "76200" in _norm_digits(str(back_reply.get("answer") or ""))


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_ambiguous_service_switch_does_not_reuse_old_tooth_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    sid = f"demo-vol-ambiguous-{uuid.uuid4().hex[:8]}"
    reported = _with_reported_count(answer_envelope(
        "Стоимость восстановления одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported", 1)
    runner(
        monkeypatch, sid=sid, backend=_Backend(reported),
        user_message="У меня нет одного зуба. Сколько стоит имплантация?",
        envelope_json=reported,
    )
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 1

    ambiguous = _service_clarify_envelope()
    question = runner(
        monkeypatch, sid=sid, backend=_Backend(ambiguous),
        user_message="Теперь хочу узнать цену восстановления всей челюсти, какой вариант?",
        envelope_json=ambiguous, reset_session=False,
    )
    assert "76200" not in _norm_digits(str(question.get("answer") or ""))
    assert {item["ref"] for item in question.get("quick_replies") or []} == {
        "target:ui_service/all_on_4", "target:ui_service/all_on_6",
    }
    saved = read_target_runtime_session_for(sid).patient_facts
    assert saved is not None and saved.extent == "one_tooth" and saved.tooth_count == 1

    vague = answer_envelope(
        "Уточните вариант восстановления.", commercial_intent="price",
        service_id=None, extent=None, service_reference_status="none",
    )
    after = runner(
        monkeypatch, sid=sid, backend=_Backend(vague),
        user_message="А сколько?", envelope_json=vague, reset_session=False,
    )
    assert "76200" not in _norm_digits(str(after.get("answer") or ""))
    assert (after.get("meta") or {}).get("matched_service_id") != "classic"
    assert str(after.get("answer") or "").strip()
    assert (after.get("meta") or {}).get("error_code") is None
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 1

    back = answer_envelope(
        "Стоимость имплантации.", commercial_intent="price",
        service_id="classic", service_reference_status="resolved",
        requested_service_id="classic",
    )
    returned = runner(
        monkeypatch, sid=sid, backend=_Backend(back),
        user_message="Вернёмся к имплантации одного зуба. Сколько стоит?",
        envelope_json=back, reset_session=False,
    )
    assert "76200" in _norm_digits(str(returned.get("answer") or ""))
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 1


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_ambiguous_service_choice_prices_selected_jaw_without_replacing_need(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-ambiguous-click-{uuid.uuid4().hex[:8]}"
    reported = _with_reported_count(answer_envelope(
        "Стоимость одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported", 1)
    runner(
        monkeypatch, sid=sid, backend=_Backend(reported),
        user_message="У меня нет одного зуба. Сколько стоит имплантация?",
        envelope_json=reported,
    )
    ambiguous = _service_clarify_envelope()
    question = runner(
        monkeypatch, sid=sid, backend=_Backend(ambiguous),
        user_message="Теперь интересует вся челюсть. Какой вариант?",
        envelope_json=ambiguous, reset_session=False,
    )
    selected_ref = next(
        item["ref"] for item in question.get("quick_replies") or []
        if item["ref"] == "target:ui_service/all_on_4"
    )
    quote = answer_envelope(
        "Стоимость All-on-4 за челюсть.", commercial_intent="price",
        service_id="all_on_4", extent="full_arch",
        service_reference_status="resolved", requested_service_id="all_on_4",
    )
    selected = runner(
        monkeypatch, sid=sid, backend=_Backend(quote),
        user_message="", envelope_json=quote, ref=selected_ref,
        reset_session=False,
    )
    digits = _norm_digits(str(selected.get("answer") or ""))
    assert "318000" in digits
    assert "76200" not in digits
    assert (selected.get("meta") or {}).get("matched_service_id") == "all_on_4"
    saved = read_target_runtime_session_for(sid).patient_facts
    assert saved is not None and saved.extent == "one_tooth" and saved.tooth_count == 1


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_exact_reported_count_correction_hypothetical_and_unspecified_correction(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    sid = f"demo-vol-count-{uuid.uuid4().hex[:8]}"

    def turn(
        message: str, commitment: str, count: int | None, *,
        reset: bool, extent: str | None = "few_teeth",
    ) -> None:
        env = _with_reported_count(answer_envelope(
            "Понял объём лечения.", commercial_intent="none",
            service_id="classic", extent=extent,
            service_reference_status="resolved", requested_service_id="classic",
        ), commitment, count)
        runner(
            monkeypatch, sid=sid, backend=_Backend(env),
            user_message=message, envelope_json=env, reset_session=reset,
        )

    turn("У меня нет двух зубов", "reported", 2, reset=True)
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 2
    turn("Нет, трёх", "correction", 3, reset=False, extent=None)
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 3
    turn("А если четыре?", "hypothetical", 4, reset=False)
    assert read_target_runtime_session_for(sid).patient_facts.tooth_count == 3
    turn("Точнее, несколько зубов, число пока не знаю", "correction", None, reset=False)
    facts = read_target_runtime_session_for(sid).patient_facts
    assert facts is not None and facts.extent == "few_teeth" and facts.tooth_count is None


def test_correction_one_tooth_after_full_arch_scope_click(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-corr-{uuid.uuid4().hex[:8]}"
    t1_env = _general_overview_envelope()
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref, _ = _scope_ref(t1, "full_arch")
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(_scoped_model_envelope("x")),
        user_message="",
        envelope_json=_scoped_model_envelope("x"),
        ref=ref,
        reset_session=False,
    )
    correction_env = _with_scope_commitment(answer_envelope(
        "Классическая имплантация одного зуба.",
        commercial_intent="price",
        service_id="classic",
        extent="one_tooth",
        service_reference_status="resolved",
        requested_service_id="classic",
    ), "correction")
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(correction_env),
        user_message="Нет, я имел в виду один зуб",
        envelope_json=correction_env,
        reset_session=False,
    )
    session = read_target_runtime_session_for(sid)
    assert session.patient_facts is not None
    assert session.patient_facts.extent == "one_tooth"
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "76200" in digits
    assert "318000" not in digits
    offer_ids = _offer_ids(payload)
    assert offer_ids
    assert all(oid.startswith("classic.one_tooth.") for oid in offer_ids)


def test_correction_one_tooth_persists_on_next_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-corr-next-{uuid.uuid4().hex[:8]}"
    t1_env = _general_overview_envelope()
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref, _ = _scope_ref(t1, "full_arch")
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(_scoped_model_envelope("x")),
        user_message="",
        envelope_json=_scoped_model_envelope("x"),
        ref=ref,
        reset_session=False,
    )
    correction_env = _with_scope_commitment(answer_envelope(
        "Классическая имплантация одного зуба.",
        commercial_intent="price",
        service_id="classic",
        extent="one_tooth",
        service_reference_status="resolved",
        requested_service_id="classic",
    ), "correction")
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(correction_env),
        user_message="Нет, я имел в виду один зуб",
        envelope_json=correction_env,
        reset_session=False,
    )
    session = read_target_runtime_session_for(sid)
    assert session.patient_facts is not None
    assert session.patient_facts.extent == "one_tooth"

    follow_env = answer_envelope(
        "Стоимость по объёму.",
        commercial_intent="price",
        service_id=None,
        service_reference_status="none",
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_Backend(follow_env),
        user_message="Сколько стоит?",
        envelope_json=follow_env,
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids
    assert all(oid.startswith("classic.one_tooth.") for oid in offer_ids)
    assert "76200" in _norm_digits(str(payload.get("answer") or ""))
    assert "318000" not in _norm_digits(str(payload.get("answer") or ""))


def test_explicit_all_on_4_not_priced_as_single_tooth_overview(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = answer_envelope(
        "All-on-4 за челюсть.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
    )
    payload = _run_ask(
        monkeypatch,
        sid=f"demo-vol-a4-{uuid.uuid4().hex[:8]}",
        backend=_Backend(env),
        user_message="Сколько стоит All-on-4?",
        envelope_json=env,
    )
    meta = payload.get("meta") or {}
    assert meta.get("matched_service_id") == "all_on_4"
    digits = _norm_digits(str(payload.get("answer") or ""))
    assert "318000" in digits
    assert digits.count("76200") == 0
    quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") not in quick_refs


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_all_on_4_both_jaws_quotes_one_jaw_unit_without_total(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = answer_envelope(
        "Стоимость All-on-4 для обеих челюстей.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        jaw="both",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
    )
    sid = f"demo-vol-both-{uuid.uuid4().hex[:8]}"
    payload = runner(
        monkeypatch,
        sid=sid,
        backend=_Backend(env),
        user_message="Сколько стоит All-on-4 на обе челюсти?",
        envelope_json=env,
    )
    answer = str(payload.get("answer") or "").casefold()
    digits = _norm_digits(answer)
    assert "318000" in digits
    assert "за одну челюсть" in answer
    assert "обе челюсти" in answer
    assert "636000" not in digits
    # Asking for a quote does not confirm the patient's treatment need.
    assert read_target_runtime_session_for(sid).patient_facts is None


def test_hypothetical_full_jaw_quote_does_not_replace_reported_one_tooth(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    sid = f"demo-vol-hypothetical-{uuid.uuid4().hex[:8]}"
    reported = _with_scope_commitment(answer_envelope(
        "Стоимость одного зуба.",
        commercial_intent="price",
        service_id="classic",
        extent="one_tooth",
        service_reference_status="resolved",
        requested_service_id="classic",
    ), "reported")
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(reported),
        user_message="У меня нет одного зуба. Сколько стоит восстановить?",
        envelope_json=reported,
    )
    assert read_target_runtime_session_for(sid).patient_facts.extent == "one_tooth"

    hypothetical = _with_scope_commitment(answer_envelope(
        "Стоимость восстановления челюсти.",
        commercial_intent="price",
        service_id="all_on_4",
        extent="full_arch",
        service_reference_status="resolved",
        requested_service_id="all_on_4",
    ), "hypothetical")
    payload = _run_ask(
        monkeypatch, sid=sid, backend=_Backend(hypothetical),
        user_message="А если всю челюсть?",
        envelope_json=hypothetical, reset_session=False,
    )
    assert "318000" in _norm_digits(str(payload.get("answer") or ""))
    assert read_target_runtime_session_for(sid).patient_facts.extent == "one_tooth"


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
@pytest.mark.parametrize("axis,labels", [
    ("extent", {"Один зуб", "Несколько зубов", "Вся челюсть", "Не знаю"}),
    ("jaw", {"Верхняя", "Нижняя", "Обе", "Не знаю"}),
])
def test_extent_clarification_unknown_button_exits_without_scope(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
    axis,
    labels,
) -> None:
    from core.sales_fast_presentation import D2_SCOPE_DESCRIBE_REF, D2_SCOPE_UNKNOWN_REF

    sid = f"demo-vol-unknown-{uuid.uuid4().hex[:8]}"
    clarify = _scope_clarify_envelope(axis)
    first = runner(
        monkeypatch, sid=sid, backend=_Backend(clarify),
        user_message="Сколько будет стоить восстановление?",
        envelope_json=clarify,
    )
    choices = {item["label"]: item["ref"] for item in first.get("quick_replies") or []}
    assert set(choices) == labels
    assert choices["Не знаю"] == D2_SCOPE_UNKNOWN_REF

    unknown = runner(
        monkeypatch, sid=sid, backend=_Backend("invalid"),
        user_message="", envelope_json="invalid", ref=D2_SCOPE_UNKNOWN_REF,
        reset_session=False,
    )
    assert "Ничего страшного" in str(unknown.get("answer") or "")
    assert "Сколько зубов" not in str(unknown.get("answer") or "")
    assert read_target_runtime_session_for(sid).patient_facts is None
    next_choices = {item["label"]: item["ref"] for item in unknown.get("quick_replies") or []}
    assert set(next_choices) == {"Описать ситуацию", "Записаться на консультацию"}

    describe = runner(
        monkeypatch, sid=sid, backend=_Backend("invalid"),
        user_message="", envelope_json="invalid", ref=D2_SCOPE_DESCRIBE_REF,
        reset_session=False,
    )
    assert "Опишите" in str(describe.get("answer") or "")
    assert read_target_runtime_session_for(sid).patient_facts is None

    stale = runner(
        monkeypatch, sid=sid, backend=_Backend("invalid"),
        user_message="", envelope_json="invalid", ref=D2_SCOPE_UNKNOWN_REF,
        reset_session=False,
    )
    assert (stale.get("meta") or {}).get("service_route") == "sales_fast_followup_unknown"


@pytest.mark.parametrize("runner", (_run_ask, _run_stream))
def test_extent_clarification_choice_enters_single_model_path(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    runner,
) -> None:
    sid = f"demo-vol-choice-{uuid.uuid4().hex[:8]}"
    clarify = _scope_clarify_envelope()
    first = runner(
        monkeypatch, sid=sid, backend=_Backend(clarify),
        user_message="Сколько будет стоить восстановление?",
        envelope_json=clarify,
    )
    choice = next(
        item["ref"] for item in first.get("quick_replies") or []
        if item["label"] == "Один зуб"
    )
    reported = _with_scope_commitment(answer_envelope(
        "Стоимость одного зуба.", commercial_intent="price",
        service_id="classic", extent="one_tooth",
        service_reference_status="resolved", requested_service_id="classic",
    ), "reported")
    selected = runner(
        monkeypatch, sid=sid, backend=_Backend(reported),
        user_message="", envelope_json=reported, ref=choice, reset_session=False,
    )
    assert "76200" in _norm_digits(str(selected.get("answer") or ""))
    assert read_target_runtime_session_for(sid).patient_facts.extent == "one_tooth"


@pytest.mark.parametrize("axis,question", [
    ("extent", "Сколько зубов нужно восстановить"),
    ("jaw", "Какую челюсть нужно восстановить"),
])
def test_code_deferred_scope_question_matches_buttons_and_clears_stale_refs(
    isolated_demo_sqlite,
    axis,
    question,
) -> None:
    from core.sales_fast_presentation import materialize_dialogue_price_clarify_payload

    sid = f"demo-vol-defer-{uuid.uuid4().hex[:8]}"
    scope = materialize_dialogue_price_clarify_payload(
        client_id="demo", sid=sid, clarify_axis=axis,
    )
    assert question in str(scope.payload["answer"])
    assert scope.payload["quick_replies"]
    old_ref = scope.payload["quick_replies"][0]["ref"]
    assert old_ref in {item.ref for item in read_target_runtime_session_for(sid).followups}

    generic = materialize_dialogue_price_clarify_payload(client_id="demo", sid=sid)
    assert generic.payload["quick_replies"] == []
    assert old_ref not in {item.ref for item in read_target_runtime_session_for(sid).followups}


def test_unknown_scope_consultation_button_requires_model_booking_decision(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    from core.sales_fast_presentation import D2_SCOPE_BOOK_REF, D2_SCOPE_UNKNOWN_REF

    sid = f"demo-vol-book-{uuid.uuid4().hex[:8]}"
    clarify = _scope_clarify_envelope()
    _run_ask(
        monkeypatch, sid=sid, backend=_Backend(clarify),
        user_message="Сколько будет стоить восстановление?",
        envelope_json=clarify,
    )
    unknown = _run_ask(
        monkeypatch, sid=sid, backend=_Backend("invalid"),
        user_message="", envelope_json="invalid", ref=D2_SCOPE_UNKNOWN_REF,
        reset_session=False,
    )
    assert D2_SCOPE_BOOK_REF in {
        item["ref"] for item in unknown.get("quick_replies") or []
    }
    no_booking_request = answer_envelope("Запись обсудим после уточнения.")
    clicked = _run_ask(
        monkeypatch, sid=sid, backend=_Backend(no_booking_request),
        user_message="", envelope_json=no_booking_request, ref=D2_SCOPE_BOOK_REF,
        reset_session=False,
    )
    assert (clicked.get("meta") or {}).get("service_route") == "sales_fast_materialized"
    assert (clicked.get("meta") or {}).get("lead_step") != "name"
    assert read_target_runtime_session_for(sid).patient_facts is None

def test_broad_overview_ask_and_stream_ui_parity(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 10),
    )
    env = _general_overview_envelope()
    q = "Сколько стоит имплантация?"
    sid_ask = f"demo-vol-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"demo-vol-parity-stream-{uuid.uuid4().hex[:8]}"
    ask_payload = _run_ask(
        monkeypatch,
        sid=sid_ask,
        backend=_Backend(env),
        user_message=q,
        envelope_json=env,
    )
    stream_payload = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=_Backend(env),
        user_message=q,
        envelope_json=env,
    )
    assert compare_ask_stream_payloads(ask_payload, stream_payload) == []
    for payload in (ask_payload, stream_payload):
        quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
        assert build_ui_scope_ref(topic="implantation", extent="one_tooth") in quick_refs
        assert build_ui_scope_ref(topic="implantation", extent="full_arch") in quick_refs
