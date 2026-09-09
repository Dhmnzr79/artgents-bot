"""Offline tests for BOT-CLEANUP-UI-SERVICE-FLOW-1."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import config
import pytest

import app as app_module
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_service_action import build_ui_service_ref
from core.one_call_envelope_protocol import OneCallEnvelopeProtocolError, parse_production_envelope_json
from core.one_call_prompt_contract import ONE_CALL_MODEL_SNAPSHOT
from core.pending_price_clarify import read_pending_price_clarify
from core.sales_one_plus_live_backend import sales_one_plus_model
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from core.target_runtime_session import read_target_runtime_session
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_one_plus_turn import (
    _DEMO_CATALOG,
    _DEMO_COMMERCIAL_CATALOG,
    _DEMO_REF_CATALOG,
    _EMPTY_CATALOG,
    _EMPTY_COMMERCIAL_CATALOG,
    _EMPTY_REF_CATALOG,
    answer_envelope,
    admin_envelope,
)

_REPO = Path(__file__).resolve().parents[1]


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


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0
        self.last_invocation = None

    def generate(self, invocation, /):
        self.call_count += 1
        self.last_invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.last_invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        on_raw_delta(str(self.output))
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _clarify_service_envelope(text: str, *, options: list[str]) -> str:
    return answer_envelope(
        text,
        route="CLARIFY",
        commercial_intent="price",
        promotion_scope="none",
        clarify_axis="service",
        clarify_service_options=options,
        service_reference_status="none",
        requested_service_id=None,
    )


def _neutral_price_answer_envelope(text: str = "Актуальная стоимость по выбранной услуге.") -> str:
    return answer_envelope(
        text,
        commercial_intent="price",
        service_id=None,
        extent=None,
        service_reference_status="none",
        requested_service_id=None,
    )


def _run_ask(
    monkeypatch: pytest.MonkeyPatch,
    *,
    sid: str,
    backend: _CountingBackend,
    user_message: str = "",
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
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
    backend: _CountingBackend,
    user_message: str = "",
    envelope_json: str,
    ref: str | None = None,
    reset_session: bool = True,
) -> dict:
    _install_sales_fast(monkeypatch, backend)
    if reset_session:
        mem_reset(sid)
    client = app_module.app.test_client()
    payload = {"q": user_message, "sid": sid, "client_id": "demo"}
    if ref:
        payload["ref"] = ref
    response = client.post("/ask/stream", json=payload)
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    assert "event: ui" in text
    assert "event: done" in text
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    return body


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


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


def _pending_snapshot(sid: str) -> dict[str, object] | None:
    pending = read_pending_price_clarify(mem_get(sid))
    if pending is None:
        return None
    return {
        "kind": pending.kind,
        "allowed_service_ids": tuple(pending.allowed_service_ids),
        "set_at_turn": pending.set_at_turn,
    }


def _user_visible_result_snapshot(sid: str, payload: dict) -> dict:
    meta = payload.get("meta") or {}
    return {
        "answer": payload.get("answer"),
        "offer": payload.get("offer"),
        "quick_replies": payload.get("quick_replies"),
        "cta": payload.get("cta"),
        "video": payload.get("video"),
        "meta": {
            key: meta.get(key)
            for key in (
                "matched_service_id",
                "service_topic",
                "service_route",
                "followup_count",
                "terminal_mode",
                "answer_path",
                "cta_key",
                "cta_action",
            )
            if key in meta
        },
        "session": _session_fields(sid),
        "pending_price_clarify": _pending_snapshot(sid),
    }


def _count_amount(answer: str, amount: int) -> int:
    return _norm_digits(answer).count(str(amount))


def _session_fields(sid: str) -> dict[str, object]:
    session = read_target_runtime_session(sid)
    return {
        "last_service_id": session.last_service_id,
        "last_displayed_offer_ids": tuple(session.last_displayed_offer_ids),
        "last_selected_offer_id": session.last_selected_offer_id,
    }


def _general_implantation_envelope(prose: str) -> str:
    return answer_envelope(
        prose,
        commercial_intent="price",
        service_id=None,
        extent=None,
        scenario="cost",
        service_reference_status="none",
    )


def _user_history(sid: str) -> list[str]:
    return [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["target_runtime_followups"] = [
            {
                "ref": item.ref,
                "label": item.label,
                **({"client_id": item.client_id} if item.client_id else {}),
            }
            for item in items
        ]
        _persist_unlocked(sid, st)


@pytest.fixture
def flask_app():
    return app_module.app


def test_two_turn_service_click_via_ask_and_stream(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    options = ["classic", "all_on_4", "all_on_6"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope(
            "Уточните, какой вариант вас интересует.",
            options=options,
        )
    )
    answer_backend = _CountingBackend(_neutral_price_answer_envelope())
    sid = f"ui-flow-ask-{uuid.uuid4().hex[:8]}"

    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    quick = list(t1.get("quick_replies") or [])
    assert quick
    chosen = next(item for item in quick if "all_on_4" in str(item.get("ref") or ""))
    ref = str(chosen["ref"])
    label = str(chosen["label"])

    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="",
        envelope_json=answer_backend.output,
        ref=ref,
        reset_session=False,
    )
    assert (t2.get("meta") or {}).get("matched_service_id") == "all_on_4"
    assert "уточните" not in str(t2.get("answer") or "").lower()
    session = _session_fields(sid)
    assert session["last_service_id"] == "all_on_4"
    assert session["last_displayed_offer_ids"]
    assert label in _user_history(sid)
    assert "продолжить" not in _user_history(sid)

    sid_stream = f"ui-flow-stream-{uuid.uuid4().hex[:8]}"
    clarify_backend_stream = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    answer_backend_stream = _CountingBackend(_neutral_price_answer_envelope())
    t1s = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=clarify_backend_stream,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend_stream.output,
    )
    quick_s = list(t1s.get("quick_replies") or [])
    ref_s = str(next(item for item in quick_s if item.get("ref"))["ref"])
    label_s = str(next(item for item in quick_s if item.get("label"))["label"])
    t2s = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=answer_backend_stream,
        user_message="",
        envelope_json=answer_backend_stream.output,
        ref=ref_s,
        reset_session=False,
    )
    assert (t2s.get("meta") or {}).get("matched_service_id") == "classic"
    assert label_s in _user_history(sid_stream)
    assert answer_backend_stream.last_invocation is not None
    hints = answer_backend_stream.last_invocation.sales_context or {}
    assert hints.get("catalog_service_hint") != "all_on_4"


def test_zygomatic_service_click_price_control(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-zygo-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ref = build_ui_service_ref(service_id="zygomatic_implants")
    label = "Скуловая имплантация"
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label=label, client_id="demo"))
    backend = _CountingBackend(_neutral_price_answer_envelope("Стоимость скуловой имплантации."))
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=backend,
        envelope_json=backend.output,
        ref=ref,
        reset_session=False,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    assert "420000" in answer
    assert (payload.get("meta") or {}).get("matched_service_id") == "zygomatic_implants"
    assert "zygomatic_implants" in _offer_ids(payload) or any(
        offer_id.startswith("zygomatic_implants.") for offer_id in _offer_ids(payload)
    )
    assert label in _user_history(sid)
    assert (payload.get("meta") or {}).get("service_route") != "sales_fast_error"


def test_classic_service_click_multi_brand_overview(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-classic-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    t1_backend = _CountingBackend(
        _clarify_service_envelope("Какой вариант интересует?", options=options)
    )
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t1_backend,
        user_message="Сколько стоит?",
        envelope_json=t1_backend.output,
    )
    ref = str(
        next(item["ref"] for item in t1["quick_replies"] if "classic" in str(item.get("ref")))
    )
    t2_backend = _CountingBackend(_neutral_price_answer_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t2_backend,
        user_message="",
        envelope_json=t2_backend.output,
        ref=ref,
        reset_session=False,
    )
    offer_ids = set(_offer_ids(payload))
    assert "classic.one_tooth.implantium" in offer_ids
    assert "classic.one_tooth.impro" in offer_ids
    assert any("nobel" in offer_id for offer_id in offer_ids)
    assert (payload.get("meta") or {}).get("service_route") != "sales_fast_error"


def test_pending_price_text_resolves_allowed_service(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-text-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4", "all_on_6"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    pending = read_pending_price_clarify(mem_get(sid))
    assert pending is not None
    assert "classic" in pending.allowed_service_ids

    answer_backend = _CountingBackend(_neutral_price_answer_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="классическая имплантация",
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    assert (payload.get("meta") or {}).get("matched_service_id") == "classic"
    assert read_pending_price_clarify(mem_get(sid)) is None


@pytest.mark.parametrize(
    ("case", "setup"),
    [
        ("unshown", lambda sid: None),
        (
            "wrong_client",
            lambda sid: _seed_followups(
                sid,
                TargetRuntimeFollowupItem(
                    ref=build_ui_service_ref(service_id="classic"),
                    label="Классическая имплантация",
                    client_id="nikadent",
                ),
            ),
        ),
        (
            "inactive_service",
            lambda sid: _seed_followups(
                sid,
                TargetRuntimeFollowupItem(
                    ref=build_ui_service_ref(service_id="braces"),
                    label="Брекеты",
                    client_id="demo",
                ),
            ),
        ),
        (
            "not_in_pending",
            lambda sid: (
                _seed_followups(
                    sid,
                    TargetRuntimeFollowupItem(
                        ref=build_ui_service_ref(service_id="all_on_6"),
                        label="All-on-6",
                        client_id="demo",
                    ),
                ),
                _run_pending_write(sid, ["classic", "all_on_4"]),
            ),
        ),
    ],
)
def test_negative_ui_service_refs_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    case: str,
    setup,
) -> None:
    sid = f"ui-flow-neg-{case}-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    setup(sid)
    ref = build_ui_service_ref(
        service_id="all_on_6" if case == "not_in_pending" else "classic"
    )
    if case == "inactive_service":
        ref = build_ui_service_ref(service_id="braces")
    backend = _CountingBackend(_neutral_price_answer_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=backend,
        envelope_json=backend.output,
        ref=ref,
        reset_session=False,
    )
    meta = payload.get("meta") or {}
    assert meta.get("service_route") in {
        "sales_fast_followup_unknown",
        "sales_fast_dialogue_price_clarify",
    } or meta.get("terminal_mode") == "clarify"


def _run_pending_write(sid: str, allowed: list[str]) -> None:
    from core.pending_price_clarify import write_pending_price_clarify
    from session import _lock, _persist_unlocked, mem_get

    with _lock:
        st = mem_get(sid)
        st["session_turn_count"] = 1
        _persist_unlocked(sid, st)
    write_pending_price_clarify(
        sid,
        allowed_service_ids=tuple(allowed),
        session_turn_count=1,
    )


def test_stale_pending_not_used_after_reset(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-stale-{uuid.uuid4().hex[:8]}"
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните.", options=["classic", "all_on_4"])
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    mem_reset(sid)
    answer_backend = _CountingBackend(_neutral_price_answer_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="классическая имплантация",
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    assert (payload.get("meta") or {}).get("matched_service_id") != "classic"


@pytest.mark.parametrize("route", ("CLARIFY", "ADMIN"))
def test_terminal_direct_fact_ids_are_cleared_not_rejected(route: str) -> None:
    overrides: dict[str, object] = {
        "route": route,
        "references": {"direct_fact_ids": ["installment_12"]},
    }
    if route == "CLARIFY":
        overrides.update(
            patient_text="Уточните масштаб.",
            clarify_axis="extent",
            clarify_service_options=None,
        )
    else:
        overrides.update(patient_text=None, clarify_axis=None, clarify_service_options=None)
    from core.one_call_envelope_protocol import production_envelope_template

    payload = production_envelope_template(**overrides)
    envelope = parse_production_envelope_json(
        json.dumps(payload),
        active_service_catalog=_DEMO_CATALOG,
        service_reference_catalog=_DEMO_REF_CATALOG,
        commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
    )
    assert envelope.references.direct_fact_ids == ()


def test_terminal_direct_fact_ids_invalid_type_still_errors() -> None:
    from core.one_call_envelope_protocol import production_envelope_template

    payload = production_envelope_template(
        route="CLARIFY",
        patient_text="Уточните.",
        clarify_axis="extent",
        references={"direct_fact_ids": "installment_12"},
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_invalid"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_EMPTY_CATALOG,
            service_reference_catalog=_EMPTY_REF_CATALOG,
            commercial_fact_catalog=_EMPTY_COMMERCIAL_CATALOG,
        )


def test_answer_direct_fact_ids_rules_unchanged() -> None:
    from core.one_call_envelope_protocol import production_envelope_template

    payload = production_envelope_template(
        route="ANSWER",
        patient_text="Про рассрочку.",
        references={"direct_fact_ids": [True]},
    )
    with pytest.raises(OneCallEnvelopeProtocolError, match="direct_fact_ids_invalid"):
        parse_production_envelope_json(
            json.dumps(payload),
            active_service_catalog=_DEMO_CATALOG,
            service_reference_catalog=_DEMO_REF_CATALOG,
            commercial_fact_catalog=_DEMO_COMMERCIAL_CATALOG,
        )


def test_general_implantation_price_overview_without_zygomatic(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-general-{uuid.uuid4().hex[:8]}"
    backend = _CountingBackend(
        _general_implantation_envelope("Стоимость зависит от объёма работы.")
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=backend.output,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    meta = payload.get("meta") or {}
    assert meta.get("service_topic") == "implantation"
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") in quick_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") in quick_refs
    assert "zygomatic" not in " ".join(quick_refs).lower()
    assert not _offer_ids(payload) or not any("zygomatic" in oid for oid in _offer_ids(payload))
    assert "76200" in answer
    assert "318000" in answer
    assert _count_amount(answer, 76200) == 1
    assert _count_amount(answer, 318000) == 1
    assert "уточните" in answer.lower() or "один зуб" in answer.lower() or "челюсть" in answer.lower()


@pytest.mark.parametrize(
    ("model_prose", "forbidden_amounts"),
    [
        (
            "Классическая имплантация — 76 200 ₽. All-on-4 — 999 999 ₽ за челюсть. Стоимость зависит от объёма.",
            (999999,),
        ),
        (
            "Классическая имплантация — 76 200 ₽ за зуб. All-on-4 — 318 000 ₽ за челюсть. Стоимость зависит от объёма.",
            (),
        ),
        (
            "Ориентир: 50 000 ₽ за зуб и 400 000 ₽ за челюсть. Стоимость зависит от объёма.",
            (50000, 400000),
        ),
    ],
)
def test_broad_family_price_strips_hostile_model_amounts(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    model_prose: str,
    forbidden_amounts: tuple[int, ...],
) -> None:
    sid = f"ui-flow-hostile-{uuid.uuid4().hex[:8]}"
    backend = _CountingBackend(_general_implantation_envelope(model_prose))
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=backend.output,
    )
    answer = str(payload.get("answer") or "")
    normalized = _norm_digits(answer)
    assert "76200" in normalized
    assert "318000" in normalized
    assert _count_amount(answer, 76200) == 1
    assert _count_amount(answer, 318000) == 1
    for amount in forbidden_amounts:
        assert str(amount) not in normalized


def test_pending_text_does_not_set_governed_ui_hint(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-text-auth-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    answer_backend = _CountingBackend(_neutral_price_answer_envelope())
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="классическая имплантация",
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    hints = answer_backend.last_invocation.sales_context or {}
    assert hints.get("governed_ui_service_id") is None


def test_envelope_service_beats_pending_text_candidate(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-env-beat-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    answer_backend = _CountingBackend(
        answer_envelope(
            "Цена All-on-4.",
            commercial_intent="price",
            service_id="all_on_4",
            extent=None,
            service_reference_status="none",
        )
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="классическая имплантация",
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    assert (payload.get("meta") or {}).get("matched_service_id") == "all_on_4"


def test_pending_text_outside_allowed_services_not_applied(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-text-out-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    answer_backend = _CountingBackend(_neutral_price_answer_envelope())
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message="скуловая имплантация",
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    assert (payload.get("meta") or {}).get("matched_service_id") != "zygomatic_implants"
    assert read_pending_price_clarify(mem_get(sid)) is None


@pytest.mark.parametrize(
    "user_message",
    [
        "Где вы находитесь?",
        "Расскажите про врача-имплантолога",
    ],
)
def test_unrelated_message_clears_pending_price_clarify(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    user_message: str,
) -> None:
    sid = f"ui-flow-clear-{uuid.uuid4().hex[:8]}"
    options = ["classic", "all_on_4"]
    clarify_backend = _CountingBackend(
        _clarify_service_envelope("Уточните вариант.", options=options)
    )
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=clarify_backend,
        user_message="Сколько стоит?",
        envelope_json=clarify_backend.output,
    )
    assert read_pending_price_clarify(mem_get(sid)) is not None
    answer_backend = _CountingBackend(answer_envelope("Ответ.", commercial_intent="none"))
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=answer_backend,
        user_message=user_message,
        envelope_json=answer_backend.output,
        reset_session=False,
    )
    assert read_pending_price_clarify(mem_get(sid)) is None


def test_implantation_topic_hint_negative_cases(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    cases = (
        (
            "Имплант уже установлен, нужна коронка",
            None,
            answer_envelope(
                "Про коронку.",
                commercial_intent="none",
                service_id=None,
                extent=None,
                service_reference_status="none",
            ),
        ),
        (
            "Сколько стоит коронка на имплант?",
            None,
            answer_envelope(
                "Про коронку на имплант.",
                commercial_intent="price",
                service_id=None,
                extent=None,
                service_reference_status="none",
            ),
        ),
        (
            "Кто у вас устанавливает импланты?",
            None,
            answer_envelope(
                "Про врачей.",
                commercial_intent="none",
                service_id=None,
                extent=None,
                service_reference_status="none",
            ),
        ),
        (
            "Сколько стоит All-on-6?",
            "all_on_6",
            answer_envelope(
                "All-on-6.",
                commercial_intent="price",
                service_id="all_on_6",
                extent="full_arch",
                service_reference_status="none",
            ),
        ),
        (
            "Сколько стоит All-on-4?",
            "all_on_4",
            answer_envelope(
                "All-on-4.",
                commercial_intent="price",
                service_id="all_on_4",
                extent="full_arch",
                service_reference_status="none",
            ),
        ),
        (
            "Сколько стоит имплантация Straumann?",
            "classic",
            answer_envelope(
                "Straumann.",
                commercial_intent="price",
                service_id="classic",
                extent="one_tooth",
                service_reference_status="none",
            ),
        ),
        (
            "Расскажите про имплантацию",
            None,
            answer_envelope(
                "Общая информация.",
                commercial_intent="none",
                service_id=None,
                extent=None,
                service_reference_status="none",
            ),
        ),
    )
    for message, expected_service, envelope_json in cases:
        sid = f"ui-flow-neg-topic-{uuid.uuid4().hex[:8]}"
        backend = _CountingBackend(envelope_json)
        payload = _run_ask(
            monkeypatch,
            sid=sid,
            backend=backend,
            user_message=message,
            envelope_json=backend.output,
        )
        meta = payload.get("meta") or {}
        quick_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
        assert build_ui_scope_ref(topic="implantation", extent="one_tooth") not in quick_refs
        assert build_ui_scope_ref(topic="implantation", extent="full_arch") not in quick_refs
        if expected_service is None:
            assert meta.get("service_topic") != "implantation"
            assert meta.get("matched_service_id") in {None, ""}
        else:
            assert meta.get("matched_service_id") == expected_service


def test_ask_and_stream_payload_parity_for_general_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    envelope = _general_implantation_envelope("Стоимость зависит от объёма.")
    ask_backend = _CountingBackend(envelope)
    stream_backend = _CountingBackend(envelope)
    sid_ask = f"ui-flow-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"ui-flow-parity-stream-{uuid.uuid4().hex[:8]}"
    ask_payload = _run_ask(
        monkeypatch,
        sid=sid_ask,
        backend=ask_backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=envelope,
    )
    stream_payload = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=stream_backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=envelope,
    )
    assert _user_visible_result_snapshot(sid_ask, ask_payload) == _user_visible_result_snapshot(
        sid_stream,
        stream_payload,
    )


def test_active_runtime_defaults_to_plus_model() -> None:
    assert config.SALES_ONE_PLUS_MODEL == "qwen3.7-plus-2026-05-26"
    assert sales_one_plus_model() == config.SALES_ONE_PLUS_MODEL
    assert ONE_CALL_MODEL_SNAPSHOT == config.SALES_ONE_PLUS_MODEL


def test_active_runtime_model_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    import importlib

    import config as config_module
    import core.sales_one_plus_live_backend as backend_module

    monkeypatch.setenv("SALES_ONE_PLUS_MODEL", "qwen3.7-plus-custom-test")
    importlib.reload(config_module)
    importlib.reload(backend_module)
    assert config_module.SALES_ONE_PLUS_MODEL == "qwen3.7-plus-custom-test"
    assert backend_module.sales_one_plus_model() == "qwen3.7-plus-custom-test"
    monkeypatch.delenv("SALES_ONE_PLUS_MODEL", raising=False)
    importlib.reload(config_module)
    importlib.reload(backend_module)


def test_ui_scope_click_records_visible_label_in_history(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"ui-flow-scope-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ref = build_ui_scope_ref(topic="implantation", extent="one_tooth")
    _seed_followups(sid, TargetRuntimeFollowupItem(ref=ref, label="Один зуб"))
    backend = _CountingBackend(answer_envelope("Цена одного зуба.", commercial_intent="price"))
    _run_ask(
        monkeypatch,
        sid=sid,
        backend=backend,
        envelope_json=backend.output,
        ref=ref,
        reset_session=False,
    )
    assert _user_history(sid) == ["Один зуб"]
    assert "продолжить" not in _user_history(sid)
