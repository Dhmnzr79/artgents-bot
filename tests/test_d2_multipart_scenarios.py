"""CP5-MP: assembled A05/A06/B14 multi-part through the common D2 route.

Fake raw → production parser → tenant snapshot → materializer/renderer →
D2DialogueStore. Provider/live/network forbidden. Decisions: D2-042, D2-072,
D2-080, T2; adjacent C02 mechanics without expanding into full C02.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import sqlite3
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import D2_PRICE_DEFERRAL_TEXT, SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 16, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="mp-multipart")
PAIN_LIVE = (
    "Понимаю этот страх — при имплантации работаем с анестезией, "
    "и обычно всё терпимее, чем кажется заранее."
)
WARRANTY_LIVE = (
    "Да, гарантия есть: на работу врача — год, на Nobel и Impro — пожизненно, "
    "на Implantium — пять лет. Условия фиксируем в договоре."
)
WARRANTY_ALSO = "Гарантия на работу врача и импланты фиксируется в договоре."
PAIN_VIDEO = "pain-doctor-explains"
PAIN_FOLLOW = "implantation__faq__pain.md#kakuyu-anesteziyu-ispolzuyut"


def _price_part(
    *,
    request_id: str,
    service_id: str,
    topic_id: str,
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": "price",
        "subject_id": None,
        "context": "general_information",
        "topic_id": topic_id,
        "service_id": service_id,
        "statement_mode": "question",
        "situation": None,
    }


def _content_part(
    *,
    request_id: str,
    content_ref: str,
    service_id: str | None,
    topic_id: str | None,
    text: str,
    section_refs: list[str] | None = None,
    fallback: str | None = "a:korotko",
) -> dict[str, object]:
    return {
        "request_id": request_id,
        "kind": "content",
        "subject_id": None,
        "context": "general_information",
        "topic_id": topic_id,
        "service_id": service_id,
        "statement_mode": "question",
        "situation": None,
        "content_text": text,
        "content_ref": content_ref,
        "content_realization": "model_prose",
        "content_section_refs": section_refs or ["a:korotko"],
        "content_fallback_section_ref": fallback,
    }


def _raw(*parts: dict[str, object], commercial_intent: str = "price") -> str:
    price_ids = [item["request_id"] for item in parts if item["kind"] == "price"]
    return json.dumps(
        production_envelope_template(
            commercial_intent=commercial_intent,
            promotion_scope="none",
            scenario="none",
            primary_price_request_id=price_ids[0] if price_ids else None,
            patient_text=None,
            request_understanding={"subjects": [], "requests": list(parts)},
        ),
        ensure_ascii=False,
    )


class RawFakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


@pytest.fixture(autouse=True)
def isolated_io(monkeypatch, tmp_path):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    monkeypatch.setenv("BOT_LOG_DIR", str(log_dir))
    os.environ["BOT_LOG_DIR"] = str(log_dir)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("network forbidden in CP5-MP")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        assert Path(database).resolve().is_relative_to(tmp_path.resolve()), "non-test DB forbidden"
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)


@contextmanager
def observed_common_route():
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, _arg):
        if event != "call":
            return
        module = frame.f_globals.get("__name__", "")
        calls.append((module, frame.f_code.co_name))
        assert not module.startswith((
            "core.sales_",
            "core.target_composer",
            "core.target_runtime_",
            "core.response_plan_composer_executor",
            "core.target_session_selection",
            "core.one_call_runtime",
            "core.one_call_presentation",
            "core.response_plan_session",
            "core.target_offer_projection",
            "core.target_service_selection",
            "core.response_strategy",
        )), f"legacy runtime/selector called: {module}"
        assert module != "core.target_marketing_selector", "legacy marketing selector called"
        if module == "session":
            assert frame.f_code.co_name == "current_session_client_id", (
                f"unexpected session use on ordinary D2 route: {frame.f_code.co_name}"
            )
            return

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _clients(tmp_path: Path) -> Path:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
    return clients


def _run(
    tmp_path: Path,
    raw: str,
    *,
    key: SessionKey = KEY,
    message: str = "Вопрос",
) -> tuple[object, object, object, list]:
    clients = _clients(tmp_path)
    provider = RawFakeProvider(raw)
    with observed_common_route() as calls:
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=clients,
                store=store,
                now=NOW,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls


def _money(text: str) -> str:
    return text.replace("\u00a0", " ").replace("\u202f", " ")


def test_a05_price_plus_pain_keeps_prices_and_info_without_pain_secondary(tmp_path: Path) -> None:
    # Direction overview (typed topic + subject) yields up to 3 prices; pain is
    # independent content. Price channel suppresses pain follow-up/video (D2-042).
    raw = json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [
                    {"subject_id": "s1", "relation": "self", "age_group": "unknown"}
                ],
                "requests": [
                    {
                        "request_id": "r1",
                        "kind": "price",
                        "subject_id": "s1",
                        "context": "general_information",
                        "topic_id": "implantation",
                        "service_id": None,
                        "statement_mode": "question",
                        "situation": None,
                    },
                    _content_part(
                        request_id="r2",
                        content_ref="implantation__faq__pain.md",
                        service_id="classic",
                        topic_id="implantation",
                        text=PAIN_LIVE,
                    ),
                ],
            },
        ),
        ensure_ascii=False,
    )
    outcome, saved, provider, calls = _run(
        tmp_path,
        raw,
        message="Сколько стоит имплантация и больно ли это?",
    )

    resolved = outcome.response.resolved
    ui = outcome.response.ui_projection
    assert [(part.request_id, part.status, part.kind) for part in resolved.d2_request_parts] == [
        ("r1", "answered", "price"),
        ("r2", "answered", "content"),
    ]
    assert resolved.d2_price_block is not None
    assert 1 <= len(resolved.d2_price_block.rows) <= 3
    assert PAIN_LIVE in outcome.response.rendered_text
    assert {row.offer_id for row in resolved.d2_price_block.rows}
    assert any(row.offer_id.startswith("classic.") for row in resolved.d2_price_block.rows)
    assert ui.video is None
    assert PAIN_FOLLOW not in {item.reply_id for item in ui.quick_replies}
    assert PAIN_VIDEO not in saved.state.accumulated_shown_ids.secondary_ref_ids
    assert PAIN_FOLLOW not in saved.state.accumulated_shown_ids.secondary_ref_ids
    assert len(provider.inputs) == 1
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


def test_a06_veneer_price_and_implant_warranty_do_not_swap_services(tmp_path: Path) -> None:
    outcome, _, _, calls = _run(
        tmp_path,
        _raw(
            _price_part(request_id="r1", service_id="veneers", topic_id="prosthetics"),
            _content_part(
                request_id="r2",
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                text=WARRANTY_LIVE,
            ),
        ),
        key=SessionKey(client_id="demo", sid="mp-a06"),
        message="Сколько стоят виниры и есть ли гарантия на импланты?",
    )

    resolved = outcome.response.resolved
    text = outcome.response.rendered_text
    assert [(part.request_id, part.status, part.service_id, part.topic_id) for part in resolved.d2_request_parts] == [
        ("r1", "answered", "veneers", "prosthetics"),
        ("r2", "answered", None, "clinic"),
    ]
    assert [row.offer_id for row in resolved.d2_price_block.rows] == ["veneers.default"]
    assert "35 000" in _money(text)
    assert WARRANTY_LIVE in text
    assert WARRANTY_ALSO not in text
    assert "classic" not in {row.service_id for row in resolved.d2_price_block.rows}
    assert resolved.ui_plan.source_content_ref == "clinic__info__warranty.md"
    assert outcome.response.ui_projection.video is None
    assert outcome.response.ui_projection.quick_replies == ()
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


@pytest.mark.parametrize(
    ("first", "second"),
    [
        (
            ("veneers", "prosthetics", "veneers.default", 35_000),
            ("professional_whitening", "whitening", "professional_whitening.default", 18_000),
        ),
        (
            ("professional_whitening", "whitening", "professional_whitening.default", 18_000),
            ("veneers", "prosthetics", "veneers.default", 35_000),
        ),
    ],
)
def test_b14_two_prices_answer_first_and_defer_second(tmp_path: Path, first, second) -> None:
    first_service, first_topic, first_offer, first_amount = first
    second_service, second_topic, second_offer, second_amount = second
    outcome, _, _, _ = _run(
        tmp_path,
        _raw(
            _price_part(request_id="r1", service_id=first_service, topic_id=first_topic),
            _price_part(request_id="r2", service_id=second_service, topic_id=second_topic),
        ),
        key=SessionKey(client_id="demo", sid=f"mp-b14-{first_service}"),
        message="Два ценовых вопроса",
    )

    resolved = outcome.response.resolved
    text = _money(outcome.response.rendered_text)
    assert [(part.request_id, part.status) for part in resolved.d2_request_parts] == [
        ("r1", "answered"),
        ("r2", "deferred"),
    ]
    assert [row.offer_id for row in resolved.d2_price_block.rows] == [first_offer]
    assert len(resolved.d2_price_block.rows) <= 3
    assert [block.request_id for block in resolved.d2_part_deferred_blocks] == ["r2"]
    assert text.count(D2_PRICE_DEFERRAL_TEXT) == 1
    assert str(first_amount).replace(",", " ") in text or f"{first_amount:,}".replace(",", " ") in text or str(first_amount) in text
    assert second_offer not in {row.offer_id for row in resolved.d2_price_block.rows}
    assert str(second_amount) not in text or D2_PRICE_DEFERRAL_TEXT in text
    assert resolved.d2_result_status == "degraded"
    assert resolved.terminal_text is None


def test_b14_price_plus_info_keeps_info_and_defers_nothing_extra(tmp_path: Path) -> None:
    outcome, _, _, _ = _run(
        tmp_path,
        _raw(
            _price_part(request_id="r1", service_id="veneers", topic_id="prosthetics"),
            _content_part(
                request_id="r2",
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                text=WARRANTY_LIVE,
            ),
        ),
        key=SessionKey(client_id="demo", sid="mp-b14-price-info"),
        message="Цена виниров и гарантия",
    )

    resolved = outcome.response.resolved
    assert [part.status for part in resolved.d2_request_parts] == ["answered", "answered"]
    assert resolved.d2_part_deferred_blocks == ()
    assert WARRANTY_LIVE in outcome.response.rendered_text
    assert "35 000" in _money(outcome.response.rendered_text)
    assert outcome.response.ui_projection.quick_replies == ()
    assert outcome.response.ui_projection.video is None


def test_c02_adjacent_broken_price_keeps_independent_content(tmp_path: Path) -> None:
    """Broken independent price part must not kill live content (C02 mechanics)."""
    clients = _clients(tmp_path)
    # Deactivate the only veneers offer so price resolves to no candidates while
    # warranty content remains independently answerable.
    offer_path = (
        clients / "demo" / "target_response" / "pricebook" / "services" / "veneers.default.json"
    )
    payload = json.loads(offer_path.read_text(encoding="utf-8"))
    payload["active"] = False
    offer_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    provider = RawFakeProvider(
        _raw(
            _price_part(request_id="r1", service_id="veneers", topic_id="prosthetics"),
            _content_part(
                request_id="r2",
                content_ref="clinic__info__warranty.md",
                service_id=None,
                topic_id="clinic",
                text=WARRANTY_LIVE,
            ),
        )
    )
    with observed_common_route():
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=SessionKey(client_id="demo", sid="mp-c02"),
                user_message="Виниры цена и гарантия",
                provider=provider,
                clients_root=clients,
                store=store,
                now=NOW,
            )

    resolved = outcome.response.resolved
    assert [(part.request_id, part.status) for part in resolved.d2_request_parts] == [
        ("r1", "unavailable"),
        ("r2", "answered"),
    ]
    assert resolved.d2_price_block is None
    assert WARRANTY_LIVE in outcome.response.rendered_text
    assert resolved.d2_result_status == "degraded"
    assert resolved.terminal_text is None
