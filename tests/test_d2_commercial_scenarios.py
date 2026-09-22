"""CP5-M3: assembled A02/A11/B08 through the common D2 route."""

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


NOW = datetime(2026, 9, 22, 13, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="m3-commercial-scenarios")
WHITENING_SHORT = "Скидка 10% до 30.11.2026."
WHITENING_FULL = "Сейчас на профессиональное отбеливание действует скидка 10% до 30 ноября 2026 года."
IMPLANT_SHORT = "Скидка до 15% при оплате в день обращения."
COMPAT_TEXT = "Скидка и рассрочка не суммируются: можно выбрать один вариант."
WARRANTY_ALSO = "Гарантия на работу врача и импланты фиксируется в договоре."


def _raw_price(service_id: str, topic_id: str) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="price",
            primary_price_request_id="r1",
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "price",
                    "subject_id": None,
                    "context": "general_information",
                    "topic_id": topic_id,
                    "service_id": service_id,
                    "statement_mode": "question",
                    "situation": None,
                }],
            },
        ),
        ensure_ascii=False,
    )


def _raw_promotion(*, scope: str, service_id: str | None = None, topic_id: str | None = None) -> str:
    return json.dumps(
        production_envelope_template(
            commercial_intent="promotion",
            promotion_scope=scope,
            primary_price_request_id=None,
            patient_text=None,
            request_understanding={
                "subjects": [],
                "requests": [{
                    "request_id": "r1",
                    "kind": "content",
                    "subject_id": None,
                    "context": "general_information",
                    "topic_id": topic_id,
                    "service_id": service_id,
                    "statement_mode": "question",
                    "situation": None,
                }],
            },
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
        raise AssertionError("network forbidden in CP5-M3")

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


def _run(tmp_path: Path, raw: str, *, key: SessionKey = KEY, message: str = "Вопрос") -> object:
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
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
    return outcome, saved, provider, calls, clients


def test_a02_whitening_and_veneers_share_price_profile(tmp_path: Path) -> None:
    whitening, _, _, _, _ = _run(
        tmp_path,
        _raw_price("professional_whitening", "whitening"),
        message="Сколько стоит отбеливание?",
    )
    veneers, _, _, calls, _ = _run(
        tmp_path,
        _raw_price("veneers", "prosthetics"),
        key=SessionKey(client_id="demo", sid="m3-veneers"),
        message="Сколько стоят виниры?",
    )

    white = whitening.response.resolved
    assert [(row.offer_id, row.min_amount) for row in white.d2_price_block.rows] == [
        ("professional_whitening.default", 18_000),
    ]
    assert [block.display_text for block in white.promo_blocks] == [WHITENING_SHORT]
    assert white.d2_price_booster_block is not None
    assert white.d2_also_list_block is not None
    assert white.automatic_amplifier_blocks == ()
    assert whitening.response.ui_projection.quick_replies == ()
    assert whitening.response.ui_projection.video is None
    assert WHITENING_SHORT in whitening.response.rendered_text
    assert "18 000" in whitening.response.rendered_text.replace("\u00a0", " ").replace("\u202f", " ")

    veneer = veneers.response.resolved
    assert [(row.offer_id, row.min_amount) for row in veneer.d2_price_block.rows] == [
        ("veneers.default", 35_000),
    ]
    assert veneer.promo_blocks == ()
    assert veneer.d2_price_booster_block is None
    assert veneer.d2_also_list_block is None
    assert veneer.automatic_amplifier_blocks == ()
    assert veneers.response.ui_projection.quick_replies == ()
    assert "35 000" in veneers.response.rendered_text.replace("\u00a0", " ").replace("\u202f", " ")
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


def test_a11_direct_promotion_uses_full_form_and_can_repeat(tmp_path: Path) -> None:
    first, saved, _, _, clients = _run(
        tmp_path,
        _raw_price("professional_whitening", "whitening"),
        message="Сколько стоит отбеливание?",
    )
    assert [block.display_text for block in first.response.resolved.promo_blocks] == [WHITENING_SHORT]
    assert saved.state.accumulated_shown_ids.promo_fact_ids == ("professional_whitening_discount",)

    provider = RawFakeProvider(_raw_promotion(
        scope="service",
        service_id="professional_whitening",
        topic_id="whitening",
    ))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        direct = run_d2_dialogue_turn(
            session_key=KEY,
            user_message="Какие акции на отбеливание?",
            provider=provider,
            clients_root=clients,
            store=store,
            now=NOW.replace(minute=1),
        )
    assert [block.display_text for block in direct.response.resolved.promo_blocks] == [WHITENING_FULL]
    assert WHITENING_FULL in direct.response.rendered_text
    assert WHITENING_SHORT not in direct.response.rendered_text
    assert direct.response.resolved.d2_price_block is None
    assert direct.response.resolved.d2_price_booster_block is None
    assert direct.response.ui_projection.quick_replies == ()

    general_provider = RawFakeProvider(_raw_promotion(scope="general"))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        general = run_d2_dialogue_turn(
            session_key=SessionKey(client_id="demo", sid="m3-general-promo"),
            user_message="Какие акции?",
            provider=general_provider,
            clients_root=clients,
            store=store,
            now=NOW,
        )
    texts = [block.display_text for block in general.response.resolved.promo_blocks]
    assert WHITENING_FULL in texts
    assert len(texts) <= 4
    assert all("скидка 10%" not in text.lower() or text == WHITENING_FULL for text in texts)


def test_expired_promo_is_not_auto_or_direct_shown(tmp_path: Path) -> None:
    expired = NOW.replace(year=2026, month=12, day=1)
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    provider = RawFakeProvider(_raw_price("professional_whitening", "whitening"))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        price = run_d2_dialogue_turn(
            session_key=KEY,
            user_message="Сколько стоит отбеливание?",
            provider=provider,
            clients_root=clients,
            store=store,
            now=expired,
        )
    assert price.response.resolved.promo_blocks == ()
    assert price.response.resolved.d2_price_block is not None
    assert WHITENING_SHORT not in price.response.rendered_text
    assert WHITENING_FULL not in price.response.rendered_text

    direct_provider = RawFakeProvider(_raw_promotion(
        scope="service",
        service_id="professional_whitening",
        topic_id="whitening",
    ))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        with pytest.raises(ValueError, match="d2_promotion_no_eligible_facts"):
            run_d2_dialogue_turn(
                session_key=SessionKey(client_id="demo", sid="m3-expired-direct"),
                user_message="Какие акции на отбеливание?",
                provider=direct_provider,
                clients_root=clients,
                store=store,
                now=expired,
            )


def test_b08_price_profile_also_warranty_and_compatibility(tmp_path: Path) -> None:
    outcome, _, _, calls, _ = _run(
        tmp_path,
        _raw_price("pterygoid_implants", "implantation"),
        key=SessionKey(client_id="demo", sid="m3-b08"),
        message="Сколько стоит птеригоидный имплант?",
    )
    resolved = outcome.response.resolved
    assert [(row.offer_id, row.min_amount) for row in resolved.d2_price_block.rows] == [
        ("pterygoid_implants.default", 95_000),
    ]
    assert [block.display_text for block in resolved.promo_blocks] == [IMPLANT_SHORT]
    assert resolved.d2_price_booster_block is not None
    assert resolved.d2_also_list_block is not None
    assert resolved.d2_also_list_block.body_text == WARRANTY_ALSO
    members = resolved.d2_compatibility_blocks[0].member_ids
    visible_ids = {block.fact_id for block in resolved.promo_blocks} | {
        row.offer_id for row in resolved.d2_price_block.rows
    }
    assert members == ("implant_same_day_discount", "pterygoid_implants.default")
    assert set(members) <= visible_ids
    assert IMPLANT_SHORT in outcome.response.rendered_text
    assert "95 000" in outcome.response.rendered_text.replace("\u00a0", " ").replace("\u202f", " ")
    assert resolved.automatic_amplifier_blocks == ()
    assert outcome.response.ui_projection.quick_replies == ()
    assert COMPAT_TEXT in outcome.response.rendered_text
    assert WARRANTY_ALSO in outcome.response.rendered_text
    assert sum(name == "select_target_marketing" for _, name in calls) == 0
    assert sum(name == "resolve_d2_commercial_plan" for _, name in calls) == 1
