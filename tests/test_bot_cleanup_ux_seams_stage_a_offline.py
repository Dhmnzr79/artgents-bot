"""Offline E2E for BOT-CLEANUP-UX-SEAMS-STAGE-A-1."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import config
import pytest

import app as app_module
from contracts.ui_scope_action import build_ui_scope_ref
from contracts.ui_stage_action import build_ui_stage_ref
from core.target_runtime_followup_nav import TargetRuntimeFollowupItem
from session import bind_session_client, mem_get, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
UI_STAGE_REF = build_ui_stage_ref(topic="prosthetics", stage="implant_placed")
UI_STAGE_LABEL = "Имплант установлен"
MANDATORY_EXCLUSION_FULL_ARCH = "КТ и костная пластика по показаниям — отдельно"
MANDATORY_EXCLUSION_ONE_TOOTH = "КТ при необходимости и временная коронка — отдельно"
_PARITY_META_KEYS = (
    "service_route",
    "matched_service_id",
    "service_topic",
    "presentation_channel",
    "followup_count",
)


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
def isolated_demo_sqlite(tmp_path: Path):
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    def _sqlite_path(client_id: str | None) -> str:
        pack = (client_id or "demo").strip() or "demo"
        return str((sessions_dir / f"{pack}.db").resolve())

    _clear_session_connection_cache()
    import unittest.mock as um

    p1 = um.patch("core.client_runtime.sqlite_path_for_client", _sqlite_path)
    p2 = um.patch("session.sqlite_path_for_client", _sqlite_path)
    p1.start()
    p2.start()
    bind_session_client("demo")
    try:
        yield
    finally:
        p2.stop()
        p1.stop()
        _clear_session_connection_cache()


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0

    def generate(self, invocation, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        if isinstance(self.output, Exception):
            raise self.output
        on_raw_delta(str(self.output))
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _general_implantation_envelope(prose: str) -> str:
    return answer_envelope(
        prose,
        commercial_intent="price",
        service_id=None,
        extent=None,
        scenario="cost",
        service_reference_status="none",
    )


def _scoped_continuation_envelope(prose: str) -> str:
    return answer_envelope(
        prose,
        commercial_intent="none",
        service_id=None,
        extent=None,
        scenario="none",
        service_reference_status="none",
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
    match = re.search(r"event: ui\ndata: (.+?)\n\n", text)
    assert match is not None
    body = json.loads(match.group(1))
    assert isinstance(body, dict)
    return body


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


def _user_history(sid: str) -> list[str]:
    return [
        str(item.get("content") or "")
        for item in mem_get(sid).get("hist") or []
        if item.get("role") == "user"
    ]


def _scope_ref_from_payload(payload: dict, *, extent_token: str) -> tuple[str, str]:
    for item in payload.get("quick_replies") or []:
        ref = str(item.get("ref") or "")
        if extent_token in ref:
            return ref, str(item.get("label") or "")
    raise AssertionError(f"scope ref with {extent_token} not in quick_replies")


def _visible_snapshot(payload: dict) -> dict:
    session = payload.get("session") or {}
    return {
        "answer": payload.get("answer"),
        "quick_replies": payload.get("quick_replies"),
        "offer": payload.get("offer"),
        "cta": payload.get("cta"),
        "video": payload.get("video"),
        "meta": {
            k: (payload.get("meta") or {}).get(k)
            for k in (
                "matched_service_id",
                "service_topic",
                "service_route",
                "terminal_mode",
                "answer_path",
                "intent",
                "presentation_channel",
                "followup_count",
            )
        },
        "history_user": _user_history(str((payload.get("meta") or {}).get("sid") or "")),
    }


def _session_snapshot(sid: str) -> dict:
    state = mem_get(sid)
    return {
        "history_user": _user_history(sid),
        "patient_facts": state.get("patient_facts") or {},
        "last_displayed_offer_ids": state.get("last_displayed_offer_ids"),
        "last_selected_offer_id": state.get("last_selected_offer_id"),
        "last_service_id": state.get("last_service_id"),
        "last_primary_aspect": state.get("last_primary_aspect"),
    }


def _parity_snapshot(payload: dict, sid: str) -> dict:
    meta = payload.get("meta") or {}
    return {
        "answer": payload.get("answer"),
        "quick_replies": payload.get("quick_replies"),
        "offer": payload.get("offer"),
        "cta": payload.get("cta"),
        "video": payload.get("video"),
        "meta": {key: meta.get(key) for key in _PARITY_META_KEYS},
        "session": _session_snapshot(sid),
    }


def _pick_scope_ref(payload: dict, extent_token: str) -> tuple[str, str]:
    return _scope_ref_from_payload(payload, extent_token=extent_token)


def _seed_followups(sid: str, *items: TargetRuntimeFollowupItem) -> None:
    from session import _lock, _persist_unlocked

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


def test_broad_implantation_t1_shows_from_prices_and_conditions(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-broad-{uuid.uuid4().hex[:8]}"
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(
            _general_implantation_envelope("Стоимость зависит от объёма работы.")
        ),
        user_message="Сколько стоит имплантация?",
        envelope_json=_general_implantation_envelope("Стоимость зависит от объёма работы."),
    )
    answer = str(payload.get("answer") or "")
    assert "от" in answer
    assert "76" in _norm_digits(answer)
    assert "318" in _norm_digits(answer)
    assert MANDATORY_EXCLUSION_FULL_ARCH in answer or MANDATORY_EXCLUSION_ONE_TOOTH in answer
    scope_refs = {str(item.get("ref") or "") for item in payload.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") in scope_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") in scope_refs


def test_broad_to_full_arch_scope_shows_code_owned_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-fa-{uuid.uuid4().hex[:8]}"
    t1_backend = _CountingBackend(
        _general_implantation_envelope("Стоимость зависит от объёма работы.")
    )
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t1_backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_backend.output,
    )
    ref, label = _pick_scope_ref(t1, "full_arch")
    assert label
    t2_backend = _CountingBackend(
        _scoped_continuation_envelope(
            "Чтобы назвать точную сумму, нужна консультация. Запишем вас на приём?"
        )
    )
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t2_backend,
        user_message="",
        envelope_json=t2_backend.output,
        ref=ref,
        reset_session=False,
    )
    answer = _norm_digits(str(t2.get("answer") or ""))
    answer_raw = str(t2.get("answer") or "")
    assert "от" in answer_raw
    assert "318000" in answer
    assert "398000" in answer
    assert MANDATORY_EXCLUSION_FULL_ARCH in answer_raw
    assert answer_raw.count(MANDATORY_EXCLUSION_FULL_ARCH) == 1
    assert label in _user_history(sid)
    assert "продолжить" not in _user_history(sid)
    assert "бесплатн" not in answer_raw.casefold() and "консультации врач" not in answer_raw.casefold()
    assert "запишем вас на приём" not in answer_raw.casefold()
    quick_refs = {str(q.get("ref") or "") for q in t2.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="one_tooth") not in quick_refs
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") not in quick_refs
    assert (t2.get("meta") or {}).get("matched_service_id") is None


def test_broad_to_one_tooth_scope_shows_scoped_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-ot-{uuid.uuid4().hex[:8]}"
    t1_backend = _CountingBackend(
        _general_implantation_envelope("Стоимость зависит от объёма работы.")
    )
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t1_backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_backend.output,
    )
    ref, label = _pick_scope_ref(t1, "one_tooth")
    t2_backend = _CountingBackend(
        _scoped_continuation_envelope("На консультации врач предложит вариант.")
    )
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t2_backend,
        user_message="",
        envelope_json=t2_backend.output,
        ref=ref,
        reset_session=False,
    )
    answer = _norm_digits(str(t2.get("answer") or ""))
    answer_raw = str(t2.get("answer") or "")
    assert "от" in answer_raw
    assert "76200" in answer
    assert MANDATORY_EXCLUSION_ONE_TOOTH in answer_raw
    assert label in _user_history(sid)
    assert "продолжить" not in _user_history(sid)
    quick_refs = {str(q.get("ref") or "") for q in t2.get("quick_replies") or []}
    assert build_ui_scope_ref(topic="implantation", extent="full_arch") not in quick_refs


def test_scoped_full_arch_strips_hostile_model_amount(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-hostile-{uuid.uuid4().hex[:8]}"
    t1_backend = _CountingBackend(_general_implantation_envelope("Обзор."))
    t1 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t1_backend,
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_backend.output,
    )
    ref, _ = _pick_scope_ref(t1, "full_arch")
    t2_backend = _CountingBackend(
        _scoped_continuation_envelope("All-on-4 стоит 999 999 ₽ за челюсть. Нужна консультация.")
    )
    t2 = _run_ask(
        monkeypatch,
        sid=sid,
        backend=t2_backend,
        user_message="",
        envelope_json=t2_backend.output,
        ref=ref,
        reset_session=False,
    )
    answer = _norm_digits(str(t2.get("answer") or ""))
    assert "999999" not in answer
    assert "318000" in answer


def test_scope_click_ask_stream_parity(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid_ask = f"stage-a-parity-ask-{uuid.uuid4().hex[:8]}"
    sid_stream = f"stage-a-parity-stream-{uuid.uuid4().hex[:8]}"
    t1_env = _general_implantation_envelope("Стоимость зависит от объёма.")
    t2_env = _scoped_continuation_envelope("Консультация без цен в модели.")

    t1_ask = _run_ask(
        monkeypatch,
        sid=sid_ask,
        backend=_CountingBackend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref_ask, label_ask = _pick_scope_ref(t1_ask, "full_arch")

    t1_stream = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=_CountingBackend(t1_env),
        user_message="Сколько стоит имплантация?",
        envelope_json=t1_env,
    )
    ref_stream, label_stream = _pick_scope_ref(t1_stream, "full_arch")
    assert ref_ask == ref_stream

    t2_ask = _run_ask(
        monkeypatch,
        sid=sid_ask,
        backend=_CountingBackend(t2_env),
        user_message="",
        envelope_json=t2_env,
        ref=ref_ask,
        reset_session=False,
    )
    t2_stream = _run_stream(
        monkeypatch,
        sid=sid_stream,
        backend=_CountingBackend(t2_env),
        user_message="",
        envelope_json=t2_env,
        ref=ref_stream,
        reset_session=False,
    )
    snap_ask = _parity_snapshot({**t2_ask, "meta": {**(t2_ask.get("meta") or {}), "sid": sid_ask}}, sid_ask)
    snap_stream = _parity_snapshot(
        {**t2_stream, "meta": {**(t2_stream.get("meta") or {}), "sid": sid_stream}},
        sid_stream,
    )
    assert snap_ask["answer"] == snap_stream["answer"]
    assert snap_ask["quick_replies"] == snap_stream["quick_replies"]
    assert snap_ask["offer"] == snap_stream["offer"]
    assert snap_ask["cta"] == snap_stream["cta"]
    assert snap_ask["video"] == snap_stream["video"]
    assert snap_ask["meta"] == snap_stream["meta"]
    assert snap_ask["session"]["history_user"] == snap_stream["session"]["history_user"]
    assert snap_ask["session"]["patient_facts"] == snap_stream["session"]["patient_facts"]
    assert (
        snap_ask["session"]["last_displayed_offer_ids"]
        == snap_stream["session"]["last_displayed_offer_ids"]
    )
    assert (
        snap_ask["session"]["last_selected_offer_id"]
        == snap_stream["session"]["last_selected_offer_id"]
    )
    assert snap_ask["session"]["last_service_id"] == snap_stream["session"]["last_service_id"]
    assert (
        snap_ask["session"]["last_primary_aspect"]
        == snap_stream["session"]["last_primary_aspect"]
    )
    assert label_ask in snap_ask["session"]["history_user"]
    assert label_stream in snap_stream["session"]["history_user"]


def test_unshown_scope_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-bad-ref-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    ref = build_ui_scope_ref(topic="implantation", extent="full_arch")
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(_general_implantation_envelope("x")),
        user_message="",
        envelope_json=_general_implantation_envelope("x"),
        ref=ref,
    )
    assert (payload.get("meta") or {}).get("service_route") == "sales_fast_followup_unknown"


def test_stage_click_records_visible_label_in_history(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-stage-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    _seed_followups(
        sid,
        TargetRuntimeFollowupItem(ref=UI_STAGE_REF, label=UI_STAGE_LABEL),
    )
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(
            _scoped_continuation_envelope("На консультации подберём вариант протезирования.")
        ),
        user_message="",
        envelope_json=_scoped_continuation_envelope("На консультации подберём вариант протезирования."),
        ref=UI_STAGE_REF,
        reset_session=False,
    )
    assert UI_STAGE_LABEL in _user_history(sid)
    assert "продолжить" not in _user_history(sid)
    facts = mem_get(sid).get("patient_facts") or {}
    assert facts.get("stage") == "implant_placed"
    assert facts.get("topic") == "prosthetics"
    assert (payload.get("meta") or {}).get("service_route") != "sales_fast_followup_unknown"


def test_unshown_stage_ref_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = f"stage-a-bad-stage-{uuid.uuid4().hex[:8]}"
    mem_reset(sid)
    payload = _run_ask(
        monkeypatch,
        sid=sid,
        backend=_CountingBackend(_general_implantation_envelope("x")),
        user_message="",
        envelope_json=_general_implantation_envelope("x"),
        ref=UI_STAGE_REF,
    )
    assert (payload.get("meta") or {}).get("service_route") == "sales_fast_followup_unknown"


@pytest.fixture
def demo_bundle():
    from core.response_schema_loader import load_response_schema_bundle

    return load_response_schema_bundle(_REPO / "clients" / "demo" / "target_response")


def _active_offers_for_service(bundle, service_id: str):
    return tuple(
        offer
        for offer in bundle.offers
        if offer.service_id == service_id and offer.active
    )


def test_service_level_price_mode_regression(demo_bundle) -> None:
    from contracts.response_schema import TargetFromPrice, TargetNoPublicPrice, TargetRangePrice
    from core.sales_fast_authoritative_commerce import (
        build_service_level_overview_line,
        format_service_level_amount_text,
    )

    classic = _active_offers_for_service(demo_bundle, "classic")
    all_on_4 = _active_offers_for_service(demo_bundle, "all_on_4")

    assert format_service_level_amount_text(classic).startswith("от ")
    assert format_service_level_amount_text(all_on_4).startswith("от ")

    singleton = classic[0].model_copy(deep=True)
    assert format_service_level_amount_text((singleton,)).startswith("76")
    assert "от" not in format_service_level_amount_text((singleton,))

    same_fixed = (
        classic[0].model_copy(deep=True),
        classic[0].model_copy(update={"offer_id": "classic.same"}, deep=True),
    )
    same_fixed_text = format_service_level_amount_text(same_fixed)
    assert same_fixed_text.startswith("76")
    assert "от" not in same_fixed_text

    from_offer = classic[0].model_copy(
        update={
            "offer_id": "classic.from",
            "price": TargetFromPrice(
                mode="from",
                min_amount=70000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
        },
        deep=True,
    )
    assert format_service_level_amount_text((from_offer,)).startswith("от ")

    range_offer = classic[0].model_copy(
        update={
            "offer_id": "classic.range",
            "price": TargetRangePrice(
                mode="range",
                min_amount=80000,
                max_amount=110000,
                currency="RUB",
                billing_unit="tooth_package",
            ),
        },
        deep=True,
    )
    range_text = format_service_level_amount_text((range_offer,))
    assert "80" in range_text and "110" in range_text

    no_public = classic[0].model_copy(
        update={
            "offer_id": "classic.npp",
            "price": TargetNoPublicPrice(
                mode="no_public_price",
                approved_text="По запросу",
            ),
        },
        deep=True,
    )
    assert format_service_level_amount_text((no_public,)) == "По запросу"


def test_service_overview_shared_mandatory_condition_once(demo_bundle) -> None:
    from core.sales_fast_authoritative_commerce import (
        assemble_service_level_overview_block,
        build_service_level_overview_line,
    )

    line4 = build_service_level_overview_line(
        service_name="Имплантация All-on-4",
        offers=_active_offers_for_service(demo_bundle, "all_on_4"),
    )
    line6 = build_service_level_overview_line(
        service_name="Имплантация All-on-6",
        offers=_active_offers_for_service(demo_bundle, "all_on_6"),
    )
    assert line4 is not None and line6 is not None
    block = assemble_service_level_overview_block((line4, line6))
    assert MANDATORY_EXCLUSION_FULL_ARCH in block
    assert block.count(MANDATORY_EXCLUSION_FULL_ARCH) == 1
    assert "от" in block


def test_service_overview_single_mandatory_condition_once(demo_bundle) -> None:
    from core.sales_fast_authoritative_commerce import (
        assemble_service_level_overview_block,
        build_service_level_overview_line,
    )

    line = build_service_level_overview_line(
        service_name="Классическая имплантация",
        offers=_active_offers_for_service(demo_bundle, "classic"),
    )
    assert line is not None
    condition = str(line.condition_text or "").strip()
    assert condition
    block = assemble_service_level_overview_block((line,))
    assert condition in block
    assert block.count(condition) == 1
    assert ";" not in block.split("\n")[0]
