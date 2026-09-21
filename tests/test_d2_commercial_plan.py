"""CP5-M2: D2-native commercial plan is frozen before render on the common route."""

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


NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
KEY = SessionKey(client_id="demo", sid="m2-commercial-plan")


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
        raise AssertionError("network forbidden in CP5-M2")

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
        assert module != "session", "second ordinary memory called"

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _run(tmp_path: Path, raw: str, *, key: SessionKey = KEY, now: datetime = NOW):
    clients = tmp_path / "clients"
    if not (clients / "demo").exists():
        shutil.copytree(Path("clients") / "demo", clients / "demo")
    provider = RawFakeProvider(raw)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=key,
            user_message="Сколько стоит?",
            provider=provider,
            clients_root=clients,
            store=store,
            now=now,
        )
        saved = store.read(key)
    return outcome, saved, provider, clients


def test_price_profile_freezes_short_promo_and_packages(tmp_path: Path) -> None:
    with observed_common_route() as calls:
        outcome, saved, provider, _ = _run(tmp_path, _raw_price("professional_whitening", "whitening"))

    resolved = outcome.response.resolved
    assert len(provider.inputs) == 1
    assert [(row.offer_id, row.min_amount) for row in resolved.d2_price_block.rows] == [
        ("professional_whitening.default", 18_000),
    ]
    assert [block.fact_id for block in resolved.promo_blocks] == ["professional_whitening_discount"]
    assert resolved.promo_blocks[0].display_text == "Скидка 10% до 30.11.2026."
    assert resolved.automatic_amplifier_blocks == ()
    assert resolved.d2_price_booster_block is not None
    assert resolved.d2_price_booster_block.package_id == "demo_payment_booster"
    assert resolved.d2_also_list_block is not None
    assert resolved.d2_also_list_block.package_id == "demo_also_diagnostics"
    assert "Скидка 10% до 30.11.2026." in outcome.response.rendered_text
    assert "Удобный способ оплаты можно обсудить на консультации." in outcome.response.rendered_text
    assert "Перед лечением доступна диагностика по показаниям." in outcome.response.rendered_text
    assert saved.state.accumulated_shown_ids.promo_fact_ids == ("professional_whitening_discount",)
    assert sum(name == "resolve_d2_commercial_plan" for _, name in calls) == 1
    assert sum(name == "select_target_marketing" for _, name in calls) == 0


def test_empty_packages_keep_published_price(tmp_path: Path) -> None:
    outcome, saved, _, _ = _run(tmp_path, _raw_price("caries", "treatment"))
    resolved = outcome.response.resolved
    assert [(row.offer_id, row.min_amount) for row in resolved.d2_price_block.rows] == [
        ("caries.default", 6_500),
    ]
    assert resolved.promo_blocks == ()
    assert resolved.d2_price_booster_block is None
    assert resolved.d2_also_list_block is None
    assert resolved.d2_compatibility_blocks == ()
    assert saved.state.accumulated_shown_ids.promo_fact_ids == ()
    assert "от 6 500" in outcome.response.rendered_text.replace("\u00a0", " ").replace("\u202f", " ")


def test_shown_auto_promo_is_not_repeated(tmp_path: Path) -> None:
    first, saved, _, clients = _run(tmp_path, _raw_price("professional_whitening", "whitening"))
    assert [block.fact_id for block in first.response.resolved.promo_blocks] == ["professional_whitening_discount"]
    provider = RawFakeProvider(_raw_price("professional_whitening", "whitening"))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        second = run_d2_dialogue_turn(
            session_key=KEY,
            user_message="А ещё раз про цену?",
            provider=provider,
            clients_root=clients,
            store=store,
            now=NOW.replace(minute=1),
        )
    assert second.response.resolved.promo_blocks == ()
    assert second.response.resolved.d2_price_block is not None
    assert second.response.resolved.d2_price_booster_block is not None
    assert saved.state.accumulated_shown_ids.promo_fact_ids == ("professional_whitening_discount",)


def test_compatibility_block_uses_authored_explanation(tmp_path: Path) -> None:
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    config = clients / "demo" / "target_response" / "d2_commercial.json"
    payload = json.loads(config.read_text(encoding="utf-8"))
    payload["incompatibility_groups"] = [{
        "group_id": "demo_whitening_discount_or_offer",
        "offer_or_fact_ids": ["professional_whitening_discount", "professional_whitening.default"],
        "explanation_text": "Скидка оформляется отдельно от опубликованной цены.",
    }]
    config.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    provider = RawFakeProvider(_raw_price("professional_whitening", "whitening"))
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=KEY,
            user_message="Сколько стоит?",
            provider=provider,
            clients_root=clients,
            store=store,
            now=NOW,
        )
    blocks = outcome.response.resolved.d2_compatibility_blocks
    assert len(blocks) == 1
    assert blocks[0].member_ids == ("professional_whitening_discount", "professional_whitening.default")
    assert "Скидка оформляется отдельно от опубликованной цены." in outcome.response.rendered_text
    assert [block.fact_id for block in outcome.response.resolved.promo_blocks] == ["professional_whitening_discount"]
