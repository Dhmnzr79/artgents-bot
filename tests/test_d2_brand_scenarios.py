"""Offline B05 brand questions through the ordinary D2 entry."""

from __future__ import annotations

import json
import shutil
import socket
from datetime import datetime, timezone
from pathlib import Path

import pytest

from contracts.response_plan import SessionKey
from core.d2_dialogue import run_d2_dialogue_turn
from core.d2_dialogue_store import D2DialogueStore
from core.d2_live_provider import build_d2_d1r_messages
from core.one_call_envelope_protocol import production_envelope_template


NOW = datetime(2026, 9, 23, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("BOT_LOG_DIR", str(tmp_path))

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network forbidden in CP5-B05")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket.socket, "connect_ex", forbidden)
    monkeypatch.setattr(socket.socket, "sendto", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket, "getaddrinfo", forbidden)


def _raw(kind: str, *, brand_id: str | None, service_id: str | None = None,
         content_ref: str | None = None, section: str | None = None,
         text: str | None = None) -> str:
    part = {
        "request_id": "r1", "kind": kind,
        "subject_id": "s1" if kind == "price" and service_id is None else None,
        "context": "general_information", "topic_id": "implantation",
        "service_id": service_id, "brand_id": brand_id,
        "statement_mode": "question", "situation": None,
    }
    if kind == "content":
        part.update({
            "content_ref": content_ref,
            "content_text": text,
            "content_realization": "model_prose" if section else "authored",
            "content_section_refs": [section] if section else [],
        })
    return json.dumps(production_envelope_template(
        commercial_intent="price" if kind == "price" else "none",
        primary_price_request_id="r1" if kind == "price" else None,
        request_understanding={
            "subjects": ([{"subject_id": "s1", "relation": "self", "age_group": "unknown"}]
                         if kind == "price" and service_id is None else []),
            "requests": [part],
        },
    ), ensure_ascii=False)


class FakeProvider:
    def __init__(self, raw: str) -> None:
        self.raw = raw
        self.inputs = []

    def generate(self, request):
        self.inputs.append(request)
        return self.raw


def _run(tmp_path: Path, raw: str, question: str):
    clients = tmp_path / "clients"
    shutil.copytree(Path("clients") / "demo", clients / "demo")
    provider = FakeProvider(raw)
    with D2DialogueStore(tmp_path / "dialogue.sqlite") as store:
        outcome = run_d2_dialogue_turn(
            session_key=SessionKey(client_id="demo", sid="brand-test"),
            user_message=question, provider=provider, clients_root=clients,
            store=store, now=NOW,
        )
        saved = store.read(SessionKey(client_id="demo", sid="brand-test"))
    assert saved is not None
    return outcome, provider


def test_named_brand_exact_service_keeps_only_its_price(tmp_path: Path) -> None:
    outcome, provider = _run(tmp_path, _raw("price", brand_id="nobel_biocare", service_id="all_on_4"),
                             "Сколько стоит All-on-4 на Nobel?")
    block = outcome.response.resolved.d2_price_block
    assert block is not None
    assert [(row.offer_id, row.amount, row.billing_unit) for row in block.rows] == [
        ("all_on_4.jaw.nobel", 428_000, "jaw")
    ]
    assert len(provider.inputs) == 1


def test_brand_overview_has_only_that_brand_and_multiple_scales(tmp_path: Path) -> None:
    outcome, _ = _run(tmp_path, _raw("price", brand_id="implantium"),
                      "Сколько стоят импланты Implantium?")
    block = outcome.response.resolved.d2_price_block
    assert block is not None
    assert 1 <= len(block.rows) <= 3
    assert [row.offer_id for row in block.rows] == [
        "classic.one_tooth.implantium", "all_on_4.jaw.implantium",
    ]
    assert {row.billing_unit for row in block.rows} >= {"tooth_package", "jaw"}
    assert "Implantium" in outcome.response.rendered_text


@pytest.mark.parametrize(("brand", "country", "section", "question"), (
    ("impro", "Германия", "a:impro-razumnyy-balans", "Немецкие импланты ставите?"),
    ("implantium", "Южная Корея", "a:implantium-dostupnyy-variant", "Корейские импланты ставите?"),
))
def test_country_brand_content_and_prompt_use_existing_data(
    tmp_path: Path, brand: str, country: str, section: str, question: str,
) -> None:
    raw = _raw("content", brand_id=brand,
               content_ref="implantation__info__implant_systems.md",
               section=section,
               text=f"Да, используем систему {brand.capitalize()}.")
    outcome, provider = _run(tmp_path, raw, question)
    assert brand.capitalize() in outcome.response.rendered_text
    assert outcome.response.resolved.information_blocks
    system, _ = build_d2_d1r_messages(provider.inputs[0])
    assert f'"country":"{country}"' in system["content"]
    assert section.removeprefix("a:") in system["content"]


@pytest.mark.parametrize(("brand", "question", "expected", "forbidden"), (
    ("osstem", "Ставите Osstem?", "Osstem в ассортименте нет", "101 200"),
    ("straumann", "Ставите Straumann?", "недостаточно информации", "в ассортименте нет"),
    ("израильские", "Израильские импланты ставите?", "недостаточно информации", "в ассортименте нет"),
))
def test_unknown_brand_uses_only_explicit_policy_or_gap(
    tmp_path: Path, brand: str, question: str, expected: str, forbidden: str,
) -> None:
    outcome, _ = _run(tmp_path, _raw("content", brand_id=brand), question)
    assert expected in outcome.response.rendered_text
    assert forbidden not in outcome.response.rendered_text
    assert outcome.response.resolved.d2_price_block is None


def test_unknown_brand_price_never_substitutes_other_brand(tmp_path: Path) -> None:
    outcome, _ = _run(tmp_path, _raw("price", brand_id="straumann"),
                      "Сколько стоит All-on-4 на Straumann?")
    assert "недостаточно информации" in outcome.response.rendered_text
    assert outcome.response.resolved.d2_price_block is None
    assert not outcome.response.resolved.promo_blocks


def test_known_brand_without_service_offer_does_not_use_generic_price(tmp_path: Path) -> None:
    outcome, _ = _run(
        tmp_path,
        _raw("price", brand_id="nobel_biocare", service_id="pterygoid_implants"),
        "Сколько стоят птеригоидные импланты Nobel?",
    )
    assert outcome.response.rendered_text.strip()
    assert outcome.response.resolved.d2_price_block is None
    assert not outcome.response.resolved.promo_blocks
    assert outcome.response.resolved.d2_result_status == "failed"
