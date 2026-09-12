"""Offline tests for BOT-CLEANUP-DIALOGUE-PRICE-SCOPE-1."""

from __future__ import annotations

import json
from pathlib import Path

import config
import pytest

import app as app_module
from contracts.ui_service_action import build_ui_service_ref
from core.sales_fast_authoritative_commerce import PAYMENT_STAGES_UNAVAILABLE_TEXT
from session import bind_session_client, mem_add_user, mem_reset, session_client_scope
from tests.session_binding_test_support import read_target_runtime_session_for
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]
_CONTEXT_COMPARE_ARTIFACT = (
    _REPO
    / "evals/v5/artifacts/bot_context_compare_live_1/bot_context_compare_live_1_2026-09-06-01"
)

_CONTEXT_COMPARE_ARTIFACT_AVAILABLE = _CONTEXT_COMPARE_ARTIFACT.is_dir()
_SKIP_CONTEXT_COMPARE_ARTIFACT = pytest.mark.skipif(
    not _CONTEXT_COMPARE_ARTIFACT_AVAILABLE,
    reason="requires local context-compare LIVE artifact tree (not committed to git)",
)
_REPO_DEMO_DB = _REPO / "data" / "demo" / "bot.db"


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
    yield {"db_path": sessions_dir / "demo.db"}
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


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
    ref: str | None = None,
) -> dict:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    with session_client_scope("demo"):
        if reset_session:
            mem_reset(sid, client_id="demo")
        if ref:
            client = flask_app.test_client()
            response = client.post(
                "/ask",
                json={"q": user_message, "sid": sid, "client_id": "demo", "ref": ref},
            )
            payload = response.get_json()
            assert isinstance(payload, dict)
            payload["_outcome_model_route"] = "ref_click"
            return payload
        if user_message.strip():
            mem_add_user(sid, user_message)
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": user_message, "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            from core.sales_fast_widget_runtime import run_sales_fast_widget_turn

            request.ctx = {"turn_t0_monotonic": 0.0}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message=user_message,
                backend=backend,
            )
        payload = dict(outcome.widget.payload or {})
        payload["_outcome_model_route"] = outcome.model_route
        return payload


def _norm_digits(text: str) -> str:
    return text.replace("\u00a0", "").replace(" ", "")


def _load_context_compare_envelope(turn_id: str, *, config_id: str = "plus_full") -> str:
    raw_turn_path = _CONTEXT_COMPARE_ARTIFACT / "raw_turns" / f"{config_id}__{turn_id}.json"
    raw_turn = json.loads(raw_turn_path.read_text(encoding="utf-8"))
    attempt_index = int(raw_turn["turn"]["provider_attempt"]["attempt_index"])
    provider_raw = json.loads(
        (
            _CONTEXT_COMPARE_ARTIFACT
            / "provider_raw"
            / config_id
            / f"{turn_id}_attempt_{attempt_index}.json"
        ).read_text(encoding="utf-8")
    )
    return str(provider_raw["provider_snapshot"]["choices"][0]["message"]["content"])


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


def _session_fields(sid: str) -> dict[str, object]:
    session = read_target_runtime_session_for(sid)
    return {
        "last_service_id": session.last_service_id,
        "last_displayed_offer_ids": tuple(session.last_displayed_offer_ids),
        "last_selected_offer_id": session.last_selected_offer_id,
        "service_focus_set_at_turn": session.service_focus_set_at_turn,
    }


def _assert_no_removable_denture_prices(payload: dict) -> None:
    answer = _norm_digits(str(payload.get("answer") or ""))
    offer_ids = _offer_ids(payload)
    assert "removable_dentures" not in offer_ids
    assert "45000" not in answer
    assert "65000" not in answer
    assert (payload.get("meta") or {}).get("matched_service_id") != "removable_dentures"


def _assert_dialogue_price_clarify(payload: dict) -> None:
    answer = str(payload.get("answer") or "")
    meta = payload.get("meta") or {}
    assert meta.get("terminal_mode") == "clarify"
    assert meta.get("service_route") == "sales_fast_dialogue_price_clarify"
    assert payload.get("_outcome_model_route") == "clarify"
    assert "+7" not in answer
    assert "позвоните" not in answer.lower()
    assert "администратор" not in answer.lower()
    assert "уточните" in answer.lower() or "интересует" in answer.lower()


def _clarify_envelope(text: str, **overrides: object) -> str:
    return answer_envelope(
        text,
        route="CLARIFY",
        commercial_intent="none",
        promotion_scope="none",
        clarify_axis="service",
        clarify_service_options=["all_on_4", "all_on_6"],
        service_reference_status="none",
        requested_service_id=None,
        **overrides,
    )


def _run_dia_02_chain(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    config_id: str,
) -> tuple[list[dict[str, object]], dict]:
    sid = f"dia-02-price-scope-{config_id}"
    turns = [
        ("DIA-02-T1", "У меня нет всех зубов сверху, что можно сделать?"),
        ("DIA-02-T2", "Расскажите про варианты"),
        ("DIA-02-T3", "А второй?"),
        ("DIA-02-T4", "Сколько стоит?"),
    ]
    session_trace: list[dict[str, object]] = []
    final_payload: dict | None = None
    for turn_id, user_message in turns:
        payload = _run_turn(
            monkeypatch,
            flask_app,
            sid=sid,
            user_message=user_message,
            envelope_json=_load_context_compare_envelope(turn_id, config_id=config_id),
            reset_session=turn_id == "DIA-02-T1",
        )
        session_trace.append({"turn_id": turn_id, **_session_fields(sid)})
        final_payload = payload
    assert final_payload is not None
    return session_trace, final_payload


@pytest.fixture
def flask_app():
    return app_module.app


@_SKIP_CONTEXT_COMPARE_ARTIFACT
def test_dia_02_plus_full_chain_t4_dialogue_price_clarify_not_admin(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    session_trace, final_payload = _run_dia_02_chain(
        monkeypatch, flask_app, config_id="plus_full"
    )
    _assert_no_removable_denture_prices(final_payload)
    _assert_dialogue_price_clarify(final_payload)


@_SKIP_CONTEXT_COMPARE_ARTIFACT
def test_dia_02_plus_curated_chain_t4_dialogue_price_clarify_not_admin(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    session_trace, final_payload = _run_dia_02_chain(
        monkeypatch, flask_app, config_id="plus_curated"
    )
    _assert_no_removable_denture_prices(final_payload)
    _assert_dialogue_price_clarify(final_payload)


def test_all_on_4_info_followup_then_price_with_envelope_service_shows_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-a4-info-price-with-service"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про All-on-4.",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление на четырёх имплантах.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А сколько длится?",
        envelope_json=answer_envelope(
            "Лечение занимает несколько месяцев.",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id="all_on_4",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids and all(offer_id.startswith("all_on_4.") for offer_id in offer_ids)


def test_all_on_4_info_followup_then_price_without_service_shows_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-a4-info-price-without-service"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про All-on-4.",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление на четырёх имплантах.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А сколько длится?",
        envelope_json=answer_envelope(
            "Лечение занимает несколько месяцев.",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids and all(offer_id.startswith("all_on_4.") for offer_id in offer_ids)
    assert (payload.get("meta") or {}).get("matched_service_id") == "all_on_4"


def test_single_service_all_on_4_price_followup(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-price-single-a4"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Вы делаете All-on-4?",
        envelope_json=answer_envelope(
            "Да, делаем All-on-4.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    session_after_question = _session_fields(sid)
    assert session_after_question["last_service_id"] == "all_on_4"

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id=None,
            extent="full_arch",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids and all(offer_id.startswith("all_on_4.") for offer_id in offer_ids)
    assert (payload.get("meta") or {}).get("matched_service_id") == "all_on_4"


def test_explicit_service_switch_to_all_on_6_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-price-switch-a6"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про съёмный протез.",
        envelope_json=answer_envelope(
            "Съёмный протез — доступный вариант.",
            service_id="removable_dentures",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="removable_dentures",
        ),
    )
    assert _session_fields(sid)["last_service_id"] == "removable_dentures"

    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А если All-on-6?",
        envelope_json=answer_envelope(
            "All-on-6 — несъёмное восстановление на шести имплантах.",
            service_id="all_on_6",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_6",
        ),
        reset_session=False,
    )
    assert _session_fields(sid)["last_service_id"] == "all_on_6"

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-6.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids and all(offer_id.startswith("all_on_6.") for offer_id in offer_ids)
    _assert_no_removable_denture_prices(payload)


def test_ambiguous_implant_group_price_does_not_use_stale_removable(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-price-ambiguous-implant"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="У меня нет всех зубов сверху, что можно сделать?",
        envelope_json=answer_envelope(
            "Есть съёмный протез и All-on-4/All-on-6.",
            service_id="removable_dentures",
            extent="full_arch",
            jaw="upper",
            service_reference_status="resolved",
            requested_service_id="removable_dentures",
        ),
    )
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А второй?",
        envelope_json=answer_envelope(
            "Второй вариант — All-on-4 или All-on-6.",
            service_id=None,
            extent="full_arch",
            jaw="upper",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    session_after_t3 = _session_fields(sid)
    assert session_after_t3["last_service_id"] == "removable_dentures"
    assert session_after_t3["service_focus_set_at_turn"] == 1

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Цена зависит от протокола.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    _assert_no_removable_denture_prices(payload)
    _assert_dialogue_price_clarify(payload)
    offer_ids = _offer_ids(payload)
    assert not offer_ids


def test_brand_included_followup_keeps_selected_offer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-price-brand-included"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит восстановить один зуб на Implantium?",
        envelope_json=answer_envelope(
            "Implantium.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
    )
    session = read_target_runtime_session_for(sid)
    assert session.last_selected_offer_id == "classic.one_tooth.implantium"

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Что входит?",
        envelope_json=answer_envelope(
            "В пакет входит имплант и коронка.",
            commercial_intent="included",
            service_id="classic",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
        reset_session=False,
    )
    session = read_target_runtime_session_for(sid)
    assert session.last_selected_offer_id == "classic.one_tooth.implantium"
    assert (payload.get("meta") or {}).get("matched_service_id") == "classic"


@pytest.mark.parametrize(
    "user_message",
    [
        "Как платить по этапам?",
        "Сколько платить на каждом этапе?",
        "Какие суммы вносить сначала и потом?",
    ],
)
def test_payment_stages_followup_keeps_context(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
    user_message: str,
) -> None:
    sid = f"dia-price-payment-stages-{abs(hash(user_message)) % 10000}"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message=user_message,
        envelope_json=answer_envelope(
            "Этапы оплаты.",
            commercial_intent="payment_stages",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": []},
        ),
        reset_session=False,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    assert read_target_runtime_session_for(sid).last_service_id == "all_on_4"
    assert (payload.get("meta") or {}).get("matched_service_id") == "all_on_4"
    assert "190800" in answer or "127200" in answer


def test_payment_stages_unavailable_when_selected_offer_has_no_authored_stages(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-payment-stages-unavailable"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит съёмный протез на одну челюсть?",
        envelope_json=answer_envelope(
            "Съёмный протез на одну челюсть.",
            commercial_intent="price",
            service_id="removable_dentures",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="removable_dentures",
        ),
    )
    backend = _CountingBackend(
        answer_envelope(
            "Оплата делится на два этапа.",
            commercial_intent="payment_stages",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": []},
        )
    )
    _install_sales_fast(monkeypatch, backend)
    with session_client_scope("demo"):
        mem_add_user(sid, "Как оплачивается по этапам?")
        with flask_app.test_request_context(
            "/ask",
            method="POST",
            json={"q": "Как оплачивается по этапам?", "sid": sid, "client_id": "demo"},
        ):
            from flask import request

            from core.sales_fast_widget_runtime import run_sales_fast_widget_turn

            request.ctx = {"turn_t0_monotonic": 0.0}
            outcome = run_sales_fast_widget_turn(
                client_id="demo",
                sid=sid,
                user_message="Как оплачивается по этапам?",
                backend=backend,
            )
    payload = dict(outcome.widget.payload or {})
    answer = str(payload.get("answer") or "")
    norm = _norm_digits(answer)
    assert backend.call_count == 1
    assert PAYMENT_STAGES_UNAVAILABLE_TEXT in answer
    assert "Оплата делится на два этапа" not in answer
    assert "190800" not in norm
    assert "127200" not in norm
    assert "76200" not in norm
    assert "45200" not in norm
    assert read_target_runtime_session_for(sid).last_service_id == "removable_dentures"
    assert (payload.get("meta") or {}).get("matched_service_id") == "removable_dentures"


def test_payment_stages_not_from_direct_fact_ids_only(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-payment-stages-fact-only"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Как платить по этапам?",
        envelope_json=answer_envelope(
            "Оплата по этапам возможна.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["payment_stages"]},
        ),
        reset_session=False,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    assert "190800" not in answer
    assert "127200" not in answer


def test_payment_intent_does_not_materialize_stage_amounts(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-payment-intent-no-stages"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит All-on-4 на Implantium?",
        envelope_json=answer_envelope(
            "All-on-4 на Implantium.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Есть рассрочка?",
        envelope_json=answer_envelope(
            "Доступна рассрочка.",
            commercial_intent="payment",
            service_id=None,
            service_reference_status="none",
            references={"direct_fact_ids": ["installment_12"]},
        ),
        reset_session=False,
    )
    answer = _norm_digits(str(payload.get("answer") or ""))
    assert "190800" not in answer
    assert "127200" not in answer


def test_stale_service_focus_not_rejuvenated_on_related_followup(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    from core.routing_loader import THRESHOLDS
    from session import _lock, _persist_unlocked, mem_get

    sid = "dia-stale-focus-guard"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про All-on-4.",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    with session_client_scope("demo"):
        with _lock:
            st = mem_get(sid)
            st["session_turn_count"] = int(THRESHOLDS.follow_up.max_service_focus_turn_age) + 2
            _persist_unlocked(sid, st)

    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А сколько длится?",
        envelope_json=answer_envelope(
            "Лечение занимает несколько месяцев.",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    assert _session_fields(sid)["service_focus_set_at_turn"] == 1

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    _assert_dialogue_price_clarify(payload)


def test_topic_change_does_not_refresh_service_focus(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-topic-guard"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про All-on-4.",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Какой у вас адрес?",
        envelope_json=answer_envelope(
            "Клиника находится в центре города.",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    assert _session_fields(sid)["service_focus_set_at_turn"] == 1

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    _assert_dialogue_price_clarify(payload)


def test_all_on_4_jaw_upper_without_service_then_price_keeps_all_on_4(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-a4-jaw-upper-price"
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Расскажите про All-on-4.",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление на четырёх имплантах.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
    )
    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Это на верхнюю челюсть?",
        envelope_json=answer_envelope(
            "Да, All-on-4 можно на верхнюю челюсть.",
            service_id=None,
            extent="full_arch",
            jaw="upper",
            service_reference_status="none",
        ),
        reset_session=False,
    )
    session = _session_fields(sid)
    assert session["last_service_id"] == "all_on_4"
    assert session["service_focus_set_at_turn"] == 2

    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Стоимость All-on-4.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    offer_ids = _offer_ids(payload)
    assert offer_ids and all(offer_id.startswith("all_on_4.") for offer_id in offer_ids)
    assert (payload.get("meta") or {}).get("matched_service_id") == "all_on_4"


def test_clarify_service_options_show_all_on_buttons_and_ui_service_click(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-clarify-service-buttons"
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=_clarify_envelope(
            "Уточните, какой вариант вас интересует.",
        ),
    )
    answer = str(payload.get("answer") or "")
    assert "All-on-4" in answer and "All-on-6" in answer
    quick = list(payload.get("quick_replies") or [])
    assert len(quick) == 2
    refs = {str(item.get("ref") or "") for item in quick}
    assert build_ui_service_ref(service_id="all_on_4") in refs
    assert build_ui_service_ref(service_id="all_on_6") in refs

    followup_payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="",
        envelope_json=answer_envelope(
            "All-on-4 — несъёмное восстановление.",
            service_id="all_on_4",
            extent="full_arch",
            service_reference_status="resolved",
            requested_service_id="all_on_4",
        ),
        reset_session=False,
        ref=build_ui_service_ref(service_id="all_on_4"),
    )
    assert (followup_payload.get("meta") or {}).get("matched_service_id") == "all_on_4"


def test_multi_brand_ambiguous_price_clarifies_without_buttons_or_wrong_offer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    sid = "dia-brand-ambiguous-price"
    overview_payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит классический имплант за один зуб?",
        envelope_json=answer_envelope(
            "Классическая имплантация одного зуба.",
            commercial_intent="price",
            service_id="classic",
            extent="one_tooth",
            service_reference_status="resolved",
            requested_service_id="classic",
        ),
    )
    overview_ids = set(_offer_ids(overview_payload))
    assert "classic.one_tooth.implantium" in overview_ids
    assert "classic.one_tooth.impro" in overview_ids

    _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="А сколько длится?",
        envelope_json=answer_envelope(
            "Лечение занимает несколько месяцев.",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )

    clarify_payload = _run_turn(
        monkeypatch,
        flask_app,
        sid=sid,
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Цена зависит от системы имплантов.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
        reset_session=False,
    )
    _assert_dialogue_price_clarify(clarify_payload)
    assert clarify_payload.get("quick_replies") == []
    assert not _offer_ids(clarify_payload)
    answer = _norm_digits(str(clarify_payload.get("answer") or ""))
    assert "76200" not in answer
    assert "85200" not in answer
    assert "classic.one_tooth.implantium" not in str(clarify_payload.get("offer") or "")


def test_bare_price_without_displayed_offers_has_no_clarify_buttons(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    isolated_demo_sqlite,
) -> None:
    payload = _run_turn(
        monkeypatch,
        flask_app,
        sid="dia-brand-clarify-empty",
        user_message="Сколько стоит?",
        envelope_json=answer_envelope(
            "Цена зависит от протокола.",
            commercial_intent="price",
            service_id=None,
            service_reference_status="none",
        ),
    )
    _assert_dialogue_price_clarify(payload)
    assert payload.get("quick_replies") == []
