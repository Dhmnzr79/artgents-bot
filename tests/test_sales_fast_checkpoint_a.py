"""Checkpoint A — demo foundation offline tests (sales-fast public path)."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import config
import pytest

import app as app_module
from core.sales_fast_service_identity import resolve_catalog_service_identity
from core.sales_fast_widget_runtime import run_sales_fast_widget_turn
from core.service_availability_presentation import FAMILY_CONTEXT_DISCLAIMER
from core.target_client_data import load_target_client_data
from core.target_runtime_session import read_target_runtime_session
from session import bind_session_client, mem_reset
from tests.test_sales_one_plus_turn import answer_envelope

_REPO = Path(__file__).resolve().parents[1]


@pytest.fixture
def flask_app():
    return app_module.app


class _CountingBackend:
    def __init__(self, output: object) -> None:
        self.output = output
        self.call_count = 0
        self.invocation = None

    def generate(self, invocation, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        return self.output

    def generate_stream(self, invocation, on_raw_delta, /):
        self.call_count += 1
        self.invocation = invocation
        if isinstance(self.output, Exception):
            raise self.output
        on_raw_delta(str(self.output))
        return None


def _install_sales_fast(monkeypatch: pytest.MonkeyPatch, backend: _CountingBackend) -> None:
    monkeypatch.setattr(config, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(app_module, "SALES_ONE_PLUS_ON", True)
    monkeypatch.setattr(
        "orchestration.sales_fast_widget_turn._default_sales_fast_backend",
        lambda: backend,
    )


def _run_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    client_id: str,
    sid: str,
    user_message: str,
    envelope_json: str,
    on_delta: list[str] | None = None,
    reset_session: bool = True,
) -> tuple[dict, _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    if client_id != "demo":
        monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    bind_session_client(client_id)
    if reset_session:
        mem_reset(sid)
    captured: list[str] = []

    def _on_delta(text: str) -> None:
        captured.append(text)
        if on_delta is not None:
            on_delta.append(text)

    with flask_app.test_request_context(
        "/ask",
        method="POST",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    ):
        from flask import request

        request.ctx = {"turn_t0_monotonic": 0.0}
        outcome = run_sales_fast_widget_turn(
            client_id=client_id,
            sid=sid,
            user_message=user_message,
            backend=backend,
            on_delta=_on_delta if on_delta is not None else None,
        )
    payload = dict(outcome.widget.payload or {})
    payload["_outcome_model_route"] = outcome.model_route
    payload["_failure_kind"] = outcome.failure_kind
    payload["_widget_kind"] = outcome.widget.kind
    payload["_streamed_deltas"] = captured
    return payload, backend


def _parse_sse_events(resp) -> list[tuple[str, dict]]:
    buffer = ""
    events: list[tuple[str, dict]] = []
    current_event: str | None = None
    for chunk in resp.response:
        buffer += chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        while "\n" in buffer:
            line, buffer = buffer.split("\n", 1)
            line = line.rstrip("\r")
            if line.startswith("event: "):
                current_event = line[len("event: ") :].strip()
            elif line.startswith("data: "):
                raw = line[len("data: ") :]
                try:
                    data = json.loads(raw) if raw.strip() else {}
                except json.JSONDecodeError:
                    data = {}
                if current_event:
                    events.append((current_event, data))
                current_event = None
    return events


def _run_stream_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    *,
    client_id: str,
    sid: str,
    user_message: str,
    envelope_json: str,
    reset_session: bool = True,
) -> tuple[dict, list[tuple[str, dict]], _CountingBackend]:
    backend = _CountingBackend(envelope_json)
    _install_sales_fast(monkeypatch, backend)
    if client_id != "demo":
        monkeypatch.setattr(config, "ALLOWED_CLIENTS", frozenset({"demo", "nikadent"}))
    bind_session_client(client_id)
    if reset_session:
        mem_reset(sid)
    client = flask_app.test_client()
    resp = client.post(
        "/ask/stream",
        json={"q": user_message, "sid": sid, "client_id": client_id},
    )
    assert resp.status_code == 200
    events = _parse_sse_events(resp)
    ui_events = [data for name, data in events if name == "ui"]
    assert ui_events, f"expected ui event, got: {events}"
    return ui_events[-1], events, backend


def _patient_visible_text(events: list[tuple[str, dict]]) -> str:
    parts: list[str] = []
    for name, data in events:
        if name == "text_delta":
            parts.append(str(data.get("delta") or ""))
        elif name == "ui":
            parts.append(str(data.get("answer") or ""))
    return "".join(parts)


def _expected_demo_price_snippet(service_id: str) -> str:
    data = load_target_client_data("demo")
    for offer in data.bundle.offers:
        if offer.service_id != service_id:
            continue
        price = offer.price
        if price.mode == "fixed" and price.amount is not None:
            return str(int(price.amount))
        if price.mode == "from" and price.min_amount is not None:
            return str(int(price.min_amount))
    raise AssertionError(f"no_demo_price_offer_for:{service_id}")


@pytest.mark.parametrize(
    ("service_id", "user_message"),
    [
        ("tomography", "Сколько стоит КТ?"),
        ("professional_whitening", "Сколько стоит отбеливание?"),
        ("caries", "Сколько стоит лечение кариеса?"),
        ("pulpitis", "Сколько стоит лечение пульпита?"),
        ("teeth_treatment", "Сколько стоит лечение зубов?"),
        ("tooth_extraction", "Сколько стоит удаление зуба?"),
        ("veneers", "Сколько стоят виниры?"),
    ],
)
def test_checkpoint_a_demo_exact_service_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    service_id: str,
    user_message: str,
) -> None:
    expected_amount = _expected_demo_price_snippet(service_id)
    hostile = "999999"
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=f"cp-a-price-{service_id}",
        user_message=user_message,
        envelope_json=answer_envelope(
            f"Неправильная цена {hostile} ₽.",
            commercial_intent="price",
            service_id=service_id,
        ),
    )
    answer = payload["answer"]
    assert backend.call_count == 1
    assert hostile not in answer.replace(" ", "")
    assert expected_amount in answer.replace("\u00a0", "").replace(" ", "")
    assert payload["meta"]["service_route"] == "sales_fast_materialized"


def test_checkpoint_a_tomography_fixed_3000(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-kt-fixed",
        user_message="Сколько стоит компьютерная томография?",
        envelope_json=answer_envelope(
            "КТ стоит 1 ₽.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    assert backend.call_count == 1
    assert "3000" in payload["answer"].replace("\u00a0", "").replace(" ", "")


def test_checkpoint_a_whitening_from_price_and_expired_promo_hidden(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 16),
    )
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-whitening",
        user_message="Сколько стоит профессиональное отбеливание?",
        envelope_json=answer_envelope(
            "Отбеливание стоит 1 ₽.",
            commercial_intent="price",
            service_id="professional_whitening",
            scenario="cost",
        ),
    )
    answer = payload["answer"].lower()
    assert backend.call_count == 1
    assert "18000" in payload["answer"].replace("\u00a0", "").replace(" ", "")
    assert "15 августа" not in answer
    assert "15%" not in answer or "отбеливан" not in answer


def test_checkpoint_a_nikadent_tooth_extraction_exact_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="nikadent",
        sid="cp-a-nika-extract",
        user_message="Сколько стоит удаление зуба?",
        envelope_json=answer_envelope(
            "Удаление стоит 1 ₽.",
            commercial_intent="price",
            service_id="tooth_extraction",
        ),
    )
    assert backend.call_count == 1
    assert "5000" in payload["answer"].replace("\u00a0", "").replace(" ", "")


def test_checkpoint_a_nikadent_all_on_4_family_price_without_exact_card(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="nikadent",
        sid="cp-a-nika-allon4",
        user_message="Сколько стоит All-on-4?",
        envelope_json=answer_envelope(
            "All-on-4 стоит 1 ₽.",
            commercial_intent="price",
            service_id="all_on_4",
            extent="full_arch",
        ),
    )
    answer = payload["answer"]
    assert backend.call_count == 1
    assert FAMILY_CONTEXT_DISCLAIMER in answer
    assert "35" in answer and "000" in answer
    assert payload.get("offer") is None


def test_checkpoint_a_demo_no_public_price_bone_graft(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    data = load_target_client_data("demo")
    offer = next(item for item in data.bundle.offers if item.service_id == "bone_graft")
    assert offer.price.mode == "no_public_price"
    approved = str(getattr(offer.price, "approved_text", "") or "")
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-demo-bone",
        user_message="Сколько стоит костная пластика?",
        envelope_json=answer_envelope(
            "Костная пластика стоит 100 ₽.",
            commercial_intent="price",
            service_id="bone_graft",
        ),
    )
    assert backend.call_count == 1
    assert approved[:24] in payload["answer"]


def test_checkpoint_a_inactive_service_has_no_commerce(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-kno-braces",
        user_message="Сколько стоят брекеты?",
        envelope_json=answer_envelope(
            "Брекеты стоят 200000 ₽.",
            commercial_intent="price",
            service_id="braces",
        ),
    )
    assert backend.call_count == 1
    assert "200000" not in payload["answer"].replace(" ", "")
    assert payload.get("offer") is None


@pytest.mark.parametrize(
    ("user_message", "envelope_service", "patient_text", "needle", "forbidden"),
    [
        (
            "Какие гарантии на импланты Nobel?",
            None,
            "На импланты Nobel действует пожизненная гарантия производителя.",
            "пожизнен",
            ("₽", "скидк"),
        ),
        (
            "Больно ли лечить кариес?",
            "caries",
            "Лечение кариеса обычно проходит без боли.",
            "без боли",
            ("₽",),
        ),
        (
            "Больно ли ставить виниры?",
            "veneers",
            "Установка виниров обычно проходит спокойно — боли быть не должно.",
            "боли быть не должно",
            ("₽",),
        ),
        (
            "Какая приживаемость имплантов?",
            "classic",
            "По статистике клиники приживаемость имплантов — 99,8%.",
            "99,8",
            ("₽",),
        ),
    ],
)
def test_checkpoint_a_informational_content_without_price_surface(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    user_message: str,
    envelope_service: str | None,
    patient_text: str,
    needle: str,
    forbidden: tuple[str, ...],
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=f"cp-a-info-{hash(user_message) & 0xffff}",
        user_message=user_message,
        envelope_json=answer_envelope(
            patient_text,
            commercial_intent="none",
            service_id=envelope_service,
        ),
    )
    answer = payload["answer"].lower()
    assert backend.call_count == 1
    assert needle.lower() in answer
    for token in forbidden:
        assert token not in payload["answer"]
    assert payload.get("offer") is None
    assert payload["_widget_kind"] == "materialized"


def test_checkpoint_a_session_price_followup_uses_fresh_service(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "cp-a-session-followup"
    _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ нужна для планирования.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="А сколько?",
        envelope_json=answer_envelope(
            "Уточню стоимость.",
            commercial_intent="price",
            service_id=None,
        ),
        reset_session=False,
    )
    assert backend.call_count == 1
    assert "3000" in payload["answer"].replace("\u00a0", "").replace(" ", "")
    session = read_target_runtime_session(sid)
    assert session.last_service_id == "tomography"


def test_checkpoint_a_explicit_service_replaces_session(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "cp-a-session-replace"
    _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит отбеливание?",
        envelope_json=answer_envelope(
            "Отбеливание.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
        reset_session=False,
    )
    assert backend.call_count == 1
    assert "18000" in payload["answer"].replace("\u00a0", "").replace(" ", "")
    assert "3000" not in payload["answer"].replace("\u00a0", "").replace(" ", "")


def test_checkpoint_a_catalog_envelope_conflict_is_scope_clarify_not_admin(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-catalog-conflict",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ стоит 5000 ₽.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
    )
    answer = str(payload.get("answer") or "").lower()
    assert backend.call_count == 1
    assert payload["_widget_kind"] == "terminal"
    assert payload["_outcome_model_route"] == "clarify"
    assert payload["_failure_kind"] == "semantic_catalog_envelope_conflict_service_id"
    assert payload["_outcome_model_route"] != "model_admin"
    assert "5000" not in str(payload.get("answer") or "")
    assert "администратор" not in answer
    assert payload.get("offer") is None


def test_checkpoint_a_streamed_text_matches_final_authoritative_answer(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    streamed: list[str] = []
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-sse-final",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ стоит 999999 ₽.",
            commercial_intent="price",
            service_id="tomography",
        ),
        on_delta=streamed,
    )
    assert backend.call_count == 1
    assert streamed == [payload["answer"]]
    assert "999999" not in payload["answer"].replace(" ", "")
    assert "3000" in payload["answer"].replace("\u00a0", "").replace(" ", "")


def test_checkpoint_a_explicit_catalog_service_identity_from_message() -> None:
    data = load_target_client_data("demo")
    identity = resolve_catalog_service_identity(
        "Сколько стоит компьютерная томография?",
        data.bundle,
    )
    assert identity.catalog_ambiguous is False
    assert identity.explicit_service_id == "tomography"
    assert identity.explicit_service_term
    assert identity.session_service_id is None


def test_checkpoint_a_catalog_match_runs_once_per_public_stream_turn(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    import core.sales_fast_service_identity as identity_module

    calls = {"count": 0}
    original = identity_module.match_service_from_bundle

    def _spy(user_message: str, bundle: object) -> dict[str, object]:
        calls["count"] += 1
        return original(user_message, bundle)  # type: ignore[arg-type]

    monkeypatch.setattr(identity_module, "match_service_from_bundle", _spy)
    _ui, _events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-catalog-once-stream",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    assert backend.call_count == 1
    assert calls["count"] == 1


def test_checkpoint_a_stream_http_tomography_authoritative_price(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    hostile = "999999"
    ui, events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-http-kt",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            f"КТ стоит {hostile} ₽.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    assert backend.call_count == 1
    answer = str(ui.get("answer") or "")
    assert "3000" in answer.replace("\u00a0", "").replace(" ", "")
    assert hostile not in _patient_visible_text(events).replace(" ", "")
    assert ui.get("meta", {}).get("service_route") == "sales_fast_materialized"
    offer = ui.get("offer")
    assert isinstance(offer, dict)
    assert offer.get("mode") == "exact_offer"
    assert str(offer.get("offer_id") or "").startswith("tomography")
    assert any(name == "done" for name, _ in events)
    deltas = [data.get("delta") for name, data in events if name == "text_delta"]
    if deltas:
        assert deltas == [answer]


def test_checkpoint_a_stream_http_whitening_not_kt_and_expired_promo_hidden(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    monkeypatch.setattr(
        "core.target_runtime_client_context.runtime_today",
        lambda: date(2026, 8, 16),
    )
    hostile = "3000"
    ui, events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-http-whitening",
        user_message="Сколько стоит отбеливание?",
        envelope_json=answer_envelope(
            f"Отбеливание стоит {hostile} ₽.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
    )
    answer = str(ui.get("answer") or "")
    assert backend.call_count == 1
    assert "18000" in answer.replace("\u00a0", "").replace(" ", "")
    assert hostile not in answer.replace("\u00a0", "").replace(" ", "")
    assert "15 августа" not in answer.lower()
    assert hostile not in _patient_visible_text(events).replace(" ", "")


@pytest.mark.parametrize(
    ("service_id", "user_message"),
    [
        ("caries", "Сколько стоит лечение кариеса?"),
        ("pulpitis", "Сколько стоит лечение пульпита?"),
        ("teeth_treatment", "Сколько стоит лечение зубов?"),
        ("tooth_extraction", "Сколько стоит удаление зуба?"),
        ("veneers", "Сколько стоят виниры?"),
    ],
)
def test_checkpoint_a_stream_http_parametric_exact_prices(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
    service_id: str,
    user_message: str,
) -> None:
    expected_amount = _expected_demo_price_snippet(service_id)
    ui, events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=f"cp-a-http-{service_id}",
        user_message=user_message,
        envelope_json=answer_envelope(
            "Неправильная цена 999999 ₽.",
            commercial_intent="price",
            service_id=service_id,
        ),
    )
    answer = str(ui.get("answer") or "")
    assert backend.call_count == 1
    assert expected_amount in answer.replace("\u00a0", "").replace(" ", "")
    assert "999999" not in _patient_visible_text(events).replace(" ", "")
    assert ui.get("meta", {}).get("service_route") == "sales_fast_materialized"
    assert "лучше обсудить" not in answer.lower()
    offer = ui.get("offer")
    assert isinstance(offer, dict)
    assert offer.get("mode") == "exact_offer"
    assert str(offer.get("offer_id") or "").startswith(f"{service_id}")


def test_checkpoint_a_stream_http_session_followup_tomography(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    sid = "cp-a-http-session"
    _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            "КТ.",
            commercial_intent="price",
            service_id="tomography",
        ),
    )
    ui, events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid=sid,
        user_message="А сколько?",
        envelope_json=answer_envelope(
            "Уточню.",
            commercial_intent="price",
            service_id=None,
        ),
        reset_session=False,
    )
    answer = str(ui.get("answer") or "")
    assert backend.call_count == 1
    assert "3000" in answer.replace("\u00a0", "").replace(" ", "")
    assert "999999" not in _patient_visible_text(events).replace(" ", "")


def test_checkpoint_a_stream_http_catalog_conflict_is_scope_clarify(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    hostile = "5000"
    ui, events, backend = _run_stream_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-http-catalog-conflict",
        user_message="Сколько стоит КТ?",
        envelope_json=answer_envelope(
            f"КТ стоит {hostile} ₽.",
            commercial_intent="price",
            service_id="professional_whitening",
        ),
    )
    assert backend.call_count == 1
    answer = str(ui.get("answer") or "").lower()
    meta = ui.get("meta") or {}
    assert meta.get("answer_path") == "sales_fast"
    assert meta.get("service_route") == "sales_fast_scope_clarify"
    assert meta.get("ui_source_family") == "guided_fallback"
    assert meta.get("attribution_kind") == "plain"
    assert meta.get("terminal_mode") == "clarify"
    assert meta.get("semantic_conflict_code") == "semantic_catalog_envelope_conflict_service_id"
    assert hostile not in _patient_visible_text(events).replace(" ", "")
    assert "администратор" not in answer
    assert ui.get("offer") is None
    assert any(name == "done" for name, _ in events)
    deltas = [str(data.get("delta") or "") for name, data in events if name == "text_delta"]
    assert all(hostile not in delta.replace(" ", "") for delta in deltas)


def test_checkpoint_a_fullcontext_invocation_includes_authored_corpus(
    monkeypatch: pytest.MonkeyPatch,
    flask_app,
) -> None:
    corpus_needle = "импланты nobel"
    patient_text = "На импланты Nobel действует пожизненная гарантия производителя."
    payload, backend = _run_turn(
        monkeypatch,
        flask_app,
        client_id="demo",
        sid="cp-a-corpus-proof",
        user_message="Какие гарантии на импланты Nobel?",
        envelope_json=answer_envelope(
            patient_text,
            commercial_intent="none",
            service_id=None,
        ),
    )
    assert backend.call_count == 1
    assert backend.invocation is not None
    corpus = str(backend.invocation.model_corpus_text).lower()
    assert corpus_needle in corpus
    assert corpus_needle in payload["answer"].lower()
    assert payload.get("offer") is None
    assert payload["_widget_kind"] == "materialized"
