"""CP5-REC: assembled D2-native recovery through the common D2 route.

Fake raw → production parser → tenant snapshot → materializer/renderer →
D2DialogueStore. Provider/live/network forbidden. Decisions: D2-065, D2-078,
D2-081, T3; acceptance B16 / C02.
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

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 22, 18, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="rec-recovery")
PRICE_GAP = "К сожалению, у меня пока нет информации о стоимости этой услуги"
INFO_GAP = "К сожалению, у меня пока недостаточно информации по этому вопросу"
WARRANTY_LIVE = (
    "Да, гарантия есть: на работу врача — год, на Nobel и Impro — пожизненно, "
    "на Implantium — пять лет. Условия фиксируем в договоре."
)


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
    content_ref: str | None,
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
        "content_section_refs": section_refs or (["a:korotko"] if content_ref else []),
        "content_fallback_section_ref": fallback if content_ref else None,
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
        raise AssertionError("network forbidden in CP5-REC")

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
    message: str,
    key: SessionKey = KEY,
    clients: Path | None = None,
):
    root = clients or _clients(tmp_path)
    provider = RawFakeProvider(raw)
    with observed_common_route() as calls:
        with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
            outcome = run_d2_dialogue_turn(
                session_key=key,
                user_message=message,
                provider=provider,
                clients_root=root,
                store=store,
                now=NOW,
            )
            saved = store.read(key)
    return outcome, saved, provider, calls


def test_b16_no_price_keeps_independent_content_and_cta(tmp_path: Path) -> None:
    clients = _clients(tmp_path)
    offer_path = (
        clients / "demo" / "target_response" / "pricebook" / "services" / "veneers.default.json"
    )
    payload = json.loads(offer_path.read_text(encoding="utf-8"))
    payload["active"] = False
    offer_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    outcome, saved, provider, calls = _run(
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
        message="Сколько виниры и какая гарантия?",
        key=SessionKey(client_id="demo", sid="rec-b16"),
        clients=clients,
    )

    resolved = outcome.response.resolved
    text = outcome.response.rendered_text
    ui = outcome.response.ui_projection
    assert [(part.request_id, part.status, part.failure_reason) for part in resolved.d2_request_parts] == [
        ("r1", "unavailable", "d2_no_price_candidates"),
        ("r2", "answered", None),
    ]
    assert resolved.d2_price_block is None
    assert PRICE_GAP in text
    assert WARRANTY_LIVE in text
    assert "не оказываем" not in text.lower()
    assert any(button.action_kind == "cta" for button in ui.buttons)
    assert resolved.terminal_text is None
    assert saved is not None
    assert len(provider.inputs) == 1
    assert any(module == "core.d2_dialogue" for module, _ in calls)


def test_c02_live_price_survives_broken_content_ref(tmp_path: Path) -> None:
    outcome, _, _, _ = _run(
        tmp_path,
        _raw(
            _price_part(request_id="r1", service_id="veneers", topic_id="prosthetics"),
            _content_part(
                request_id="r2",
                content_ref="missing__doc.md",
                service_id=None,
                topic_id="clinic",
                text="Нет такого материала.",
            ),
        ),
        message="Виниры цена и фейковый материал",
        key=SessionKey(client_id="demo", sid="rec-c02-ref"),
    )

    resolved = outcome.response.resolved
    text = outcome.response.rendered_text
    assert [(part.request_id, part.status, part.failure_reason) for part in resolved.d2_request_parts] == [
        ("r1", "answered", None),
        ("r2", "unavailable", "d2_content_source_missing"),
    ]
    assert resolved.d2_price_block is not None
    assert [row.offer_id for row in resolved.d2_price_block.rows] == ["veneers.default"]
    assert "35000" in text.replace("\xa0", " ").replace(" ", "")
    assert INFO_GAP in text
    assert resolved.d2_result_status == "degraded"
    # No invented substitute service/direction card.
    assert all(row.service_id == "veneers" for row in resolved.d2_price_block.rows)


def test_c02_live_price_survives_prose_money_violation(tmp_path: Path) -> None:
    """T3: money in prose recovers or gaps; verified price stays (D2-065/D2-078)."""
    outcome, _, _, _ = _run(
        tmp_path,
        _raw(
            _price_part(request_id="r1", service_id="veneers", topic_id="prosthetics"),
            _content_part(
                request_id="r2",
                content_ref="implantation__faq__pain.md",
                service_id="classic",
                topic_id="implantation",
                text="Наркоз стоит 5000 руб.",
                section_refs=["a:sedatsiya-i-narkoz"],
                fallback=None,
            ),
        ),
        message="Виниры и боль с суммой в prose",
        key=SessionKey(client_id="demo", sid="rec-c02-money"),
    )

    resolved = outcome.response.resolved
    part = resolved.d2_request_parts[1]
    assert resolved.d2_request_parts[0].status == "answered"
    assert part.kind == "content"
    assert part.status in {"unavailable", "recovered"}
    assert part.failure_reason == "d2_model_prose_money"
    assert resolved.d2_price_block is not None
    assert "5000" not in outcome.response.rendered_text
    assert "Наркоз стоит" not in outcome.response.rendered_text
    if part.status == "unavailable":
        assert INFO_GAP in outcome.response.rendered_text
    assert resolved.d2_result_status == "degraded"


def test_optional_secondary_ui_failure_keeps_verified_price(tmp_path: Path) -> None:
    """D2-065 / D2-083: broken optional UI must not hide a verified price."""
    clients = _clients(tmp_path)
    (clients / "demo" / "video_catalog.yaml").write_text("videos: {}\n", encoding="utf-8")
    warranty = clients / "demo" / "md" / "clinic__info__warranty.md"
    body = warranty.read_text(encoding="utf-8")
    body = body.replace("cta_key: booking\ncta_action: lead\n", "")
    body = body.replace(
        "suggest_h3:\n  - chto-delat-esli-voznikla-problema\n",
        "suggest_h3: []\n",
    )
    warranty.write_text(body, encoding="utf-8")

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
        message="Цена виниров и гарантия без secondary UI",
        key=SessionKey(client_id="demo", sid="rec-optional-ui"),
        clients=clients,
    )

    resolved = outcome.response.resolved
    ui = outcome.response.ui_projection
    assert resolved.d2_request_parts[0].status == "answered"
    assert resolved.d2_price_block is not None
    assert WARRANTY_LIVE in outcome.response.rendered_text
    assert ui.video is None
    assert ui.quick_replies == ()
    # Allowed general CTA may remain; auto lead must not start.
    assert resolved.terminal_text is None
